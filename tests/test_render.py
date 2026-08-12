from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from ev_agent.distill import Digest
from ev_agent.render import Skipped, note, parse
from ev_agent.signals import verdict_from
from ev_agent.sources import Session
from ev_agent.store import Ledger, list_candidates, promote, slugify, write_candidate

REPLY = """TITLE: Unload the local model between calls
WHEN: Running a local LLM on a laptop shared with browsers and editors.
PATTERN: Set keep_alive to zero so the runtime releases the weights instead of
holding them resident for five minutes after the last call.
CASE: qwen3:4b at 8192 context held 3.9 GB against 2.1 GB free, and every token
paged through zram until the context was cut to 4096.
WHY: Available memory returned from 2.1 GB to 4.5 GB once the run finished.
"""


def _digest(root: Path) -> Digest:
    session = Session(
        path=root / "fixture.jsonl",
        harness="claude",
        session_id="fixture0",
        cwd="",
        modified=datetime(2026, 8, 11, tzinfo=timezone.utc),
        size=1,
    )
    return Digest(
        session=session,
        text="",
        user_turns=6,
        errors=1,
        resolved=1,
        verdict=verdict_from(1, 0, 0),
        tools=("Bash", "Write"),
        edits=1,
        tool_calls=4,
    )


class ParsesTheTemplate(unittest.TestCase):
    def test_every_field_is_read(self):
        candidate = parse(REPLY)

        self.assertEqual("Unload the local model between calls", candidate.title)
        self.assertIn("keep_alive", candidate.pattern)
        self.assertIn("3.9 GB", candidate.case)
        self.assertIn("4.5 GB", candidate.why)

    def test_multi_line_fields_are_joined(self):
        self.assertIn("holding them resident", parse(REPLY).pattern)

    def test_thinking_tags_are_stripped(self):
        candidate = parse(f"<think>weighing options</think>\n{REPLY}")

        self.assertEqual("Unload the local model between calls", candidate.title)

    def test_leading_prose_before_the_template_is_tolerated(self):
        candidate = parse(f"Okay, the user wants a pattern. Here it is.\n\n{REPLY}")

        self.assertEqual("Unload the local model between calls", candidate.title)

    def test_skip_is_honoured(self):
        with self.assertRaises(Skipped):
            parse("SKIP")

    def test_skip_as_a_title_is_honoured(self):
        with self.assertRaises(Skipped):
            parse("TITLE: SKIP")

    def test_a_reply_without_a_title_is_rejected(self):
        with self.assertRaises(Skipped):
            parse("PATTERN: something\nCASE: something else")


class RendersTheNote(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_both_layers_are_present(self):
        body = note(parse(REPLY), _digest(self.root), redactions=2, specificity=0.61)

        self.assertIn("## Pattern", body)
        self.assertIn("## What happened", body)

    def test_frontmatter_records_the_verdict_and_specificity(self):
        body = note(parse(REPLY), _digest(self.root), redactions=2, specificity=0.61)

        self.assertIn("brain: shared", body)
        self.assertIn("outcome: praised", body)
        self.assertIn("specificity: 0.61", body)
        self.assertIn("status: candidate", body)

    def test_provenance_is_recorded(self):
        body = note(parse(REPLY), _digest(self.root), redactions=2, specificity=0.61)

        self.assertIn("2 redactions", body)
        self.assertIn("[[E.V Agent]]", body)


class Slugs(unittest.TestCase):
    def test_titles_become_filesystem_safe(self):
        self.assertEqual("unload-the-model", slugify("Unload the model"))
        self.assertEqual("acentos-e-simbolos", slugify("Acentos! e / símbolos"))

    def test_an_unusable_title_still_produces_a_name(self):
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
        first = write_candidate(self.inbox, "same", "one")
        second = write_candidate(self.inbox, "same", "two")

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
