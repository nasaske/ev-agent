from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from .distill import Digest

_FIELD = re.compile(r"^(TITLE|CONTEXT|LESSON|EVIDENCE)\s*:\s*(.*)$", re.IGNORECASE)
_THINKING = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
_EMPTY = "—"


class Skipped(Exception):
    pass


@dataclass(frozen=True)
class Candidate:
    title: str
    context: str
    lesson: str
    evidence: str


def parse(reply: str) -> Candidate:
    cleaned = _THINKING.sub("", reply).strip()
    if not cleaned or cleaned.upper().startswith("SKIP"):
        raise Skipped("model returned SKIP")

    fields: dict[str, list[str]] = {}
    current: str | None = None
    for line in cleaned.splitlines():
        match = _FIELD.match(line.strip())
        if match:
            current = match.group(1).upper()
            fields[current] = [match.group(2).strip()]
        elif current and line.strip():
            fields[current].append(line.strip())

    title = " ".join(fields.get("TITLE", [])).strip()
    if not title:
        raise Skipped("no TITLE in reply")

    return Candidate(
        title=title,
        context=" ".join(fields.get("CONTEXT", [])).strip() or _EMPTY,
        lesson=" ".join(fields.get("LESSON", [])).strip() or _EMPTY,
        evidence=" ".join(fields.get("EVIDENCE", [])).strip() or _EMPTY,
    )


def note(candidate: Candidate, digest: Digest, redactions: int) -> str:
    today = date.today().isoformat()
    session = digest.session
    project = _project_of(session.path)

    return f"""---
brain: shared
type: skill
project: {project}
created_at: {today}
updated_at: {today}
source: ev-agent
session: {session.label}
status: candidate
---

# {candidate.title}

## Context
{candidate.context}

## Lesson
{candidate.lesson}

## Evidence
{candidate.evidence}

---

> Drafted by [[E.V Agent]] from `{session.harness}` session `{session.session_id[:8]}`
> on {session.modified:%Y-%m-%d} — {digest.summary}, {redactions} redactions.
> Review before promoting out of `_inbox`.
"""


def _project_of(path: Path) -> str:
    for part in reversed(path.parts):
        if part.startswith("-home-") and "projetos" in part:
            return part.rsplit("-", 1)[-1] or _EMPTY
    return path.parent.name or _EMPTY
