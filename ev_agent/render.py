from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from .distill import Digest
from .sources import read_cwd

_FIELDS = ("TITLE", "WHEN", "PATTERN", "CASE", "WHY")
_FIELD = re.compile(rf"^({'|'.join(_FIELDS)})\s*:\s*(.*)$", re.IGNORECASE)
_THINKING = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
_EMPTY = "—"


class Skipped(Exception):
    pass


@dataclass(frozen=True)
class Candidate:
    title: str
    when: str
    pattern: str
    case: str
    why: str


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

    title = _joined(fields, "TITLE")
    if not title:
        raise Skipped("no TITLE in reply")
    if title.upper() == "SKIP":
        raise Skipped("model returned SKIP as the title")

    return Candidate(
        title=title,
        when=_joined(fields, "WHEN") or _EMPTY,
        pattern=_joined(fields, "PATTERN") or _EMPTY,
        case=_joined(fields, "CASE") or _EMPTY,
        why=_joined(fields, "WHY") or _EMPTY,
    )


def _joined(fields: dict[str, list[str]], key: str) -> str:
    return " ".join(fields.get(key, [])).strip()


def note(candidate: Candidate, digest: Digest, redactions: int, specificity: float) -> str:
    today = date.today().isoformat()
    session = digest.session
    project = _project_of(session.path, read_cwd(session))

    return f"""---
brain: shared
type: skill
project: {project}
created_at: {today}
updated_at: {today}
source: ev-agent
session: {session.label}
outcome: {digest.verdict.label}
specificity: {specificity:.2f}
status: candidate
---

# {candidate.title}

## When
{candidate.when}

## Pattern
{candidate.pattern}

## What happened
{candidate.case}

## Why it held
{candidate.why}

---

> Drafted by [[E.V Agent]] from `{session.harness}` session `{session.session_id[:8]}`
> on {session.modified:%Y-%m-%d} — {digest.summary}, {redactions} redactions,
> specificity {specificity:.2f}. Review before promoting out of `_inbox`.
"""


def _project_of(path: Path, cwd: str = "") -> str:
    if cwd:
        name = Path(cwd).name
        if name and Path(cwd) != Path.home():
            return name
        return _EMPTY

    encoded = path.parent.name
    if not encoded.startswith("-"):
        return encoded or _EMPTY

    marker = "-projetos-"
    if marker in encoded:
        tail = encoded.rsplit(marker, 1)[-1]
        return tail.strip("-") or _EMPTY

    segments = [segment for segment in encoded.split("-") if segment]
    home = Path.home()
    root = [segment for segment in (home.parts[-1], "home") if segment]
    meaningful = [segment for segment in segments if segment not in root]
    return "-".join(meaningful) or _EMPTY
