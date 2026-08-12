from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from ev_agent import queue


class QueueBehaviour(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.cache = self.root / "cache"

    def tearDown(self):
        self._tmp.cleanup()

    def _transcript(self, name: str) -> Path:
        path = self.root / name
        path.write_text("{}", encoding="utf-8")
        return path

    def test_a_transcript_is_queued_once(self):
        target = self._transcript("a.jsonl")

        self.assertTrue(queue.enqueue(self.cache, target))
        self.assertFalse(queue.enqueue(self.cache, target))
        self.assertEqual(1, len(queue.pending(self.cache)))

    def test_order_is_preserved(self):
        first = self._transcript("a.jsonl")
        second = self._transcript("b.jsonl")

        queue.enqueue(self.cache, first)
        queue.enqueue(self.cache, second)

        self.assertEqual([first, second], [item.path for item in queue.pending(self.cache)])

    def test_an_empty_cache_has_nothing_pending(self):
        self.assertEqual([], queue.pending(self.cache))

    def test_corrupt_lines_are_skipped(self):
        queue.enqueue(self.cache, self._transcript("a.jsonl"))
        with (self.cache / "pending.jsonl").open("a", encoding="utf-8") as handle:
            handle.write("{broken\n")

        self.assertEqual(1, len(queue.pending(self.cache)))

    def test_clearing_empties_the_queue(self):
        queue.enqueue(self.cache, self._transcript("a.jsonl"))

        self.assertEqual(1, queue.clear(self.cache))
        self.assertEqual([], queue.pending(self.cache))


class DrainLock(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.cache = Path(self._tmp.name) / "cache"

    def tearDown(self):
        self._tmp.cleanup()

    def test_a_second_drain_is_refused(self):
        lock = queue.acquire_lock(self.cache)

        with self.assertRaises(queue.DrainBusy):
            queue.acquire_lock(self.cache)

        queue.release_lock(lock)

    def test_the_lock_can_be_taken_again_after_release(self):
        queue.release_lock(queue.acquire_lock(self.cache))

        lock = queue.acquire_lock(self.cache)

        self.assertTrue(lock.exists())
        queue.release_lock(lock)


if __name__ == "__main__":
    unittest.main()
