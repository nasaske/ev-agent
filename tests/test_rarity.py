from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from ev_agent import rarity

ROUTINE = [
    "npm run build failed then npm install fixed the dependency",
    "npm run build passed after npm install refreshed dependency versions",
    "npm install then npm run build, dependency resolved",
    "another npm install and npm run build dependency check",
]

UNUSUAL = "santander mtls certificate fingerprint akamai handshake cnpj registration"


class MeasuresSpecificity(unittest.TestCase):
    def test_common_vocabulary_scores_lower_than_unusual(self):
        vocabulary = rarity.build(ROUTINE + [UNUSUAL])

        routine = vocabulary.specificity(ROUTINE[0], common_ratio=0.5)
        unusual = vocabulary.specificity(UNUSUAL, common_ratio=0.5)

        self.assertLess(routine, unusual)
        self.assertLess(routine, 0.5)

    def test_unusual_vocabulary_scores_high(self):
        vocabulary = rarity.build(ROUTINE + [UNUSUAL])

        self.assertGreater(vocabulary.specificity(UNUSUAL, common_ratio=0.5), 0.8)

    def test_empty_text_scores_zero(self):
        self.assertEqual(0.0, rarity.build(ROUTINE).specificity(""))

    def test_stopwords_are_ignored(self):
        self.assertNotIn("that", rarity.terms_of("that thing with those files"))

    def test_redaction_placeholders_never_become_terms(self):
        terms = rarity.terms_of("token [redacted:high-entropy] here")

        self.assertFalse(any(term.startswith("[redacted") for term in terms))

    def test_short_tokens_are_ignored(self):
        self.assertNotIn("npm", rarity.terms_of("npm ci"))


class PersistsTheIndex(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_a_saved_index_round_trips(self):
        original = rarity.build(ROUTINE + [UNUSUAL])
        rarity.save(self.root, original)

        restored = rarity.load(self.root)

        self.assertIsNotNone(restored)
        self.assertEqual(original.documents, restored.documents)
        self.assertEqual(original.frequencies, restored.frequencies)

    def test_a_missing_index_loads_as_none(self):
        self.assertIsNone(rarity.load(self.root))

    def test_a_corrupt_index_loads_as_none(self):
        (self.root / "vocabulary.json").write_text("{not json", encoding="utf-8")

        self.assertIsNone(rarity.load(self.root))


if __name__ == "__main__":
    unittest.main()
