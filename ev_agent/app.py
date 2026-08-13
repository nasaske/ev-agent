from __future__ import annotations

import json
import secrets
import shutil
import subprocess
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from . import focus as focus_module
from . import i18n, progress, queue
from .config import Config
from .page import render
from .store import list_candidates

HOST = "127.0.0.1"
_MAX_BODY = 64 * 1024
_ALLOWED_HOSTS = frozenset({HOST, "localhost"})

_APP_BROWSERS = (
    "chromium",
    "chromium-browser",
    "google-chrome",
    "google-chrome-stable",
    "brave-browser",
    "microsoft-edge",
)


class Refused(RuntimeError):
    pass


def _state_payload(config: Config) -> dict:
    state = progress.read(config.cache_dir)
    prefs = focus_module.load(config.config_dir)
    return {
        "phase": state.phase,
        "running": state.running,
        "backend": state.backend or config.backend,
        "model": state.model or (config.openrouter_model
                                 if config.backend == "openrouter" else config.model),
        "total": state.total,
        "done": state.done,
        "queued": len(queue.pending(config.cache_dir)),
        "candidates": len(list_candidates(config.inbox_dir)),
        "current": {
            "session": state.current.session,
            "stage": state.current.stage,
            "started_at": state.current.started_at,
            "specificity": state.current.specificity,
        },
        "tally": state.tally,
        "recent": state.recent[:6],
        "focus": {
            "chosen": list(prefs.focus.chosen),
            "custom": list(prefs.focus.custom),
            "everything": prefs.focus.everything,
        },
        "note_language": i18n.normalise(prefs.note_language or config.note_language),
        "areas": [
            {"slug": area.slug, "en": area.en, "pt": area.pt}
            for area in focus_module.BUILTIN
        ],
    }


def _save_focus(config: Config, payload: dict) -> dict:
    prefs = focus_module.Preferences(
        focus=focus_module.Focus.of(payload.get("chosen"), payload.get("custom")),
        note_language=i18n.normalise(str(payload.get("note_language") or "")),
    )
    focus_module.save(config.config_dir, prefs)
    return _state_payload(config)


def _handler(config: Config, token: str) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        server_version = "ev-agent"

        def log_message(self, format: str, *args: object) -> None:
            return

        def _guard(self) -> bool:
            host = (self.headers.get("Host") or "").split(":")[0]
            if host not in _ALLOWED_HOSTS:
                self._send(403, {"error": "forbidden host"})
                return False
            query = parse_qs(urlparse(self.path).query)
            supplied = (query.get("t") or [""])[0]
            if not secrets.compare_digest(supplied, token):
                self._send(403, {"error": "bad token"})
                return False
            return True

        def _send(self, status: int, payload: dict) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _send_page(self) -> None:
            body = render(token, config).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:
            route = urlparse(self.path).path
            if route in ("/", "/index.html"):
                self._send_page()
                return
            if route == "/api/state":
                if self._guard():
                    self._send(200, _state_payload(config))
                return
            self._send(404, {"error": "not found"})

        def do_POST(self) -> None:
            if urlparse(self.path).path != "/api/focus":
                self._send(404, {"error": "not found"})
                return
            if not self._guard():
                return
            try:
                length = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                self._send(400, {"error": "bad length"})
                return
            if length <= 0 or length > _MAX_BODY:
                self._send(400, {"error": "bad length"})
                return
            try:
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                self._send(400, {"error": "bad json"})
                return
            if not isinstance(payload, dict):
                self._send(400, {"error": "bad json"})
                return
            self._send(200, _save_focus(config, payload))

    return Handler


def build_server(config: Config, token: str, port: int | None = None) -> ThreadingHTTPServer:
    wanted = config.ui_port if port is None else port
    try:
        return ThreadingHTTPServer((HOST, wanted), _handler(config, token))
    except OSError as exc:
        raise Refused(f"cannot bind {HOST}:{wanted} — {exc}") from exc


def open_window(url: str) -> str:
    for name in _APP_BROWSERS:
        binary = shutil.which(name)
        if not binary:
            continue
        try:
            subprocess.Popen(
                [binary, f"--app={url}", "--window-size=1040,820"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        except OSError:
            continue
        return Path(binary).name
    webbrowser.open(url)
    return ""


def serve(config: Config, launch: bool = True) -> int:
    token = secrets.token_urlsafe(18)
    server = build_server(config, token)
    url = f"http://{HOST}:{server.server_address[1]}/?t={token}"

    print(f"E.V Agent · {url}")
    if launch:
        opened = open_window(url)
        print(f"  window: {opened or 'default browser'}")
    print("  ctrl-c to close\n")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("closed")
    finally:
        server.server_close()
    return 0
