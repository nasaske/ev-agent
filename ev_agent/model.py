from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass, replace

SYSTEM_PROMPT = """\
You write reusable engineering patterns from agent session logs.

The log you receive has already been filtered: the work in it succeeded and the
user did not ask for it to be redone. Your job is to name what worked so it can
be reused, not to review whether it was a good idea.

Rules:
- Use only what the log states. Never invent commands, versions or causes.
- PATTERN and CASE must not say the same thing twice. CASE names what happened
  here; PATTERN states the rule that would help someone facing a different
  instance of the same problem. Write PATTERN without the proper nouns from
  this session — no product name, no file name unique to this machine.

  The example below is about shipping rates. It is here to show the SHAPE of
  the two fields, nothing more. Never reuse its subject, its nouns, or its
  wording — your answer must be about the log you were given.

    CASE-shaped (wrong for this field): Raised the carrier timeout to 30s so
    the Correios quote stopped failing.
    RULE-shaped (right): When an upstream quote call fails intermittently
    under load, raise the client timeout to the upstream's published p99
    before adding retries — retries on a too-short timeout multiply the load
    that caused the failure.

- Keep the CASE concrete and specific to this log: real names, real numbers.
- Reply with exactly SKIP if the log shows only routine work — a small edit, a
  question answered, a command run — with nothing another engineer would need
  told to them. Most sessions are routine. Skipping is the common answer.
- Placeholders like [redacted:...] are removed secrets. Never speculate about
  their contents, and never reproduce them.
- Write in English. Keep the whole reply under 220 words.

Reply with exactly this template and nothing else:

TITLE: <one line, imperative, under 70 characters>
WHEN: <the situation that should trigger this pattern, one sentence>
PATTERN: <the reusable rule, 2-4 sentences>
CASE: <what concretely happened in this session, 2-3 sentences>
WHY: <the concrete result in the log that shows it worked — a command that
     succeeded, an error that stopped, a value that changed. Never cite the
     outcome line in the header; that is an input, not evidence.>
"""

_TEMPERATURE = 0.2
_DEFAULT_CONTEXT_WINDOW = 4096
_UNLOADED = "0"
_RESIDENT_DURING_RUN = "5m"


class ModelUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class Client:
    base_url: str
    model: str
    timeout: int
    context_window: int = _DEFAULT_CONTEXT_WINDOW
    keep_alive: str = _UNLOADED

    def resident(self) -> "Client":
        return replace(self, keep_alive=_RESIDENT_DURING_RUN)

    def unload(self) -> None:
        try:
            self._post("/api/generate", {"model": self.model, "keep_alive": _UNLOADED})
        except ModelUnavailable:
            return

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
                "keep_alive": self.keep_alive,
                "options": {"temperature": _TEMPERATURE, "num_ctx": self.context_window},
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
