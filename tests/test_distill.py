from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from ev_agent.distill import build
from ev_agent.sources import Session, read_turns

CLAUDE_LINES = [
    {"type": "user", "message": {"role": "user", "content": "por que o build quebrou?"}},
    {
        "type": "assistant",
        "message": {
            "role": "assistant",
            "content": [
                {"type": "thinking", "thinking": "a" * 5000, "signature": "x"},
                {"type": "text", "text": "Vou olhar o log."},
                {
                    "type": "tool_use",
                    "id": "t1",
                    "name": "Bash",
                    "input": {"command": "npm run build"},
                },
            ],
        },
    },
    {
        "type": "user",
        "message": {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": "t1",
                    "is_error": True,
                    "content": "error: cannot find module 'zod'",
                }
            ],
        },
    },
    {"type": "user", "message": {"role": "user", "content": "na verdade era o lockfile"}},
]

CODEX_LINES = [
    {"type": "session_meta", "payload": {"id": "abc", "cwd": "/tmp"}},
    {"type": "event_msg", "payload": {"type": "user_message", "message": "roda o deploy"}},
    {
        "type": "response_item",
        "payload": {"type": "function_call", "name": "shell", "arguments": "gcloud run deploy"},
    },
    {
        "type": "response_item",
        "payload": {"type": "function_call_output", "output": "ERROR: permission denied"},
    },
]


def _session(lines: list[dict], harness: str, root: Path) -> Session:
    path = root / f"{harness}-fixture.jsonl"
    path.write_text("\n".join(json.dumps(line) for line in lines), encoding="utf-8")
    return Session(
        path=path,
        harness=harness,
        session_id="fixture0",
        cwd="",
        modified=datetime(2026, 8, 11, tzinfo=timezone.utc),
        size=path.stat().st_size,
    )


class ReadsBothHarnesses(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_claude_thinking_blocks_are_dropped(self):
        session = _session(CLAUDE_LINES, "claude", self.root)

        turns = list(read_turns(session))

        self.assertFalse(any("a" * 100 in turn.text for turn in turns))

    def test_claude_errors_are_captured(self):
        session = _session(CLAUDE_LINES, "claude", self.root)

        errors = [turn for turn in read_turns(session) if turn.role == "error"]

        self.assertEqual(1, len(errors))
        self.assertIn("cannot find module", errors[0].text)

    def test_claude_tool_calls_keep_the_command(self):
        session = _session(CLAUDE_LINES, "claude", self.root)

        tools = [turn for turn in read_turns(session) if turn.role == "tool"]

        self.assertEqual(1, len(tools))
        self.assertIn("npm run build", tools[0].text)

    def test_codex_messages_and_failures_are_read(self):
        session = _session(CODEX_LINES, "codex", self.root)

        turns = list(read_turns(session))
        roles = [turn.role for turn in turns]

        self.assertIn("user", roles)
        self.assertIn("tool", roles)
        self.assertIn("error", roles)


class ScoresSignal(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_correction_and_error_are_counted(self):
        session = _session(CLAUDE_LINES, "claude", self.root)

        digest = build(session, max_chars=12_000)

        self.assertEqual(1, digest.errors)
        self.assertEqual(1, digest.corrections)
        self.assertTrue(digest.has_signal)

    def test_session_without_stumbles_has_no_signal(self):
        lines = [{"type": "user", "message": {"role": "user", "content": "oi"}}]
        session = _session(lines, "claude", self.root)

        digest = build(session, max_chars=12_000)

        self.assertFalse(digest.has_signal)

    def test_digest_respects_the_character_budget(self):
        lines = CLAUDE_LINES * 200
        session = _session(lines, "claude", self.root)

        digest = build(session, max_chars=2_000)

        self.assertLessEqual(len(digest.text), 2_000)

    def test_digest_keeps_the_failure_section(self):
        session = _session(CLAUDE_LINES, "claude", self.root)

        digest = build(session, max_chars=12_000)

        self.assertIn("What went wrong", digest.text)
        self.assertIn("cannot find module", digest.text)


if __name__ == "__main__":
    unittest.main()
