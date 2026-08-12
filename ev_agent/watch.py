from __future__ import annotations

import shutil
import time
from datetime import datetime, timezone
from pathlib import Path

from . import progress

RED = "\033[38;2;224;27;61m"
BLUE = "\033[38;2;27;77;224m"
INK = "\033[38;2;226;232;242m"
MUTED = "\033[38;2;122;136;156m"
FAINT = "\033[38;2;74;85;104m"
BOLD = "\033[1m"
RESET = "\033[0m"

HIDE_CURSOR = "\033[?25l"
SHOW_CURSOR = "\033[?25h"
HOME = "\033[H"
CLEAR = "\033[2J"
CLEAR_LINE = "\033[K"

_MIN_WIDTH = 62
_MAX_WIDTH = 88

_GOOD_OUTCOMES = frozenset({"written"})
_BAD_OUTCOMES = frozenset({"quarantined"})

_STAGE_LABELS = {
    progress.READING: "read",
    progress.SCRUBBING: "scrub",
    progress.WEIGHING: "weigh",
    progress.ASKING: "model",
    progress.WRITING: "write",
}


def _width() -> int:
    columns = shutil.get_terminal_size(fallback=(80, 24)).columns
    return max(_MIN_WIDTH, min(_MAX_WIDTH, columns - 2))


def _rule(width: int, left: str = "", right: str = "") -> str:
    left_part = f" {left} " if left else ""
    right_part = f" {right} " if right else ""
    filler = "─" * max(0, width - len(left_part) - len(right_part) - 2)
    return f"{FAINT}┌{BOLD}{INK}{left_part}{RESET}{FAINT}{filler}{MUTED}{right_part}{FAINT}┐{RESET}"


def _line(width: int, content: str = "", visible: int | None = None) -> str:
    shown = visible if visible is not None else len(content)
    padding = " " * max(0, width - shown - 3)
    return f"{FAINT}│{RESET} {content}{padding}{FAINT}│{RESET}"


def _bottom(width: int) -> str:
    return f"{FAINT}└{'─' * (width - 2)}┘{RESET}"


def _elapsed(started_at: str) -> str:
    if not started_at:
        return "--:--"
    try:
        started = datetime.fromisoformat(started_at)
    except ValueError:
        return "--:--"
    if started.tzinfo is None:
        started = started.replace(tzinfo=timezone.utc)
    seconds = int((datetime.now(tz=timezone.utc) - started).total_seconds())
    if seconds < 0 or seconds > 86_400:
        return "--:--"
    return f"{seconds // 60:02d}:{seconds % 60:02d}"


def _stages(active: str) -> tuple[str, int]:
    rendered: list[str] = []
    plain: list[str] = []
    reached = active in progress.STAGES
    passed = progress.STAGES.index(active) if reached else -1

    for index, stage in enumerate(progress.STAGES):
        label = _STAGE_LABELS[stage]
        if index == passed:
            rendered.append(f"{BLUE}●{RESET} {INK}{label}{RESET}")
        elif index < passed:
            rendered.append(f"{BLUE}◦{RESET} {FAINT}{label}{RESET}")
        else:
            rendered.append(f"{FAINT}◦ {label}{RESET}")
        plain.append(f"◦ {label}")

    return "  ".join(rendered), len("  ".join(plain))


def _frame(state: progress.State) -> str:
    width = _width()
    right = f"{state.backend} · {state.model}" if state.backend else "not running"
    rows = [_rule(width, "E.V AGENT", right), _line(width)]

    if state.running:
        dot = f"{BLUE}●{RESET}"
        headline = f"{dot} {INK}working{RESET}   {MUTED}{state.done} of {state.total}{RESET}"
        plain = f"● working   {state.done} of {state.total}"
        if state.queued:
            headline += f"   {MUTED}queue {state.queued}{RESET}"
            plain += f"   queue {state.queued}"
    else:
        headline = f"{FAINT}○{RESET} {MUTED}idle{RESET}"
        plain = "○ idle"
        if state.queued:
            headline += f"   {INK}{state.queued} queued{RESET}  {FAINT}run: ev drain{RESET}"
            plain += f"   {state.queued} queued  run: ev drain"

    rows.append(_line(width, headline, len(plain)))
    rows.append(_line(width))

    if state.running and state.current.session:
        session = state.current.session
        elapsed = _elapsed(state.current.started_at)
        rows.append(
            _line(width, f"{INK}{session}{RESET}   {FAINT}{elapsed}{RESET}", len(session) + 3 + len(elapsed))
        )
        stages, stages_len = _stages(state.current.stage)
        spec = state.current.specificity
        suffix = f"   {MUTED}spec {spec:.2f}{RESET}" if spec else ""
        suffix_len = len(f"   spec {spec:.2f}") if spec else 0
        rows.append(_line(width, stages + suffix, stages_len + suffix_len))
        rows.append(_line(width))

    if state.tally:
        parts = []
        plain_parts = []
        for key, value in sorted(state.tally.items()):
            colour = BLUE if key in _GOOD_OUTCOMES else RED if key in _BAD_OUTCOMES else MUTED
            parts.append(f"{colour}{value} {key}{RESET}")
            plain_parts.append(f"{value} {key}")
        rows.append(_line(width, "  ".join(parts), len("  ".join(plain_parts))))
        rows.append(_line(width))

    if state.recent:
        rows.append(_line(width, f"{FAINT}recent{RESET}", len("recent")))
        for item in state.recent[:5]:
            outcome = str(item.get("outcome", ""))
            detail = str(item.get("detail", "")) or str(item.get("session", ""))
            colour = BLUE if outcome in _GOOD_OUTCOMES else RED if outcome in _BAD_OUTCOMES else FAINT
            room = max(8, width - 20)
            clipped = detail[:room]
            text = f"  {colour}{outcome:<13}{RESET}{MUTED}{clipped}{RESET}"
            rows.append(_line(width, text, 2 + 13 + len(clipped)))
        rows.append(_line(width))

    rows.append(_bottom(width))
    rows.append(f"{FAINT}  ctrl-c to leave · reads {progress._STATE_FILE}{RESET}")
    return "\n".join(row + CLEAR_LINE for row in rows)


def watch(cache_dir: Path, interval: float = 1.0) -> int:
    print(HIDE_CURSOR + CLEAR, end="")
    try:
        while True:
            state = progress.read(cache_dir)
            print(HOME + _frame(state) + "\033[J", end="", flush=True)
            time.sleep(interval)
    except KeyboardInterrupt:
        return 0
    finally:
        print(SHOW_CURSOR + RESET)


def snapshot(cache_dir: Path) -> str:
    return _frame(progress.read(cache_dir))
