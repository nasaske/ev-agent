from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timezone
from pathlib import Path

_STATE_FILE = "state.json"
_RECENT_LIMIT = 8

IDLE = "idle"
READING = "reading"
SCRUBBING = "scrubbing"
WEIGHING = "weighing"
ASKING = "asking model"
WRITING = "writing"

STAGES = (READING, SCRUBBING, WEIGHING, ASKING, WRITING)


def _now() -> str:
    return datetime.now(tz=timezone.utc).isoformat(timespec="seconds")


@dataclass(frozen=True)
class Current:
    session: str = ""
    stage: str = IDLE
    started_at: str = ""
    specificity: float = 0.0
    outcome_hint: str = ""


@dataclass(frozen=True)
class State:
    phase: str = IDLE
    pid: int = 0
    backend: str = ""
    model: str = ""
    total: int = 0
    done: int = 0
    queued: int = 0
    updated_at: str = ""
    current: Current = field(default_factory=Current)
    tally: dict[str, int] = field(default_factory=dict)
    recent: list[dict] = field(default_factory=list)

    @property
    def running(self) -> bool:
        return self.phase != IDLE and _alive(self.pid)


def _alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return Path(f"/proc/{pid}").exists()
    return True


class Reporter:
    def __init__(self, cache_dir: Path, backend: str, model: str, total: int) -> None:
        self.path = cache_dir / _STATE_FILE
        cache_dir.mkdir(parents=True, exist_ok=True)
        self.state = State(
            phase="working",
            pid=os.getpid(),
            backend=backend,
            model=model,
            total=total,
            updated_at=_now(),
        )
        self._flush()

    def begin(self, session: str) -> None:
        self.state = replace(
            self.state,
            current=Current(session=session, stage=READING, started_at=_now()),
        )
        self._flush()

    def stage(self, stage: str, specificity: float | None = None) -> None:
        current = replace(self.state.current, stage=stage)
        if specificity is not None:
            current = replace(current, specificity=specificity)
        self.state = replace(self.state, current=current)
        self._flush()

    def finish(self, session: str, outcome: str, detail: str = "") -> None:
        tally = dict(self.state.tally)
        tally[outcome] = tally.get(outcome, 0) + 1
        recent = [
            {"session": session, "outcome": outcome, "detail": detail, "at": _now()},
            *self.state.recent,
        ][:_RECENT_LIMIT]
        self.state = replace(
            self.state,
            done=self.state.done + 1,
            tally=tally,
            recent=recent,
            current=Current(),
        )
        self._flush()

    def queued(self, count: int) -> None:
        self.state = replace(self.state, queued=count)
        self._flush()

    def close(self) -> None:
        self.state = replace(self.state, phase=IDLE, pid=0, current=Current())
        self._flush()

    def _flush(self) -> None:
        self.state = replace(self.state, updated_at=_now())
        payload = asdict(self.state)
        tmp = self.path.with_suffix(".tmp")
        try:
            tmp.write_text(json.dumps(payload, indent=1), encoding="utf-8")
            tmp.replace(self.path)
        except OSError:
            return


def read(cache_dir: Path) -> State:
    try:
        payload = json.loads((cache_dir / _STATE_FILE).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, ValueError):
        return State()

    current = payload.get("current") or {}
    return State(
        phase=str(payload.get("phase", IDLE)),
        pid=int(payload.get("pid", 0) or 0),
        backend=str(payload.get("backend", "")),
        model=str(payload.get("model", "")),
        total=int(payload.get("total", 0) or 0),
        done=int(payload.get("done", 0) or 0),
        queued=int(payload.get("queued", 0) or 0),
        updated_at=str(payload.get("updated_at", "")),
        current=Current(
            session=str(current.get("session", "")),
            stage=str(current.get("stage", IDLE)),
            started_at=str(current.get("started_at", "")),
            specificity=float(current.get("specificity", 0.0) or 0.0),
            outcome_hint=str(current.get("outcome_hint", "")),
        ),
        tally=dict(payload.get("tally") or {}),
        recent=list(payload.get("recent") or []),
    )
