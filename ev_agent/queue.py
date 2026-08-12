from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

_QUEUE_FILE = "pending.jsonl"
_LOCK_FILE = "drain.lock"
_STALE_LOCK_SECONDS = 3600


@dataclass(frozen=True)
class Pending:
    path: Path
    queued_at: str

    def to_json(self) -> str:
        return json.dumps({"path": str(self.path), "queued_at": self.queued_at})


class DrainBusy(RuntimeError):
    pass


def enqueue(cache_dir: Path, transcript: Path) -> bool:
    cache_dir.mkdir(parents=True, exist_ok=True)
    queue_path = cache_dir / _QUEUE_FILE

    if any(item.path == transcript for item in pending(cache_dir)):
        return False

    entry = Pending(path=transcript, queued_at=datetime.now(tz=timezone.utc).isoformat())
    with queue_path.open("a", encoding="utf-8") as handle:
        handle.write(entry.to_json() + "\n")
    return True


def pending(cache_dir: Path) -> list[Pending]:
    queue_path = cache_dir / _QUEUE_FILE
    if not queue_path.is_file():
        return []

    items: list[Pending] = []
    seen: set[str] = set()
    for line in queue_path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        raw = str(payload.get("path", ""))
        if not raw or raw in seen:
            continue
        seen.add(raw)
        items.append(Pending(path=Path(raw), queued_at=str(payload.get("queued_at", ""))))
    return items


def rewrite(cache_dir: Path, items: list[Pending]) -> None:
    queue_path = cache_dir / _QUEUE_FILE
    tmp = queue_path.with_suffix(".tmp")
    tmp.write_text("".join(item.to_json() + "\n" for item in items), encoding="utf-8")
    tmp.replace(queue_path)


def clear(cache_dir: Path) -> int:
    items = pending(cache_dir)
    rewrite(cache_dir, [])
    return len(items)


def acquire_lock(cache_dir: Path) -> Path:
    cache_dir.mkdir(parents=True, exist_ok=True)
    lock = cache_dir / _LOCK_FILE

    if lock.exists() and _is_stale(lock):
        lock.unlink(missing_ok=True)

    try:
        descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as exc:
        raise DrainBusy(f"another drain is running ({lock})") from exc

    with os.fdopen(descriptor, "w") as handle:
        handle.write(str(os.getpid()))
    return lock


def release_lock(lock: Path) -> None:
    lock.unlink(missing_ok=True)


def _is_stale(lock: Path) -> bool:
    try:
        age = datetime.now(tz=timezone.utc).timestamp() - lock.stat().st_mtime
    except OSError:
        return True
    return age > _STALE_LOCK_SECONDS
