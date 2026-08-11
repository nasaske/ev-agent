from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

HOME = Path.home()

DEFAULT_VAULT = HOME / "Documentos" / "Obsidian Vault"
DEFAULT_CLAUDE = HOME / ".claude" / "projects"
DEFAULT_CODEX = HOME / ".codex" / "sessions"

DEFAULT_MODEL = "qwen3:4b"
DEFAULT_OLLAMA_URL = "http://127.0.0.1:11434"


def _path(name: str, default: Path) -> Path:
    raw = os.environ.get(name, "").strip()
    return Path(raw).expanduser() if raw else default


def _int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, "").strip() or default)
    except ValueError:
        return default


@dataclass(frozen=True)
class Config:
    claude_projects: Path
    codex_sessions: Path
    skills_dir: Path
    inbox_dir: Path
    cache_dir: Path
    model: str
    ollama_url: str
    min_user_turns: int
    max_digest_chars: int
    timeout_seconds: int

    @classmethod
    def load(cls) -> "Config":
        vault = _path("EV_VAULT", DEFAULT_VAULT)
        skills = _path("EV_SKILLS_DIR", vault / "AI Brain" / "Skills Brain")
        return cls(
            claude_projects=_path("EV_CLAUDE_PROJECTS", DEFAULT_CLAUDE),
            codex_sessions=_path("EV_CODEX_SESSIONS", DEFAULT_CODEX),
            skills_dir=skills,
            inbox_dir=_path("EV_INBOX", skills / "_inbox"),
            cache_dir=_path("EV_CACHE", HOME / ".cache" / "ev-agent"),
            model=os.environ.get("EV_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL,
            ollama_url=os.environ.get("EV_OLLAMA_URL", DEFAULT_OLLAMA_URL).rstrip("/"),
            min_user_turns=_int("EV_MIN_USER_TURNS", 4),
            max_digest_chars=_int("EV_MAX_DIGEST_CHARS", 12_000),
            timeout_seconds=_int("EV_TIMEOUT", 300),
        )
