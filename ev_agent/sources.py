from __future__ import annotations

import json
import os
import re
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

Harness = str

ROLE_USER = "user"
ROLE_AGENT = "agent"
ROLE_TOOL = "tool"
ROLE_ERROR = "error"

_TOOL_ARGUMENT_KEYS = ("command", "pattern", "query", "url", "file_path", "path", "skill")
_EMBEDDED_UUID = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.IGNORECASE
)
_ERROR_HINTS = ("error", "failed", "traceback", "exception", "not found", "denied", "erro")


@dataclass(frozen=True)
class Turn:
    role: str
    text: str
    tool: str = ""
    command: str = ""


@dataclass(frozen=True)
class Session:
    path: Path
    harness: Harness
    session_id: str
    cwd: str
    modified: datetime
    size: int

    @property
    def label(self) -> str:
        return f"{self.harness}:{self.session_id[:8]}"


def session_id_from(stem: str) -> str:
    match = _EMBEDDED_UUID.search(stem)
    return match.group(0) if match else stem


def discover(claude_root: Path, codex_root: Path) -> list[Session]:
    found: list[Session] = []
    found.extend(_discover_tree(claude_root, "claude"))
    found.extend(_discover_tree(codex_root, "codex"))
    return sorted(found, key=lambda s: s.modified, reverse=True)


def _discover_tree(root: Path, harness: Harness) -> Iterator[Session]:
    if not root.is_dir():
        return
    for path in root.rglob("*.jsonl"):
        try:
            stat = path.stat()
        except OSError:
            continue
        if stat.st_size == 0:
            continue
        yield Session(
            path=path,
            harness=harness,
            session_id=session_id_from(path.stem),
            cwd="",
            modified=datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc),
            size=stat.st_size,
        )


def read_cwd(session: Session, max_lines: int = 8) -> str:
    for index, entry in enumerate(_lines(session.path)):
        if index >= max_lines:
            break
        if cwd := entry.get("cwd"):
            return str(cwd)
        payload = entry.get("payload")
        if isinstance(payload, dict) and (cwd := payload.get("cwd")):
            return str(cwd)
    return ""


def read_turns(session: Session) -> Iterator[Turn]:
    reader = _read_claude if session.harness == "claude" else _read_codex
    issued: dict[str, str] = {}
    for line in _lines(session.path):
        yield from reader(line, issued)


def _lines(path: Path) -> Iterator[dict]:
    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            for raw in handle:
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    parsed = json.loads(raw)
                except (json.JSONDecodeError, ValueError):
                    continue
                if isinstance(parsed, dict):
                    yield parsed
    except OSError:
        return


def _read_claude(entry: dict, issued: dict[str, str]) -> Iterator[Turn]:
    kind = entry.get("type")
    if kind not in ("user", "assistant"):
        return
    message = entry.get("message") or {}
    content = message.get("content")
    speaker = ROLE_USER if kind == "user" else ROLE_AGENT

    if isinstance(content, str):
        if text := content.strip():
            yield Turn(role=speaker, text=text)
        return

    for block in content or []:
        if not isinstance(block, dict):
            continue
        block_type = block.get("type")
        if block_type == "text":
            if text := (block.get("text") or "").strip():
                yield Turn(role=speaker, text=text)
        elif block_type == "tool_use":
            described = _describe_tool(block)
            if identifier := block.get("id"):
                issued[str(identifier)] = described
            yield Turn(role=ROLE_TOOL, text=described, tool=block.get("name", "?"))
        elif block_type == "tool_result" and block.get("is_error"):
            origin = issued.get(str(block.get("tool_use_id", "")), "")
            yield Turn(
                role=ROLE_ERROR,
                text=_flatten(block.get("content"))[:600],
                command=origin,
            )


def _read_codex(entry: dict, issued: dict[str, str]) -> Iterator[Turn]:
    payload = entry.get("payload")
    if not isinstance(payload, dict):
        return
    payload_type = payload.get("type")
    call_id = str(payload.get("call_id", ""))

    if payload_type == "user_message":
        if text := (payload.get("message") or "").strip():
            yield Turn(role=ROLE_USER, text=text)
    elif payload_type == "agent_message":
        if text := (payload.get("message") or "").strip():
            yield Turn(role=ROLE_AGENT, text=text)
    elif payload_type in ("function_call", "custom_tool_call"):
        name = payload.get("name") or "?"
        arguments = _flatten(payload.get("arguments"))[:300]
        described = f"{name} {arguments}"
        if call_id:
            issued[call_id] = described
        yield Turn(role=ROLE_TOOL, text=described, tool=name)
    elif payload_type in ("function_call_output", "custom_tool_call_output"):
        output = _flatten(payload.get("output"))
        if _looks_like_error(output):
            yield Turn(role=ROLE_ERROR, text=output[:600], command=issued.get(call_id, ""))


def _describe_tool(block: dict) -> str:
    name = block.get("name", "?")
    arguments = block.get("input") or {}
    if not isinstance(arguments, dict):
        return name
    for key in _TOOL_ARGUMENT_KEYS:
        if value := arguments.get(key):
            return f"{name} {str(value)[:300]}"
    return name


def _flatten(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return " ".join(_flatten(item) for item in value)
    if isinstance(value, dict):
        for key in ("text", "content", "output", "message"):
            if key in value:
                return _flatten(value[key])
        return ""
    return str(value)


def _looks_like_error(text: str) -> bool:
    lowered = text[:400].lower()
    return any(hint in lowered for hint in _ERROR_HINTS)


def relative_to_home(path: Path) -> str:
    try:
        return "~/" + str(path.relative_to(Path.home()))
    except ValueError:
        return str(path)


def newer_than(sessions: list[Session], days: int) -> list[Session]:
    if days <= 0:
        return sessions
    cutoff = datetime.now(tz=timezone.utc).timestamp() - days * 86400
    return [s for s in sessions if s.modified.timestamp() >= cutoff]


def env_flag(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}
