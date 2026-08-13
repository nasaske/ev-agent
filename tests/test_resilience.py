from __future__ import annotations

import argparse
import json
import tempfile
import unittest
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

from ev_agent import cli, queue
from ev_agent.config import Config
from ev_agent.model import ModelUnavailable
from ev_agent.sources import Session

REPLY = """TITLE: Run pytest and ruff before the deploy
WHEN: A deploy is asked for right after an edit.
PATTERN: Run pytest and ruff before the deploy.
CASE: Write x.py, then Bash pytest and Bash ruff, then the deploy.
WHY: pytest and ruff both ran before the deploy.
"""


def _transcript(root: Path, name: str) -> Path:
    lines = [
        {"type": "user", "message": {"role": "user", "content": "resolve o deploy"}},
        {
            "type": "assistant",
            "message": {
                "role": "assistant",
                "content": [
                    {"type": "tool_use", "id": "a", "name": "Write", "input": {"file_path": "x.py"}},
                    {"type": "tool_use", "id": "b", "name": "Bash", "input": {"command": "pytest"}},
                    {"type": "tool_use", "id": "c", "name": "Bash", "input": {"command": "ruff"}},
                ],
            },
        },
        {"type": "user", "message": {"role": "user", "content": "perfeito, funcionou"}},
    ]
    path = root / name
    path.write_text("\n".join(json.dumps(line) for line in lines), encoding="utf-8")
    return path


class FlakyClient:
    def __init__(self, failures: int) -> None:
        self.remaining = failures
        self.calls = 0

    def resident(self):
        return self

    def unload(self) -> None:
        return

    def available(self) -> bool:
        return True

    def ensure_ready(self) -> None:
        return

    def generate(self, system: str, prompt: str) -> str:
        self.calls += 1
        if self.remaining > 0:
            self.remaining -= 1
            raise ModelUnavailable("timed out")
        return REPLY


class Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.config = replace(
            Config.load(),
            cache_dir=self.root / "cache",
            inbox_dir=self.root / "inbox",
            skills_dir=self.root / "skills",
            min_specificity=0.0,
            praised_min_specificity=0.0,
            settle_minutes=0,
        )
        self.args = argparse.Namespace(dry_run=False, limit=0)

    def tearDown(self):
        self._tmp.cleanup()

    def _sessions(self, count: int) -> list[Session]:
        made = []
        for index in range(count):
            path = _transcript(self.root, f"s{index}.jsonl")
            made.append(
                Session(
                    path=path,
                    harness="claude",
                    session_id=f"session{index}",
                    cwd="",
                    modified=datetime.now(tz=timezone.utc),
                    size=path.stat().st_size,
                )
            )
        return made


class OneFailureDoesNotSinkTheBatch(Base):
    def test_the_run_continues_after_a_timeout(self):
        client = FlakyClient(failures=1)
        sessions = self._sessions(3)

        with mock.patch.object(cli, "_backend", return_value=client), mock.patch.object(
            cli, "_vocabulary", return_value=None
        ):
            status = cli._run_over(sessions, self.config, self.args, "test")

        self.assertEqual(0, status)
        self.assertEqual(3, client.calls)
        self.assertEqual(2, len(list(self.config.inbox_dir.glob("*.md"))))

    def test_a_run_of_failures_stops_the_batch(self):
        client = FlakyClient(failures=99)
        sessions = self._sessions(6)

        with mock.patch.object(cli, "_backend", return_value=client), mock.patch.object(
            cli, "_vocabulary", return_value=None
        ):
            cli._run_over(sessions, self.config, self.args, "test")

        self.assertEqual(cli._CONSECUTIVE_FAILURE_LIMIT, client.calls)

    def test_failures_are_recorded_in_the_ledger(self):
        client = FlakyClient(failures=1)
        sessions = self._sessions(2)

        with mock.patch.object(cli, "_backend", return_value=client), mock.patch.object(
            cli, "_vocabulary", return_value=None
        ):
            cli._run_over(sessions, self.config, self.args, "test")

        from ev_agent.store import Ledger

        outcomes = {entry["outcome"] for entry in Ledger.load(self.config.cache_dir).entries.values()}
        self.assertIn(cli.FAILED, outcomes)
        self.assertIn(cli.WROTE, outcomes)


class DrainKeepsWhatItCouldNotFinish(Base):
    def test_failed_sessions_stay_queued(self):
        sessions = self._sessions(2)
        for session in sessions:
            queue.enqueue(self.config.cache_dir, session.path)
        client = FlakyClient(failures=1)

        with mock.patch.object(cli, "_backend", return_value=client), mock.patch.object(
            cli, "_vocabulary", return_value=None
        ):
            cli.cmd_drain(argparse.Namespace(dry_run=False, limit=0), self.config)

        still_queued = [item.path for item in queue.pending(self.config.cache_dir)]

        self.assertEqual(1, len(still_queued))
        self.assertEqual(sessions[0].path, still_queued[0])

    def test_a_clean_drain_empties_the_queue(self):
        for session in self._sessions(2):
            queue.enqueue(self.config.cache_dir, session.path)
        client = FlakyClient(failures=0)

        with mock.patch.object(cli, "_backend", return_value=client), mock.patch.object(
            cli, "_vocabulary", return_value=None
        ):
            cli.cmd_drain(argparse.Namespace(dry_run=False, limit=0), self.config)

        self.assertEqual([], queue.pending(self.config.cache_dir))

    def test_a_transcript_queued_while_the_drain_runs_is_not_lost(self):
        session = self._sessions(1)[0]
        queue.enqueue(self.config.cache_dir, session.path)
        latecomer = _transcript(self.root, "late.jsonl")
        cache = self.config.cache_dir

        class QueuesWhileWorking(FlakyClient):
            def generate(self, system: str, prompt: str) -> str:
                queue.enqueue(cache, latecomer)
                return super().generate(system, prompt)

        with mock.patch.object(
            cli, "_backend", return_value=QueuesWhileWorking(failures=0)
        ), mock.patch.object(cli, "_vocabulary", return_value=None):
            cli.cmd_drain(argparse.Namespace(dry_run=False, limit=0), self.config)

        self.assertEqual([latecomer], [item.path for item in queue.pending(cache)])

    def test_a_transcript_deleted_before_the_drain_stops_being_retried(self):
        session = self._sessions(1)[0]
        queue.enqueue(self.config.cache_dir, session.path)
        session.path.unlink()
        client = FlakyClient(failures=0)

        with mock.patch.object(cli, "_backend", return_value=client), mock.patch.object(
            cli, "_vocabulary", return_value=None
        ):
            cli.cmd_drain(argparse.Namespace(dry_run=False, limit=0), self.config)

        self.assertEqual([], queue.pending(self.config.cache_dir))


if __name__ == "__main__":
    unittest.main()
