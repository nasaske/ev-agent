from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from .sources import Session

_STATE_FILE = "processed.json"
_SLUG_STRIP = re.compile(r"[^a-z0-9]+")
_HASH_CHUNK = 1 << 20
_HASH_LENGTH = 16


def slugify(title: str, limit: int = 60) -> str:
    decomposed = unicodedata.normalize("NFKD", title.lower())
    ascii_only = "".join(char for char in decomposed if not unicodedata.combining(char))
    slug = _SLUG_STRIP.sub("-", ascii_only).strip("-")
    return (slug[:limit].rstrip("-")) or "untitled"


@dataclass
class Ledger:
    path: Path
    entries: dict[str, dict]

    @classmethod
    def load(cls, cache_dir: Path) -> "Ledger":
        cache_dir.mkdir(parents=True, exist_ok=True)
        path = cache_dir / _STATE_FILE
        try:
            entries = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            entries = {}
        return cls(path=path, entries=entries if isinstance(entries, dict) else {})

    def save(self) -> None:
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.entries, indent=1, sort_keys=True), encoding="utf-8")
        tmp.replace(self.path)

    def seen(self, session: Session) -> bool:
        entry = self.entries.get(str(session.path))
        if not entry:
            return False
        unchanged_size = entry.get("size") == session.size
        unchanged_mtime = entry.get("mtime") == int(session.modified.timestamp())
        return unchanged_size and unchanged_mtime

    def record(self, session: Session, outcome: str, detail: str = "") -> None:
        self.entries[str(session.path)] = {
            "size": session.size,
            "mtime": int(session.modified.timestamp()),
            "outcome": outcome,
            "detail": detail,
            "at": date.today().isoformat(),
        }

    def forget_all(self) -> int:
        count = len(self.entries)
        self.entries = {}
        return count

    def counts(self) -> dict[str, int]:
        tally: dict[str, int] = {}
        for entry in self.entries.values():
            outcome = str(entry.get("outcome", "?"))
            tally[outcome] = tally.get(outcome, 0) + 1
        return tally


def content_hash(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(_HASH_CHUNK), b""):
                digest.update(chunk)
    except OSError:
        return ""
    return digest.hexdigest()[:_HASH_LENGTH]


def write_candidate(inbox: Path, slug: str, body: str) -> Path:
    inbox.mkdir(parents=True, exist_ok=True)
    target = inbox / f"{slug}.md"
    counter = 2
    while target.exists():
        target = inbox / f"{slug}-{counter}.md"
        counter += 1
    target.write_text(body, encoding="utf-8")
    return target


def promote(inbox: Path, skills_dir: Path, slug: str) -> Path:
    source = inbox / f"{slug}.md"
    if not source.exists():
        raise FileNotFoundError(f"no candidate named {slug!r} in {inbox}")
    skills_dir.mkdir(parents=True, exist_ok=True)
    target = skills_dir / source.name
    if target.exists():
        raise FileExistsError(f"{target} already exists — merge it by hand")
    source.replace(target)
    return target


def list_candidates(inbox: Path) -> list[Path]:
    if not inbox.is_dir():
        return []
    return sorted(inbox.glob("*.md"))
