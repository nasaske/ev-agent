from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

HOME = Path.home()

DEFAULT_VAULT = HOME / "Documentos" / "Obsidian Vault"
DEFAULT_CLAUDE = HOME / ".claude" / "projects"
DEFAULT_CODEX = HOME / ".codex" / "sessions"

DEFAULT_MODEL = "phi4-mini"
DEFAULT_OLLAMA_URL = "http://127.0.0.1:11434"
DEFAULT_BACKEND = "ollama"
DEFAULT_OPENROUTER_MODEL = "google/gemini-2.5-flash"
DEFAULT_LANGUAGE = "en"


def _path(name: str, default: Path) -> Path:
    raw = os.environ.get(name, "").strip()
    return Path(raw).expanduser() if raw else default


def _int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, "").strip() or default)
    except ValueError:
        return default


def _flag(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, "").strip() or default)
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
    context_window: int
    backend: str
    openrouter_model: str
    allow_free_models: bool
    min_specificity: float
    min_grounding: float
    settle_minutes: int
    praised_min_specificity: float
    common_term_ratio: float
    config_dir: Path
    language: str
    note_language: str
    ui_port: int

    @classmethod
    def load(cls) -> "Config":
        vault = _path("EV_VAULT", DEFAULT_VAULT)
        skills = _path("EV_SKILLS_DIR", vault / "AI Brain" / "Skills Brain")
        language = os.environ.get("EV_LANG", DEFAULT_LANGUAGE).strip() or DEFAULT_LANGUAGE
        return cls(
            claude_projects=_path("EV_CLAUDE_PROJECTS", DEFAULT_CLAUDE),
            codex_sessions=_path("EV_CODEX_SESSIONS", DEFAULT_CODEX),
            skills_dir=skills,
            inbox_dir=_path("EV_INBOX", skills / "_inbox"),
            cache_dir=_path("EV_CACHE", HOME / ".cache" / "ev-agent"),
            model=os.environ.get("EV_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL,
            ollama_url=os.environ.get("EV_OLLAMA_URL", DEFAULT_OLLAMA_URL).rstrip("/"),
            min_user_turns=_int("EV_MIN_USER_TURNS", 4),
            max_digest_chars=_int("EV_MAX_DIGEST_CHARS", 8_000),
            timeout_seconds=_int("EV_TIMEOUT", 600),
            context_window=_int("EV_NUM_CTX", 4096),
            backend=os.environ.get("EV_BACKEND", DEFAULT_BACKEND).strip() or DEFAULT_BACKEND,
            openrouter_model=os.environ.get("EV_OPENROUTER_MODEL", "").strip()
            or DEFAULT_OPENROUTER_MODEL,
            allow_free_models=_flag("EV_ALLOW_FREE"),
            min_specificity=_float("EV_MIN_SPECIFICITY", 0.55),
            min_grounding=_float("EV_MIN_GROUNDING", 0.40),
            settle_minutes=_int("EV_SETTLE_MINUTES", 30),
            praised_min_specificity=_float("EV_PRAISED_MIN_SPECIFICITY", 0.42),
            common_term_ratio=_float("EV_COMMON_TERM_RATIO", 0.04),
            config_dir=_path("EV_CONFIG", HOME / ".config" / "ev-agent"),
            language=language,
            note_language=os.environ.get("EV_NOTE_LANG", "").strip() or language,
            ui_port=_int("EV_UI_PORT", 7317),
        )
