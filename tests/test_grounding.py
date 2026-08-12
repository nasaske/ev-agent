from __future__ import annotations

import unittest

from ev_agent import grounding

LOG = """# Session claude:abcd1234
outcome: praised

## What the user asked for
- asked: o hook do git barrou meu commit

## What was actually done
- Bash npx block-no-verify
- Bash git commit
- Write settings.json

## How the user responded
- approved: perfeito
"""


class TellsRecallFromInvention(unittest.TestCase):
    def test_a_claim_built_from_the_log_is_grounded(self):
        claim = "The npx block-no-verify hook barred the git commit, so settings.json was edited."

        self.assertTrue(grounding.is_grounded(claim, LOG))

    def test_a_claim_about_a_different_subject_is_rejected(self):
        claim = (
            "Raised the carrier timeout so the Correios quote stopped failing under load. "
            "The upstream p99 became the new client timeout."
        )

        self.assertFalse(grounding.is_grounded(claim, LOG))

    def test_a_claim_copied_from_a_prompt_example_is_rejected(self):
        claim = (
            "The Codex extension crashed; entries in state.vscdb under workspaceStorage "
            "and globalStorage were removed to stop auxiliaryBar restoring."
        )

        self.assertFalse(grounding.is_grounded(claim, LOG))

    def test_the_missing_terms_are_reported(self):
        claim = "The Correios carrier quote failed under load."

        missing = grounding.check(claim, LOG).missing

        self.assertIn("correios", missing)
        self.assertIn("carrier", missing)


class DoesNotPunishBrevity(unittest.TestCase):
    def test_a_very_short_claim_is_not_judged(self):
        self.assertTrue(grounding.is_grounded("It worked.", LOG))

    def test_generic_words_are_never_counted(self):
        terms = grounding.distinctive_terms("This would ensure that the result changes")

        self.assertEqual([], terms)

    def test_repeated_terms_count_once(self):
        terms = grounding.distinctive_terms("commit commit commit settings.json")

        self.assertEqual(["commit", "settings.json"], terms)


class TheFloorIsAdjustable(unittest.TestCase):
    def test_a_strict_floor_rejects_a_partly_grounded_claim(self):
        claim = "The git commit was barred while the Correios carrier quote timed out."

        self.assertFalse(grounding.is_grounded(claim, LOG, floor=0.95))

    def test_a_loose_floor_accepts_it(self):
        claim = "The git commit was barred while the Correios carrier quote timed out."

        self.assertTrue(grounding.is_grounded(claim, LOG, floor=0.1))


if __name__ == "__main__":
    unittest.main()
