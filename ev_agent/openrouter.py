from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass

from .model import ModelUnavailable

_ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"
_REFERER = "https://github.com/nasaske/ev-agent"
_TITLE = "E.V Agent"
_TEMPERATURE = 0.2
_FREE_SUFFIX = ":free"


class RefusedByPolicy(RuntimeError):
    pass


@dataclass(frozen=True)
class Client:
    model: str
    timeout: int
    api_key: str
    allow_free: bool = False

    def resident(self) -> "Client":
        return self

    def unload(self) -> None:
        return

    def available(self) -> bool:
        return bool(self.api_key)

    def ensure_ready(self) -> None:
        if not self.api_key:
            raise ModelUnavailable(
                "OPENROUTER_API_KEY is not set. Export it, or use EV_BACKEND=ollama."
            )
        if self.model.endswith(_FREE_SUFFIX) and not self.allow_free:
            raise RefusedByPolicy(
                f"{self.model!r} is a free-tier endpoint. OpenRouter files these under "
                '"Free model training": routing to them requires allowing prompt '
                "collection, which is the thing this tool exists to avoid. "
                "EV_ALLOW_FREE=1 proceeds and sends data_collection=allow — your "
                "scrubbed digests then become training data."
            )

    def generate(self, system: str, prompt: str) -> str:
        body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "temperature": _TEMPERATURE,
            "provider": {"data_collection": "allow" if self.allow_free else "deny"},
        }
        request = urllib.request.Request(
            _ENDPOINT,
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
                "HTTP-Referer": _REFERER,
                "X-Title": _TITLE,
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise ModelUnavailable(f"HTTP {exc.code}: {exc.read()[:200].decode('utf-8', 'replace')}") from exc
        except urllib.error.URLError as exc:
            raise ModelUnavailable(str(exc.reason)) from exc
        except (TimeoutError, json.JSONDecodeError) as exc:
            raise ModelUnavailable(str(exc)) from exc

        choices = payload.get("choices") or []
        if not choices:
            raise ModelUnavailable(f"empty response: {str(payload)[:200]}")
        return (choices[0].get("message", {}).get("content") or "").strip()


def api_key_from_env() -> str:
    return os.environ.get("OPENROUTER_API_KEY", "").strip()
