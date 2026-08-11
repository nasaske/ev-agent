from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from ev_agent.distill import Digest
from ev_agent.render import Skipped, note, parse
from ev_agent.sources import Session
from ev_agent.store import Ledger, list_candidates, promote, slugify, write_candidate

REPLY = """TITLE: Pin the lockfile before deploying
CONTEXT: When a build fails with a missing module that is present in package.json.
LESSON: Run npm ci instead of npm install so the lockfile is authoritative.
EVIDENCE: The build failed with cannot find module zod until the lockfile was regenerated.
"""


def _digest(path: Path) -> Digest:
    session = Session(
        path=path,
        harness="claude",
        session_id="fixture0",
        cwd="",
        modified=datetime(2026, 8, 11, tzinfo=timezone.utc),
        size=1,
    )
    return Digest(
        session=session,
        text="",
        user_turns=4,
        errors=1,
        corrections=1,
        tools=("Bash",),
    )


class ParsesTheTemplate(unittest.TestCase):
    def test_all_fields_are_read(self):
        candidate = parse(REPLY)

        self.assertEqual("Pin the lockfile before deploying", candidate.title)
        self.assertIn("npm ci", candidate.lesson)
        self.assertIn("zod", candidate.evidence)

    def test_thinking_tags_are_stripped(self):
        candidate = parse(f"<think>hmm let me see</think>\n{REPLY}")

        self.assertEqual("Pin the lockfile before deploying", candidate.title)

    def test_skip_is_honoured(self):
        with self.assertRaises(Skipped):
            parse("SKIP")

    def test_reply_without_a_title_is_rejected(self):
        with self.assertRaises(Skipped):
            parse("CONTEXT: something\nLESSON: something else")

    def test_empty_reply_is_rejected(self):
        with self.assertRaises(Skipped):
            parse("   ")


class RendersTheNote(unittest.TestCase):
    def test_frontmatter_follows_the_vault_convention(self):
        body = note(parse(REPLY), _digest(Path("/tmp/x.jsonl")), redactions=3)

        self.assertTrue(body.startswith("---\n"))
        self.assertIn("brain: shared", body)
        self.assertIn("status: candidate", body)
        self.assertIn("source: ev-agent", body)

    def test_provenance_is_recorded(self):
        body = note(parse(REPLY), _digest(Path("/tmp/x.jsonl")), redactions=3)

        self.assertIn("3 redactions", body)
        self.assertIn("[[E.V Agent]]", body)


class Slugs(unittest.TestCase):
    def test_titles_become_filesystem_safe(self):
        self.assertEqual("pin-the-lockfile", slugify("Pin the lockfile"))
        self.assertEqual("acentos-e-simbolos", slugify("Acentos! e / símbolos"))

    def test_empty_title_still_produces_a_name(self):
        self.assertEqual("untitled", slugify("!!!"))


class InboxLifecycle(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.inbox = self.root / "_inbox"
        self.skills = self.root / "skills"

    def tearDown(self):
        self._tmp.cleanup()

    def test_candidates_never_overwrite_each_other(self):
        first = write_candidate(self.inbox, "same-name", "one")
        second = write_candidate(self.inbox, "same-name", "two")

        self.assertNotEqual(first, second)
        self.assertEqual(2, len(list_candidates(self.inbox)))

    def test_promote_moves_the_file_out_of_the_inbox(self):
        write_candidate(self.inbox, "lesson", "body")

        target = promote(self.inbox, self.skills, "lesson")

        self.assertTrue(target.exists())
        self.assertEqual([], list_candidates(self.inbox))

    def test_promote_refuses_to_clobber_an_existing_skill(self):
        self.skills.mkdir(parents=True)
        (self.skills / "lesson.md").write_text("already here", encoding="utf-8")
        write_candidate(self.inbox, "lesson", "body")

        with self.assertRaises(FileExistsError):
            promote(self.inbox, self.skills, "lesson")

    def test_promote_reports_a_missing_candidate(self):
        with self.assertRaises(FileNotFoundError):
            promote(self.inbox, self.skills, "nope")


class LedgerPersistence(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _session(self, size: int) -> Session:
        return Session(
            path=self.root / "s.jsonl",
            harness="claude",
            session_id="s",
            cwd="",
            modified=datetime(2026, 8, 11, tzinfo=timezone.utc),
            size=size,
        )

    def test_a_recorded_session_is_seen_again(self):
        ledger = Ledger.load(self.root)
        session = self._session(100)

        ledger.record(session, "written")
        ledger.save()

        self.assertTrue(Ledger.load(self.root).seen(session))

    def test_a_grown_transcript_is_reprocessed(self):
        ledger = Ledger.load(self.root)
        ledger.record(self._session(100), "written")

        self.assertFalse(ledger.seen(self._session(200)))


if __name__ == "__main__":
    unittest.main()
