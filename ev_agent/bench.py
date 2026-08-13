from __future__ import annotations

import time
from dataclasses import dataclass, replace
from pathlib import Path

from . import grounding
from .config import Config
from .distill import build
from .model import SYSTEM_PROMPT, Client, ModelUnavailable
from .render import Candidate, Skipped, claim_of, parse
from .scrub import scrub
from .sources import Session


@dataclass(frozen=True)
class Measurement:
    model: str
    seconds: float
    candidate: Candidate | None
    digest: str = ""
    error: str = ""

    @property
    def outcome(self) -> str:
        if self.error:
            return "error"
        if self.candidate is None:
            return "skip"
        return "wrote"

    @property
    def evidence(self) -> grounding.Grounding:
        if self.candidate is None:
            return grounding.Grounding(checked=(), found=())
        return grounding.check(claim_of(self.candidate), self.digest)

    @property
    def grounding(self) -> float:
        if self.candidate is None:
            return 0.0
        return self.evidence.share


def reference_digest(session: Session, config: Config) -> str:
    return scrub(build(session, config.max_digest_chars).text).text


def measure(model: str, digest: str, config: Config) -> Measurement:
    client = Client(
        base_url=config.ollama_url,
        model=model,
        timeout=config.timeout_seconds,
        context_window=config.context_window,
    ).resident()

    started = time.monotonic()
    try:
        client.ensure_ready()
        reply = client.generate(SYSTEM_PROMPT, digest)
        candidate = parse(reply)
        return Measurement(model, time.monotonic() - started, candidate, digest)
    except Skipped:
        return Measurement(model, time.monotonic() - started, None, digest)
    except ModelUnavailable as exc:
        return Measurement(model, time.monotonic() - started, None, digest, str(exc)[:80])
    finally:
        client.unload()


def compare(models: list[str], session: Session, config: Config) -> list[Measurement]:
    digest = reference_digest(session, config)
    return [measure(model, digest, config) for model in models]


def report(
    measurement: Measurement,
    width: int = 96,
    floor: float = grounding.DEFAULT_FLOOR,
) -> str:
    head = f"{measurement.model}  ·  {measurement.seconds:.0f}s  ·  {measurement.outcome}"
    if measurement.error:
        return f"{head}\n  {measurement.error}"
    if measurement.candidate is None:
        return f"{head}\n  declined to write a note"

    evidence = measurement.evidence
    kept = evidence.share >= floor
    lines = [
        (
            f"{head}  ·  grounding {evidence.share:.2f}  ·  "
            f"{'kept' if kept else f'ungrounded, below {floor:.2f}'}"
        ),
        f"  title:   {measurement.candidate.title[:width]}",
        f"  pattern: {' '.join(measurement.candidate.pattern.split())[:width]}",
    ]
    if not kept:
        lines.append(f"  invented: {', '.join(evidence.missing[:8])}"[:width])
    return "\n".join(lines)


def with_model(config: Config, model: str) -> Config:
    return replace(config, model=model)


def transcript_at(raw: str) -> Path:
    return Path(raw).expanduser().resolve()
