from __future__ import annotations

import json
import unittest

from ev_agent import openrouter
from ev_agent.model import ModelUnavailable


class GuardsBeforeSending(unittest.TestCase):
    def test_a_missing_key_is_reported_first(self):
        client = openrouter.Client(model="google/gemini-2.5-flash", timeout=10, api_key="")

        with self.assertRaises(ModelUnavailable):
            client.ensure_ready()

    def test_a_free_model_needs_an_explicit_opt_in(self):
        client = openrouter.Client(model="x/y:free", timeout=10, api_key="sk-or-v1-x")

        with self.assertRaises(openrouter.RefusedByPolicy):
            client.ensure_ready()

    def test_the_opt_in_allows_a_free_model(self):
        client = openrouter.Client(
            model="x/y:free", timeout=10, api_key="sk-or-v1-x", allow_free=True
        )

        client.ensure_ready()

    def test_a_paid_model_needs_no_opt_in(self):
        client = openrouter.Client(model="x/y", timeout=10, api_key="sk-or-v1-x")

        client.ensure_ready()


class AlwaysDeniesDataCollection(unittest.TestCase):
    def test_the_request_body_carries_the_privacy_preference(self):
        captured = {}

        class FakeResponse:
            def read(self):
                return json.dumps({"choices": [{"message": {"content": "TITLE: x"}}]}).encode()

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

        def fake_urlopen(request, timeout=0):
            captured["body"] = json.loads(request.data.decode("utf-8"))
            captured["headers"] = request.headers
            return FakeResponse()

        client = openrouter.Client(
            model="x/y:free", timeout=10, api_key="sk-or-v1-x", allow_free=True
        )
        original = openrouter.urllib.request.urlopen
        openrouter.urllib.request.urlopen = fake_urlopen
        try:
            client.generate("system", "prompt")
        finally:
            openrouter.urllib.request.urlopen = original

        self.assertEqual({"data_collection": "allow"}, captured["body"]["provider"])
        self.assertEqual("x/y:free", captured["body"]["model"])

    def test_the_default_client_denies_data_collection(self):
        captured = self._send(openrouter.Client(model="x/y", timeout=10, api_key="k"))

        self.assertEqual({"data_collection": "deny"}, captured["provider"])

    def _send(self, client) -> dict:
        captured = {}

        class FakeResponse:
            def read(self):
                return json.dumps({"choices": [{"message": {"content": "TITLE: x"}}]}).encode()

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

        def fake_urlopen(request, timeout=0):
            captured.update(json.loads(request.data.decode("utf-8")))
            return FakeResponse()

        original = openrouter.urllib.request.urlopen
        openrouter.urllib.request.urlopen = fake_urlopen
        try:
            client.generate("system", "prompt")
        finally:
            openrouter.urllib.request.urlopen = original
        return captured


if __name__ == "__main__":
    unittest.main()
