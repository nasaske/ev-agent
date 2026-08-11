from __future__ import annotations

from dataclasses import dataclass

from .sources import (
    ROLE_AGENT,
    ROLE_ERROR,
    ROLE_TOOL,
    ROLE_USER,
    Session,
    read_turns,
    relative_to_home,
)

_CORRECTION_MARKERS = (
    "na verdade",
    "mentira",
    "não é isso",
    "nao e isso",
    "errado",
    "corrige",
    "actually",
    "no, ",
    "that's wrong",
    "thats wrong",
    "not what i",
    "instead",
    "prefiro",
)

_FAILURE_PREFIX = "- FAILED:"

_SECTION_BUDGET = (
    ("## What the user wanted", 0.45),
    ("## What went wrong", 0.30),
    ("## Trace", 0.15),
    ("## What the agent concluded", 0.10),
)


@dataclass(frozen=True)
class Digest:
    session: Session
    text: str
    user_turns: int
    errors: int
    corrections: int
    tools: tuple[str, ...]

    @property
    def has_signal(self) -> bool:
        return self.errors > 0 or self.corrections > 0

    @property
    def summary(self) -> str:
        return (
            f"{self.user_turns} turns, {self.errors} errors, "
            f"{self.corrections} corrections, {len(self.tools)} tools"
        )


def build(session: Session, max_chars: int) -> Digest:
    intent: list[str] = []
    trace: list[str] = []
    outcome: list[str] = []
    tools: list[str] = []
    errors = corrections = user_turns = 0

    for turn in read_turns(session):
        if turn.role == ROLE_USER:
            user_turns += 1
            if _is_correction(turn.text):
                corrections += 1
                intent.append(f"- correction: {_clip(turn.text, 400)}")
            else:
                intent.append(f"- asked: {_clip(turn.text, 400)}")
        elif turn.role == ROLE_ERROR:
            errors += 1
            trace.append(f"{_FAILURE_PREFIX} {_clip(turn.text, 300)}")
        elif turn.role == ROLE_TOOL:
            if turn.tool and turn.tool not in tools:
                tools.append(turn.tool)
            trace.append(f"- {_clip(turn.text, 200)}")
        elif turn.role == ROLE_AGENT:
            outcome.append(f"- {_clip(turn.text, 300)}")

    text = _assemble(session, intent, trace, outcome, max_chars)
    return Digest(
        session=session,
        text=text,
        user_turns=user_turns,
        errors=errors,
        corrections=corrections,
        tools=tuple(tools),
    )


def _assemble(
    session: Session,
    intent: list[str],
    trace: list[str],
    outcome: list[str],
    max_chars: int,
) -> str:
    header = [
        f"# Session {session.label}",
        f"date: {session.modified:%Y-%m-%d}",
        f"file: {relative_to_home(session.path)}",
        "",
    ]
    budget = max_chars - sum(len(line) + 1 for line in header)

    content = (
        intent,
        [line for line in trace if line.startswith(_FAILURE_PREFIX)],
        [line for line in trace if not line.startswith(_FAILURE_PREFIX)],
        outcome[-6:],
    )

    parts: list[str] = list(header)
    for (title, share), lines in zip(_SECTION_BUDGET, content):
        if not lines:
            continue
        parts.append(title)
        parts.extend(_fit(lines, int(budget * share)))
        parts.append("")

    return "\n".join(parts).strip()


def _fit(lines: list[str], allowance: int) -> list[str]:
    if allowance <= 0:
        return []
    kept: list[str] = []
    used = 0
    for line in reversed(lines):
        cost = len(line) + 1
        if used + cost > allowance:
            break
        kept.append(line)
        used += cost
    return list(reversed(kept))


def _clip(text: str, limit: int) -> str:
    collapsed = " ".join(text.split())
    if len(collapsed) <= limit:
        return collapsed
    return collapsed[: limit - 1] + "…"


def _is_correction(text: str) -> bool:
    lowered = text[:300].lower()
    return any(marker in lowered for marker in _CORRECTION_MARKERS)
