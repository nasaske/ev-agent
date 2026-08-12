from __future__ import annotations

import re
import tempfile
import unittest
from pathlib import Path

from ev_agent import progress, watch

_ANSI = re.compile(r"\033\[[0-9;?]*[a-zA-Z]")


def _plain(text: str) -> list[str]:
    return [_ANSI.sub("", line) for line in text.splitlines()]


class ReportsWhatItIsDoing(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.cache = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_a_fresh_reporter_is_visible_immediately(self):
        progress.Reporter(self.cache, "ollama", "qwen3:4b", total=3)

        state = progress.read(self.cache)

        self.assertEqual(3, state.total)
        self.assertEqual("qwen3:4b", state.model)

    def test_stages_are_published_as_they_happen(self):
        reporter = progress.Reporter(self.cache, "ollama", "qwen3:4b", total=1)
        reporter.begin("claude:abcd1234")
        reporter.stage(progress.ASKING, 0.61)

        state = progress.read(self.cache)

        self.assertEqual("claude:abcd1234", state.current.session)
        self.assertEqual(progress.ASKING, state.current.stage)
        self.assertEqual(0.61, state.current.specificity)

    def test_finishing_tallies_and_clears_the_current_session(self):
        reporter = progress.Reporter(self.cache, "ollama", "qwen3:4b", total=2)
        reporter.begin("claude:abcd1234")
        reporter.finish("claude:abcd1234", "written", "note.md")

        state = progress.read(self.cache)

        self.assertEqual(1, state.done)
        self.assertEqual({"written": 1}, state.tally)
        self.assertEqual("", state.current.session)
        self.assertEqual("written", state.recent[0]["outcome"])

    def test_closing_marks_the_run_idle(self):
        reporter = progress.Reporter(self.cache, "ollama", "qwen3:4b", total=1)
        reporter.close()

        state = progress.read(self.cache)

        self.assertEqual(progress.IDLE, state.phase)
        self.assertFalse(state.running)

    def test_a_missing_state_file_reads_as_idle(self):
        state = progress.read(self.cache)

        self.assertEqual(progress.IDLE, state.phase)
        self.assertFalse(state.running)

    def test_a_corrupt_state_file_reads_as_idle(self):
        (self.cache / "state.json").write_text("{not json", encoding="utf-8")

        self.assertFalse(progress.read(self.cache).running)

    def test_a_dead_pid_is_not_reported_as_running(self):
        reporter = progress.Reporter(self.cache, "ollama", "qwen3:4b", total=1)
        payload = (self.cache / "state.json").read_text(encoding="utf-8")
        (self.cache / "state.json").write_text(payload.replace(f'"pid": {reporter.state.pid}', '"pid": 999999'), encoding="utf-8")

        self.assertFalse(progress.read(self.cache).running)


class RendersThePanel(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.cache = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_every_boxed_line_is_the_same_width(self):
        reporter = progress.Reporter(self.cache, "ollama", "qwen3:4b", total=4)
        reporter.begin("claude:abcd1234")
        reporter.stage(progress.ASKING, 0.61)
        reporter.finish("claude:abcd1234", "quarantined", "opaque:xxxx")

        boxed = [line for line in _plain(watch.snapshot(self.cache)) if line.startswith(("┌", "│", "└"))]

        self.assertGreater(len(boxed), 4)
        self.assertEqual(1, len({len(line) for line in boxed}))

    def test_the_idle_panel_still_renders(self):
        boxed = [line for line in _plain(watch.snapshot(self.cache)) if line.startswith(("┌", "│", "└"))]

        self.assertEqual(1, len({len(line) for line in boxed}))
        self.assertTrue(any("idle" in line for line in _plain(watch.snapshot(self.cache))))

    def test_only_the_current_stage_carries_the_filled_marker(self):
        rendered, _ = watch._stages(progress.SCRUBBING)
        plain = _ANSI.sub("", rendered)

        self.assertIn("● scrub", plain)
        self.assertEqual(1, plain.count("●"))
        self.assertIn("◦ read", plain)
        self.assertIn("◦ write", plain)

    def test_long_details_never_overflow_the_box(self):
        reporter = progress.Reporter(self.cache, "ollama", "qwen3:4b", total=1)
        reporter.finish("claude:abcd1234", "written", "x" * 400)

        boxed = [line for line in _plain(watch.snapshot(self.cache)) if line.startswith(("┌", "│", "└"))]

        self.assertEqual(1, len({len(line) for line in boxed}))


if __name__ == "__main__":
    unittest.main()
