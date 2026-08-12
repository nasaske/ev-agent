from __future__ import annotations

from dataclasses import dataclass

from .signals import (
    APPROVAL,
    CORRECTION,
    ErrorKind,
    Verdict,
    classify_error,
    classify_user_message,
    verdict_from,
)
from .sources import (
    ROLE_AGENT,
    ROLE_ERROR,
    ROLE_TOOL,
    ROLE_USER,
    Session,
    read_turns,
    relative_to_home,
)

_EDITING_TOOLS = frozenset({"Write", "Edit", "MultiEdit", "NotebookEdit", "apply_patch"})
_MIN_TOOL_CALLS = 3
_RESOLVED_PREFIX = "- RESOLVED:"
_OPEN_PREFIX = "- UNRESOLVED:"

_SECTION_BUDGET = (
    ("## What the user asked for", 0.34),
    ("## Failures that were fixed", 0.26),
    ("## What was actually done", 0.24),
    ("## How the user responded", 0.16),
)


@dataclass(frozen=True)
class Digest:
    session: Session
    text: str
    user_turns: int
    errors: int
    resolved: int
    verdict: Verdict
    tools: tuple[str, ...]
    edits: int
    tool_calls: int

    @property
    def did_real_work(self) -> bool:
        return self.edits > 0 or self.tool_calls >= _MIN_TOOL_CALLS

    @property
    def has_signal(self) -> bool:
        return self.did_real_work and not self.verdict.refused

    @property
    def summary(self) -> str:
        return (
            f"{self.user_turns} turns, {self.edits} edits, "
            f"{self.resolved}/{self.errors} failures fixed, {self.verdict.label}"
        )


def build(session: Session, max_chars: int) -> Digest:
    intent: list[str] = []
    failures: list[str] = []
    work: list[str] = []
    responses: list[str] = []
    tools: list[str] = []

    approvals = corrections = rejections = 0
    user_turns = edits = real_errors = resolved = tool_calls = 0
    open_failures: dict[str, int] = {}

    for turn in read_turns(session):
        if turn.role == ROLE_USER:
            user_turns += 1
            reaction = classify_user_message(turn.text)
            if reaction == CORRECTION:
                corrections += 1
                responses.append(f"- pushed back: {_clip(turn.text, 260)}")
            elif reaction == APPROVAL:
                approvals += 1
                responses.append(f"- approved: {_clip(turn.text, 160)}")
            else:
                intent.append(f"- asked: {_clip(turn.text, 360)}")

        elif turn.role == ROLE_ERROR:
            kind = classify_error(turn.text, turn.command)
            if kind is ErrorKind.USER_REJECTION:
                rejections += 1
                responses.append("- refused a proposed action")
            elif kind is ErrorKind.REAL:
                real_errors += 1
                index = len(failures)
                failures.append(f"{_OPEN_PREFIX} {_clip(turn.text, 280)}")
                open_failures.setdefault(_command_key(turn.command), index)

        elif turn.role == ROLE_TOOL:
            if turn.tool:
                tool_calls += 1
                if turn.tool not in tools:
                    tools.append(turn.tool)
                if turn.tool in _EDITING_TOOLS:
                    edits += 1
                index = open_failures.pop(_command_key(turn.text), None)
                if index is not None:
                    resolved += 1
                    failures[index] = failures[index].replace(_OPEN_PREFIX, _RESOLVED_PREFIX, 1)
            work.append(f"- {_clip(turn.text, 190)}")

        elif turn.role == ROLE_AGENT:
            work.append(f"- said: {_clip(turn.text, 220)}")

    verdict = verdict_from(approvals, corrections, rejections)
    text = _assemble(session, verdict, intent, failures, work, responses, max_chars)

    return Digest(
        session=session,
        text=text,
        user_turns=user_turns,
        errors=real_errors,
        resolved=resolved,
        verdict=verdict,
        tools=tuple(tools),
        edits=edits,
        tool_calls=tool_calls,
    )


def _command_key(described: str) -> str:
    tokens = [token for token in described.split() if token]
    return " ".join(tokens[:2]) if tokens else ""


def _assemble(
    session: Session,
    verdict: Verdict,
    intent: list[str],
    failures: list[str],
    work: list[str],
    responses: list[str],
    max_chars: int,
) -> str:
    header = [
        f"# Session {session.label}",
        f"date: {session.modified:%Y-%m-%d}",
        f"file: {relative_to_home(session.path)}",
        f"outcome: {verdict.label}",
        "",
    ]
    budget = max_chars - sum(len(line) + 1 for line in header)

    content = (
        intent,
        [line for line in failures if line.startswith(_RESOLVED_PREFIX)],
        work,
        responses,
    )

    parts: list[str] = list(header)
    for (title, share), lines in zip(_SECTION_BUDGET, content):
        if not lines:
            continue
        allowance = int(budget * share) - (len(title) + 2)
        fitted = _fit(lines, allowance)
        if not fitted:
            continue
        parts.append(title)
        parts.extend(fitted)
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
