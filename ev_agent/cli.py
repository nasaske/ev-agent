from __future__ import annotations

import argparse
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from . import __version__
from .config import Config
from .distill import Digest, build
from .model import SYSTEM_PROMPT, Client, ModelUnavailable
from .render import Skipped, note, parse
from .scrub import scrub
from .sources import Session, discover, newer_than, relative_to_home
from .store import Ledger, list_candidates, promote, slugify, write_candidate


@dataclass(frozen=True)
class Inspection:
    digest: Digest
    redactions: int
    quarantined: bool
    reasons: tuple[str, ...]
    clean_text: str


def inspect(session: Session, config: Config) -> Inspection:
    digest = build(session, config.max_digest_chars)
    result = scrub(digest.text)
    return Inspection(
        digest=digest,
        redactions=len(result.hits),
        quarantined=not result.safe,
        reasons=result.residue,
        clean_text=result.text,
    )


def _client(config: Config) -> Client:
    return Client(
        base_url=config.ollama_url,
        model=config.model,
        timeout=config.timeout_seconds,
        context_window=config.context_window,
    )


def _sessions(config: Config, days: int) -> list[Session]:
    return newer_than(discover(config.claude_projects, config.codex_sessions), days)


def _inspect_many(sessions: list[Session], config: Config, jobs: int) -> list[Inspection]:
    if jobs <= 1:
        return [inspect(session, config) for session in sessions]
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        return list(pool.map(lambda session: inspect(session, config), sessions))


def cmd_scan(args: argparse.Namespace, config: Config) -> int:
    sessions = _sessions(config, args.days)
    if not sessions:
        print("No transcripts found.")
        return 0

    print(f"Scanning {len(sessions)} transcripts (nothing leaves this machine)\n")
    findings = _inspect_many(sessions, config, args.jobs)

    exposed = [f for f in findings if f.redactions]
    quarantined = [f for f in findings if f.quarantined]
    with_signal = [f for f in findings if f.digest.has_signal]

    for finding in sorted(findings, key=lambda f: f.redactions, reverse=True)[: args.top]:
        if not finding.redactions and not finding.quarantined:
            continue
        flag = "QUARANTINE" if finding.quarantined else "redacted  "
        print(
            f"  {flag}  {finding.digest.session.label}  "
            f"{finding.redactions:>4} hits  {relative_to_home(finding.digest.session.path)}"
        )
        if finding.quarantined:
            print(f"              residue: {', '.join(finding.reasons[:3])}")

    print(
        f"\n  {len(sessions)} transcripts"
        f"\n  {len(exposed)} contained secrets (redacted locally)"
        f"\n  {len(quarantined)} would be quarantined — never sent to any model"
        f"\n  {len(with_signal)} carry a lesson worth extracting"
    )
    return 0


def cmd_run(args: argparse.Namespace, config: Config) -> int:
    client = _client(config).resident()
    if not args.dry_run:
        try:
            client.ensure_ready()
        except ModelUnavailable as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
    try:
        return _run_batch(args, config, client)
    finally:
        if not args.dry_run:
            client.unload()


def _run_batch(args: argparse.Namespace, config: Config, client: Client) -> int:

    ledger = Ledger.load(config.cache_dir)
    sessions = _sessions(config, args.days)
    pending = [s for s in sessions if args.force or not ledger.seen(s)]
    cached = len(sessions) - len(pending)

    if not pending:
        print(f"Nothing to do — {cached} sessions already processed.")
        return 0

    if args.limit:
        pending = pending[: args.limit]

    print(f"{len(pending)} to consider · {cached} cached · model {config.model}\n")

    written = quarantined = skipped = 0
    for session in pending:
        finding = inspect(session, config)

        if finding.quarantined:
            quarantined += 1
            reason = finding.reasons[0] if finding.reasons else "?"
            ledger.record(session, "quarantined", ", ".join(finding.reasons[:2]))
            print(f"  quarantined  {session.label}  ({reason})")
            continue

        if not finding.digest.has_signal:
            skipped += 1
            ledger.record(session, "no-signal")
            continue

        if args.dry_run:
            print(f"  would send   {session.label}  {finding.digest.summary}")
            continue

        try:
            candidate = parse(client.generate(SYSTEM_PROMPT, finding.clean_text))
        except Skipped:
            skipped += 1
            ledger.record(session, "model-skip")
            continue
        except ModelUnavailable as exc:
            print(f"error: {exc}", file=sys.stderr)
            ledger.save()
            return 2

        body = note(candidate, finding.digest, finding.redactions)
        path = write_candidate(config.inbox_dir, slugify(candidate.title), body)
        written += 1
        ledger.record(session, "written", path.name)
        print(f"  wrote        {path.name}")

    ledger.save()
    print(
        f"\n  {written} candidates in {relative_to_home(config.inbox_dir)}"
        f"\n  {quarantined} quarantined · {skipped} without a lesson"
    )
    return 0


def cmd_list(args: argparse.Namespace, config: Config) -> int:
    candidates = list_candidates(config.inbox_dir)
    if not candidates:
        print(f"Inbox is empty: {relative_to_home(config.inbox_dir)}")
        return 0
    print(f"{len(candidates)} awaiting review in {relative_to_home(config.inbox_dir)}\n")
    for path in candidates:
        print(f"  {path.stem}")
    return 0


def cmd_promote(args: argparse.Namespace, config: Config) -> int:
    try:
        target = promote(config.inbox_dir, config.skills_dir, args.slug)
    except (FileNotFoundError, FileExistsError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"promoted → {relative_to_home(target)}")
    return 0


def cmd_status(args: argparse.Namespace, config: Config) -> int:
    client = _client(config)
    ledger = Ledger.load(config.cache_dir)
    reachable = "reachable" if client.available() else "offline"

    print(f"E.V Agent {__version__}\n")
    print(f"  claude      {relative_to_home(config.claude_projects)}")
    print(f"  codex       {relative_to_home(config.codex_sessions)}")
    print(f"  inbox       {relative_to_home(config.inbox_dir)}")
    print(f"  model       {config.model} ({reachable})")
    print(f"  candidates  {len(list_candidates(config.inbox_dir))} awaiting review")
    tally = ledger.counts()
    if tally:
        print("  ledger      " + " · ".join(f"{k}: {v}" for k, v in sorted(tally.items())))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ev",
        description="Distil Claude Code and Codex sessions into reviewed skill notes, locally.",
    )
    parser.add_argument("--version", action="version", version=f"E.V Agent {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    scan = subparsers.add_parser("scan", help="inventory transcripts and secret exposure")
    scan.add_argument("--days", type=int, default=0, help="only sessions from the last N days")
    scan.add_argument("--top", type=int, default=20, help="how many findings to print")
    scan.add_argument("--jobs", type=int, default=4, help="parallel readers")
    scan.set_defaults(func=cmd_scan)

    run = subparsers.add_parser("run", help="distil, scrub and draft candidates")
    run.add_argument("--days", type=int, default=0)
    run.add_argument("--limit", type=int, default=0, help="stop after N sessions")
    run.add_argument("--force", action="store_true", help="ignore the cache")
    run.add_argument("--dry-run", action="store_true", help="never call the model")
    run.set_defaults(func=cmd_run)

    listing = subparsers.add_parser("list", help="show candidates awaiting review")
    listing.set_defaults(func=cmd_list)

    prom = subparsers.add_parser("promote", help="move a candidate into the brain")
    prom.add_argument("slug")
    prom.set_defaults(func=cmd_promote)

    status = subparsers.add_parser("status", help="show configuration and state")
    status.set_defaults(func=cmd_status)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args, Config.load())
    except KeyboardInterrupt:
        print("\ninterrupted", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
