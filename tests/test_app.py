from __future__ import annotations

import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from dataclasses import replace
from pathlib import Path

from ev_agent import app, focus
from ev_agent.config import Config

TOKEN = "test-token"


class Served(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.config = replace(
            Config.load(),
            cache_dir=self.root / "cache",
            inbox_dir=self.root / "inbox",
            config_dir=self.root / "config",
        )
        self.server = app.build_server(self.config, TOKEN, port=0)
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)
        self._tmp.cleanup()

    def _url(self, route: str, token: str = TOKEN) -> str:
        return f"http://{app.HOST}:{self.port}{route}?t={token}"

    def _get(self, route: str, token: str = TOKEN):
        with urllib.request.urlopen(self._url(route, token), timeout=5) as response:
            return response.status, response.read().decode("utf-8")

    def _post(self, route: str, payload: dict, token: str = TOKEN):
        request = urllib.request.Request(
            self._url(route, token),
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status, json.loads(response.read().decode("utf-8"))


class RefusesAnyoneWithoutTheToken(Served):
    def test_the_state_endpoint_needs_the_token(self):
        with self.assertRaises(urllib.error.HTTPError) as caught:
            self._get("/api/state", token="wrong")

        self.assertEqual(403, caught.exception.code)

    def test_saving_focus_needs_the_token(self):
        with self.assertRaises(urllib.error.HTTPError) as caught:
            self._post("/api/focus", {"chosen": ["data"]}, token="wrong")

        self.assertEqual(403, caught.exception.code)

    def test_an_unknown_route_is_a_404(self):
        with self.assertRaises(urllib.error.HTTPError) as caught:
            self._get("/api/secrets")

        self.assertEqual(404, caught.exception.code)


class ServesThePage(Served):
    def test_the_page_needs_no_token_but_carries_one(self):
        status, body = self._get("/", token="")

        self.assertEqual(200, status)
        self.assertIn(TOKEN, body)

    def test_the_page_ships_both_languages_so_switching_needs_no_reload(self):
        _, body = self._get("/", token="")

        self.assertIn("trabalhando", body)
        self.assertIn("working", body)
        self.assertIn("Só local", body)

    def test_the_page_pulls_nothing_from_the_network(self):
        _, body = self._get("/", token="")

        for offender in ("http://", "https://", "//cdn", "@import"):
            self.assertNotIn(offender, body.replace("http://127.0.0.1", ""))


class ReportsWhatTheAgentIsDoing(Served):
    def test_the_state_is_json_the_page_can_paint(self):
        status, body = self._get("/api/state")
        payload = json.loads(body)

        self.assertEqual(200, status)
        for key in ("phase", "running", "queued", "tally", "recent", "focus", "areas"):
            self.assertIn(key, payload)

    def test_every_built_in_area_is_offered_in_both_languages(self):
        _, body = self._get("/api/state")
        areas = json.loads(body)["areas"]

        self.assertEqual(len(focus.BUILTIN), len(areas))
        self.assertTrue(all(area["en"] and area["pt"] for area in areas))


class SavesWhatYouTick(Served):
    def test_a_choice_survives_on_disk(self):
        status, payload = self._post(
            "/api/focus", {"chosen": ["architecture"], "custom": ["Vinhos naturais"]}
        )

        self.assertEqual(200, status)
        self.assertFalse(payload["focus"]["everything"])
        stored = focus.load(self.config.config_dir)
        self.assertEqual(("architecture",), stored.focus.chosen)
        self.assertEqual(("Vinhos naturais",), stored.focus.custom)

    def test_unticking_everything_goes_back_to_keeping_everything(self):
        self._post("/api/focus", {"chosen": ["data"], "custom": []})
        _, payload = self._post("/api/focus", {"chosen": [], "custom": []})

        self.assertTrue(payload["focus"]["everything"])

    def test_the_note_language_is_stored(self):
        _, payload = self._post("/api/focus", {"chosen": [], "note_language": "pt-BR"})

        self.assertEqual("pt-BR", payload["note_language"])
        self.assertEqual("pt-BR", focus.load(self.config.config_dir).note_language)

    def test_a_junk_body_is_refused_rather_than_stored(self):
        request = urllib.request.Request(
            self._url("/api/focus"), data=b"{not json", method="POST",
            headers={"Content-Type": "application/json"},
        )
        with self.assertRaises(urllib.error.HTTPError) as caught:
            urllib.request.urlopen(request, timeout=5)

        self.assertEqual(400, caught.exception.code)


if __name__ == "__main__":
    unittest.main()
