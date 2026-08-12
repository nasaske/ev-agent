from __future__ import annotations

import time
from dataclasses import dataclass, replace
from pathlib import Path

from .config import Config
from .distill import build
from .model import SYSTEM_PROMPT, Client, ModelUnavailable
from .render import Candidate, Skipped, parse
from .scrub import scrub
from .sources import Session


@dataclass(frozen=True)
class Measurement:
    model: str
    seconds: float
    candidate: Candidate | None
    error: str = ""

    @property
    def outcome(self) -> str:
        if self.error:
            return "error"
        if self.candidate is None:
            return "skip"
        return "wrote"


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
        return Measurement(model, time.monotonic() - started, candidate)
    except Skipped:
        return Measurement(model, time.monotonic() - started, None)
    except ModelUnavailable as exc:
        return Measurement(model, time.monotonic() - started, None, str(exc)[:80])
    finally:
        client.unload()


def compare(models: list[str], session: Session, config: Config) -> list[Measurement]:
    digest = reference_digest(session, config)
    return [measure(model, digest, config) for model in models]


def report(measurement: Measurement, width: int = 96) -> str:
    head = f"{measurement.model}  ·  {measurement.seconds:.0f}s  ·  {measurement.outcome}"
    if measurement.error:
        return f"{head}\n  {measurement.error}"
    if measurement.candidate is None:
        return f"{head}\n  declined to write a note"

    pattern = " ".join(measurement.candidate.pattern.split())
    return (
        f"{head}\n"
        f"  title:   {measurement.candidate.title[:width]}\n"
        f"  pattern: {pattern[:width]}"
    )


def with_model(config: Config, model: str) -> Config:
    return replace(config, model=model)


def transcript_at(raw: str) -> Path:
    return Path(raw).expanduser().resolve()
