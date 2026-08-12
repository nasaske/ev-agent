from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from ev_agent.distill import build
from ev_agent.sources import Session, read_turns


def _agent(*blocks: dict) -> dict:
    return {"type": "assistant", "message": {"role": "assistant", "content": list(blocks)}}


def _tool(identifier: str, name: str, **args: str) -> dict:
    return {"type": "tool_use", "id": identifier, "name": name, "input": dict(args)}


def _result(identifier: str, text: str, failed: bool = False) -> dict:
    return {
        "type": "user",
        "message": {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": identifier,
                    "is_error": failed,
                    "content": text,
                }
            ],
        },
    }


def _says(text: str) -> dict:
    return {"type": "user", "message": {"role": "user", "content": text}}


PRAISED = [
    _says("o build quebrou no deploy, resolve"),
    _agent({"type": "thinking", "thinking": "a" * 4000, "signature": "x"}),
    _agent(_tool("t1", "Bash", command="command -v pnpm")),
    _result("t1", "Exit code 1: command not found", failed=True),
    _agent(_tool("t2", "Bash", command="npm run build")),
    _result("t2", "error: cannot find module 'zod'", failed=True),
    _agent(_tool("t3", "Write", file_path="package.json")),
    _agent(_tool("t4", "Bash", command="npm run build")),
    _result("t4", "build succeeded"),
    _says("perfeito, funcionou"),
]

REWORKED = [
    _says("cria o endpoint"),
    _agent(_tool("t1", "Write", file_path="api.py")),
    _agent(_tool("t2", "Bash", command="pytest")),
    _agent(_tool("t3", "Bash", command="ruff check")),
    _says("na verdade era para ser em outro modulo"),
]


def _session(lines: list[dict], root: Path, name: str = "fixture") -> Session:
    path = root / f"{name}.jsonl"
    path.write_text("\n".join(json.dumps(line) for line in lines), encoding="utf-8")
    return Session(
        path=path,
        harness="claude",
        session_id="fixture0",
        cwd="",
        modified=datetime(2026, 8, 11, tzinfo=timezone.utc),
        size=path.stat().st_size,
    )


class Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()


class ReadsTheTranscript(Base):
    def test_thinking_blocks_never_reach_the_digest(self):
        digest = build(_session(PRAISED, self.root), max_chars=12_000)

        self.assertNotIn("a" * 100, digest.text)

    def test_errors_carry_the_command_that_caused_them(self):
        turns = list(read_turns(_session(PRAISED, self.root)))
        errors = [turn for turn in turns if turn.role == "error"]

        self.assertEqual(2, len(errors))
        self.assertIn("command -v pnpm", errors[0].command)
        self.assertIn("npm run build", errors[1].command)


class SeparatesNoiseFromFailure(Base):
    def test_probe_failures_are_not_counted(self):
        digest = build(_session(PRAISED, self.root), max_chars=12_000)

        self.assertEqual(1, digest.errors)

    def test_a_failure_followed_by_a_working_retry_is_marked_resolved(self):
        digest = build(_session(PRAISED, self.root), max_chars=12_000)

        self.assertEqual(1, digest.resolved)
        self.assertIn("Failures that were fixed", digest.text)

    def test_probe_noise_never_appears_in_the_text(self):
        digest = build(_session(PRAISED, self.root), max_chars=12_000)

        self.assertNotIn("command not found", digest.text)


class ScoresTheOutcome(Base):
    def test_praise_without_pushback_is_a_candidate(self):
        digest = build(_session(PRAISED, self.root), max_chars=12_000)

        self.assertEqual("praised", digest.verdict.label)
        self.assertTrue(digest.did_real_work)
        self.assertTrue(digest.has_signal)

    def test_a_correction_disqualifies_the_session(self):
        digest = build(_session(REWORKED, self.root, "rework"), max_chars=12_000)

        self.assertEqual("reworked", digest.verdict.label)
        self.assertTrue(digest.did_real_work)
        self.assertFalse(digest.has_signal)

    def test_edits_are_counted_as_real_work(self):
        digest = build(_session(PRAISED, self.root), max_chars=12_000)

        self.assertEqual(1, digest.edits)

    def test_a_chat_only_session_did_no_work(self):
        digest = build(_session([_says("oi"), _says("tudo bem?")], self.root, "chat"), 12_000)

        self.assertFalse(digest.did_real_work)

    def test_the_outcome_is_stated_in_the_digest_header(self):
        digest = build(_session(PRAISED, self.root), max_chars=12_000)

        self.assertIn("outcome: praised", digest.text)

    def test_the_budget_is_respected(self):
        digest = build(_session(PRAISED * 60, self.root, "big"), max_chars=2_000)

        self.assertLessEqual(len(digest.text), 2_000)


if __name__ == "__main__":
    unittest.main()
