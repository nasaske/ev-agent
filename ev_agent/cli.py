from __future__ import annotations

import argparse
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from . import __version__, openrouter, queue, rarity
from .config import Config
from .distill import Digest, build
from .model import SYSTEM_PROMPT, Client, ModelUnavailable
from .render import Skipped, note, parse
from .scrub import scrub
from .sources import Session, discover, newer_than, relative_to_home, session_id_from
from .store import Ledger, list_candidates, promote, slugify, write_candidate

WROTE = "written"
QUARANTINED = "quarantined"
NO_WORK = "no-work"
REWORKED = "reworked"
ROUTINE = "routine"
MODEL_SKIP = "model-skip"


@dataclass(frozen=True)
class Inspection:
    digest: Digest
    redactions: int
    quarantined: bool
    reasons: tuple[str, ...]
    clean_text: str
    specificity: float


def inspect(session: Session, config: Config, vocabulary: rarity.Vocabulary | None) -> Inspection:
    digest = build(session, config.max_digest_chars)
    result = scrub(digest.text)
    score = vocabulary.specificity(result.text, config.common_term_ratio) if vocabulary else 1.0
    return Inspection(
        digest=digest,
        redactions=len(result.hits),
        quarantined=not result.safe,
        reasons=result.residue,
        clean_text=result.text,
        specificity=score,
    )


def _backend(config: Config):
    if config.backend == "openrouter":
        return openrouter.Client(
            model=config.openrouter_model,
            timeout=config.timeout_seconds,
            api_key=openrouter.api_key_from_env(),
        )
    return Client(
        base_url=config.ollama_url,
        model=config.model,
        timeout=config.timeout_seconds,
        context_window=config.context_window,
    )


def _model_name(config: Config) -> str:
    return config.openrouter_model if config.backend == "openrouter" else config.model


def _sessions(config: Config, days: int = 0) -> list[Session]:
    return newer_than(discover(config.claude_projects, config.codex_sessions), days)


def _session_from_path(path: Path) -> Session:
    resolved = path.expanduser().resolve()
    stat = resolved.stat()
    harness = "codex" if ".codex" in resolved.parts else "claude"
    return Session(
        path=resolved,
        harness=harness,
        session_id=session_id_from(resolved.stem),
        cwd="",
        modified=datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc),
        size=stat.st_size,
    )


def _vocabulary(config: Config, rebuild: bool = False) -> rarity.Vocabulary | None:
    if not rebuild:
        if cached := rarity.load(config.cache_dir):
            return cached
    sessions = _sessions(config)
    if not sessions:
        return None
    texts = [scrub(build(session, config.max_digest_chars).text).text for session in sessions]
    vocabulary = rarity.build(texts)
    rarity.save(config.cache_dir, vocabulary)
    return vocabulary


def _process(
    session: Session,
    config: Config,
    client,
    vocabulary: rarity.Vocabulary | None,
    ledger: Ledger,
    dry_run: bool,
) -> tuple[str, str]:
    finding = inspect(session, config, vocabulary)

    if finding.quarantined:
        reason = finding.reasons[0] if finding.reasons else "?"
        ledger.record(session, QUARANTINED, ", ".join(finding.reasons[:2]))
        return QUARANTINED, reason

    if not finding.digest.did_real_work:
        ledger.record(session, NO_WORK)
        return NO_WORK, ""

    if finding.digest.verdict.refused:
        ledger.record(session, REWORKED)
        return REWORKED, finding.digest.verdict.label

    if finding.specificity < config.min_specificity:
        ledger.record(session, ROUTINE, f"{finding.specificity:.2f}")
        return ROUTINE, f"{finding.specificity:.2f}"

    if dry_run:
        return "would-send", f"{finding.digest.summary} · spec {finding.specificity:.2f}"

    candidate = parse(client.generate(SYSTEM_PROMPT, finding.clean_text))
    body = note(candidate, finding.digest, finding.redactions, finding.specificity)
    path = write_candidate(config.inbox_dir, slugify(candidate.title), body)
    ledger.record(session, WROTE, path.name)
    return WROTE, path.name


def _run_over(
    sessions: list[Session],
    config: Config,
    args: argparse.Namespace,
    label: str,
) -> int:
    dry_run = bool(getattr(args, "dry_run", False))
    client = _backend(config)

    if not dry_run:
        try:
            client.ensure_ready()
        except (ModelUnavailable, openrouter.RefusedByPolicy) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        client = client.resident()

    vocabulary = _vocabulary(config)
    ledger = Ledger.load(config.cache_dir)
    tally: dict[str, int] = {}

    print(f"{len(sessions)} {label} · backend {config.backend} · model {_model_name(config)}\n")

    try:
        for session in sessions:
            try:
                outcome, detail = _process(session, config, client, vocabulary, ledger, dry_run)
            except Skipped:
                outcome, detail = MODEL_SKIP, ""
                ledger.record(session, MODEL_SKIP)
            except (ModelUnavailable, openrouter.RefusedByPolicy) as exc:
                print(f"error: {exc}", file=sys.stderr)
                ledger.save()
                return 2

            tally[outcome] = tally.get(outcome, 0) + 1
            if outcome in (WROTE, QUARANTINED, "would-send"):
                print(f"  {outcome:<12} {session.label}  {detail}")
    finally:
        ledger.save()
        if not dry_run:
            client.unload()

    print("\n  " + " · ".join(f"{key}: {value}" for key, value in sorted(tally.items())))
    print(f"  inbox: {relative_to_home(config.inbox_dir)}")
    return 0


def cmd_scan(args: argparse.Namespace, config: Config) -> int:
    sessions = _sessions(config, args.days)
    if not sessions:
        print("No transcripts found.")
        return 0

    print(f"Scanning {len(sessions)} transcripts (nothing leaves this machine)\n")
    vocabulary = _vocabulary(config)

    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        findings = list(pool.map(lambda s: inspect(s, config, vocabulary), sessions))

    exposed = [f for f in findings if f.redactions]
    quarantined = [f for f in findings if f.quarantined]
    worked = [f for f in findings if f.digest.did_real_work and not f.digest.verdict.refused]
    specific = [f for f in worked if f.specificity >= config.min_specificity]
    praised = [f for f in findings if f.digest.verdict.accepted]

    for finding in sorted(findings, key=lambda f: f.specificity, reverse=True)[: args.top]:
        if finding.specificity < config.min_specificity and not finding.quarantined:
            continue
        flag = "QUARANTINE" if finding.quarantined else "candidate "
        print(
            f"  {flag}  {finding.digest.session.label}  spec {finding.specificity:.2f}  "
            f"{finding.digest.summary}"
        )

    print(
        f"\n  {len(sessions)} transcripts"
        f"\n  {len(exposed)} contained secrets (redacted locally)"
        f"\n  {len(quarantined)} would be quarantined — never sent to any model"
        f"\n  {len(praised)} were explicitly praised"
        f"\n  {len(worked)} did real work that stuck"
        f"\n  {len(specific)} are specific enough to be worth a skill"
    )
    return 0


def cmd_run(args: argparse.Namespace, config: Config) -> int:
    ledger = Ledger.load(config.cache_dir)
    sessions = _sessions(config, args.days)
    pending = [s for s in sessions if args.force or not ledger.seen(s)]
    cached = len(sessions) - len(pending)

    if not pending:
        print(f"Nothing to do — {cached} sessions already processed.")
        return 0
    if args.limit:
        pending = pending[: args.limit]

    return _run_over(pending, config, args, f"to consider · {cached} cached")


def cmd_session(args: argparse.Namespace, config: Config) -> int:
    try:
        session = _session_from_path(Path(args.transcript))
    except OSError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return _run_over([session], config, args, "session")


def cmd_enqueue(args: argparse.Namespace, config: Config) -> int:
    transcript = Path(args.transcript).expanduser()
    if not transcript.is_file():
        return 0
    added = queue.enqueue(config.cache_dir, transcript.resolve())
    if added and not args.quiet:
        print(f"queued {transcript.name}")
    return 0


def cmd_drain(args: argparse.Namespace, config: Config) -> int:
    items = queue.pending(config.cache_dir)
    if not items:
        print("Queue is empty.")
        return 0

    try:
        lock = queue.acquire_lock(config.cache_dir)
    except queue.DrainBusy as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    try:
        sessions: list[Session] = []
        for item in items:
            try:
                sessions.append(_session_from_path(item.path))
            except OSError:
                continue
        if args.limit:
            sessions = sessions[: args.limit]
        status = _run_over(sessions, config, args, "queued")
    finally:
        queue.release_lock(lock)

    queue.rewrite(config.cache_dir, [])
    return status


def cmd_index(args: argparse.Namespace, config: Config) -> int:
    vocabulary = _vocabulary(config, rebuild=True)
    if not vocabulary:
        print("No transcripts to index.")
        return 0
    print(
        f"Indexed {vocabulary.documents} sessions · "
        f"{len(vocabulary.frequencies)} distinct terms → {relative_to_home(config.cache_dir)}"
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
    client = _backend(config)
    ledger = Ledger.load(config.cache_dir)
    vocabulary = rarity.load(config.cache_dir)

    print(f"E.V Agent {__version__}\n")
    print(f"  backend     {config.backend} · {_model_name(config)}")
    print(f"  reachable   {'yes' if client.available() else 'no'}")
    print(f"  inbox       {relative_to_home(config.inbox_dir)}")
    print(f"  queued      {len(queue.pending(config.cache_dir))}")
    print(f"  candidates  {len(list_candidates(config.inbox_dir))} awaiting review")
    print(f"  vocabulary  {vocabulary.documents if vocabulary else 0} sessions indexed")
    print(f"  specificity floor {config.min_specificity:.2f}")
    if tally := ledger.counts():
        print("  ledger      " + " · ".join(f"{k}: {v}" for k, v in sorted(tally.items())))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ev",
        description="Turn accepted agent sessions into reviewed skill notes, locally.",
    )
    parser.add_argument("--version", action="version", version=f"E.V Agent {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    scan = subparsers.add_parser("scan", help="inventory transcripts, exposure and specificity")
    scan.add_argument("--days", type=int, default=0)
    scan.add_argument("--top", type=int, default=20)
    scan.add_argument("--jobs", type=int, default=4)
    scan.set_defaults(func=cmd_scan)

    run = subparsers.add_parser("run", help="process a batch of sessions")
    run.add_argument("--days", type=int, default=0)
    run.add_argument("--limit", type=int, default=0)
    run.add_argument("--force", action="store_true")
    run.add_argument("--dry-run", action="store_true")
    run.set_defaults(func=cmd_run)

    session = subparsers.add_parser("session", help="process one transcript now")
    session.add_argument("transcript")
    session.add_argument("--dry-run", action="store_true")
    session.set_defaults(func=cmd_session)

    enqueue = subparsers.add_parser("enqueue", help="add a transcript to the queue")
    enqueue.add_argument("transcript")
    enqueue.add_argument("--quiet", action="store_true")
    enqueue.set_defaults(func=cmd_enqueue)

    drain = subparsers.add_parser("drain", help="process the queue, one session at a time")
    drain.add_argument("--limit", type=int, default=0)
    drain.add_argument("--dry-run", action="store_true")
    drain.set_defaults(func=cmd_drain)

    index = subparsers.add_parser("index", help="rebuild the corpus vocabulary")
    index.set_defaults(func=cmd_index)

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
