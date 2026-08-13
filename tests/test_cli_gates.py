from __future__ import annotations

import argparse
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

from ev_agent import cli
from ev_agent.config import Config
from ev_agent.sources import Session
from ev_agent.store import Ledger

PRAISED = [
    {"type": "user", "message": {"role": "user", "content": "arruma o certificado mtls"}},
    {
        "type": "assistant",
        "message": {
            "role": "assistant",
            "content": [
                {"type": "tool_use", "id": "a", "name": "Write", "input": {"file_path": "tls.py"}},
                {"type": "tool_use", "id": "b", "name": "Bash", "input": {"command": "openssl"}},
                {"type": "tool_use", "id": "c", "name": "Bash", "input": {"command": "pytest"}},
            ],
        },
    },
    {"type": "user", "message": {"role": "user", "content": "perfeito, funcionou"}},
]


class Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.config = replace(
            Config.load(),
            cache_dir=self.root / "cache",
            inbox_dir=self.root / "inbox",
            config_dir=self.root / "config",
        )

    def tearDown(self):
        self._tmp.cleanup()

    def _session(self, name: str = "s.jsonl") -> Session:
        path = self.root / name
        path.write_text("\n".join(json.dumps(line) for line in PRAISED), encoding="utf-8")
        return Session(
            path=path,
            harness="claude",
            session_id="fixture0",
            cwd="",
            modified=datetime.now(tz=timezone.utc),
            size=path.stat().st_size,
        )


class ADryRunLeavesNoTrace(Base):
    def test_a_rejected_session_is_not_recorded(self):
        config = replace(self.config, min_specificity=1.1, praised_min_specificity=1.1)
        ledger = Ledger.load(config.cache_dir)

        outcome, _ = cli._process(
            self._session(), config, None, None, ledger, dry_run=True, prompt="x"
        )

        self.assertEqual(cli.ROUTINE, outcome)
        self.assertEqual({}, ledger.entries)

    def test_the_same_session_is_recorded_when_the_run_is_real(self):
        config = replace(self.config, min_specificity=1.1, praised_min_specificity=1.1)
        ledger = Ledger.load(config.cache_dir)

        cli._process(self._session(), config, None, None, ledger, dry_run=False, prompt="x")

        self.assertEqual(1, len(ledger.entries))

    def test_a_dry_run_does_not_decide_for_the_real_run(self):
        config = replace(self.config, min_specificity=0.0, praised_min_specificity=0.0)
        session = self._session()
        ledger = Ledger.load(config.cache_dir)

        cli._process(session, config, None, None, ledger, dry_run=True, prompt="x")

        self.assertFalse(ledger.seen(session))


class ScanAgreesWithRun(Base):
    def _findings(self, specificity: float, praised: bool):
        digest = mock.Mock()
        digest.did_real_work = True
        digest.verdict.refused = False
        digest.verdict.accepted = praised
        return cli.Inspection(
            digest=digest,
            redactions=0,
            quarantined=False,
            reasons=(),
            clean_text="",
            specificity=specificity,
        )

    def test_a_praised_session_clears_at_the_lower_floor(self):
        finding = self._findings(0.45, praised=True)

        self.assertEqual(self.config.praised_min_specificity, cli._floor_for(self.config, finding))
        self.assertGreaterEqual(finding.specificity, cli._floor_for(self.config, finding))

    def test_an_unremarked_session_of_the_same_score_does_not(self):
        finding = self._findings(0.45, praised=False)

        self.assertLess(finding.specificity, cli._floor_for(self.config, finding))


class ForgettingIsDeliberate(Base):
    def _ledger_with(self, count: int) -> None:
        ledger = Ledger.load(self.config.cache_dir)
        for index in range(count):
            ledger.record(self._session(f"s{index}.jsonl"), cli.ROUTINE)
        ledger.save()

    def test_without_yes_it_only_reports(self):
        self._ledger_with(3)

        with redirect_stdout(io.StringIO()) as out:
            cli.cmd_forget(argparse.Namespace(yes=False), self.config)

        self.assertIn("3 decisions on record", out.getvalue())
        self.assertEqual(3, len(Ledger.load(self.config.cache_dir).entries))

    def test_with_yes_the_ledger_is_emptied(self):
        self._ledger_with(3)

        with redirect_stdout(io.StringIO()) as out:
            cli.cmd_forget(argparse.Namespace(yes=True), self.config)

        self.assertIn("Forgot 3", out.getvalue())
        self.assertEqual({}, Ledger.load(self.config.cache_dir).entries)

    def test_an_empty_ledger_says_so(self):
        with redirect_stdout(io.StringIO()) as out:
            cli.cmd_forget(argparse.Namespace(yes=True), self.config)

        self.assertIn("Nothing to forget", out.getvalue())


if __name__ == "__main__":
    unittest.main()
