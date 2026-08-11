from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass

SYSTEM_PROMPT = """\
You extract reusable engineering lessons from agent session logs.

You are not judging importance — a human reviews everything you write. Your
only job is to fill the template faithfully from the log you are given.

Rules:
- Use only what the log states. Never invent commands, versions or causes.
- If the log shows no durable lesson, reply with exactly: SKIP
- Placeholders like [redacted:...] are removed secrets. Never speculate about
  their contents, and never reproduce them.
- Be concrete. "Check the config" is useless; name the file and the setting.
- Write in English. Keep it under 200 words.

Reply with exactly this template and nothing else:

TITLE: <one line, imperative, under 70 characters>
CONTEXT: <when this situation comes up, one sentence>
LESSON: <what to do, 2-4 sentences>
EVIDENCE: <what in the log supports this, one sentence>
"""

_TEMPERATURE = 0.2
_CONTEXT_WINDOW = 8192
_KEEP_ALIVE = 0


class ModelUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class Client:
    base_url: str
    model: str
    timeout: int

    def available(self) -> bool:
        try:
            self._get("/api/tags")
            return True
        except ModelUnavailable:
            return False

    def installed_models(self) -> list[str]:
        payload = self._get("/api/tags")
        return [model.get("name", "") for model in payload.get("models", [])]

    def ensure_ready(self) -> None:
        if not self.available():
            raise ModelUnavailable(
                f"Ollama is not answering at {self.base_url}. Start it with `ollama serve`."
            )
        wanted = self.model.split(":")[0]
        if not any(name.split(":")[0] == wanted for name in self.installed_models()):
            raise ModelUnavailable(
                f"Model {self.model!r} is not installed. Run `ollama pull {self.model}`."
            )

    def generate(self, system: str, prompt: str) -> str:
        payload = self._post(
            "/api/generate",
            {
                "model": self.model,
                "system": system,
                "prompt": prompt,
                "stream": False,
                "keep_alive": _KEEP_ALIVE,
                "options": {"temperature": _TEMPERATURE, "num_ctx": _CONTEXT_WINDOW},
            },
        )
        return (payload.get("response") or "").strip()

    def _get(self, path: str) -> dict:
        return self._request(urllib.request.Request(self.base_url + path))

    def _post(self, path: str, body: dict) -> dict:
        request = urllib.request.Request(
            self.base_url + path,
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        return self._request(request)

    def _request(self, request: urllib.request.Request) -> dict:
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.URLError as exc:
            raise ModelUnavailable(f"{exc.reason}") from exc
        except (TimeoutError, json.JSONDecodeError) as exc:
            raise ModelUnavailable(str(exc)) from exc
