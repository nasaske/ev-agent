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


class ReadsWordsRatherThanPunctuation(unittest.TestCase):
    def test_a_sentence_ending_period_is_not_part_of_the_term(self):
        terms = grounding.distinctive_terms("The hook barred the commit.")

        self.assertIn("commit", terms)
        self.assertNotIn("commit.", terms)

    def test_a_filename_keeps_its_extension(self):
        terms = grounding.distinctive_terms("Edited settings.json and src/main.py.")

        self.assertIn("settings.json", terms)
        self.assertIn("src/main.py", terms)

    def test_a_term_only_long_enough_with_its_punctuation_is_dropped(self):
        self.assertEqual([], grounding.distinctive_terms("Ran npm."))

    def test_a_trailing_period_no_longer_counts_as_invented(self):
        self.assertNotIn("barred.", grounding.check("The commit was barred.", LOG).missing)


PORTUGUESE_LOG = """# Session claude:0e85e5e2
outcome: unremarked

## What the user asked for
- asked: '/home/daviparma/Downloads/certificado_final.pem'

## What was actually done
- said: Os `.pem` têm só a cadeia de certificados, sem a chave privada — e mTLS
  exige a chave. Ela está nos arquivos PKCS#12.
- Bash openssl pkcs12 -in "$P12" -legacy
- said: O `.p12` abriu com `-legacy`.
"""


class JudgesIdentifiersRatherThanProse(unittest.TestCase):
    def test_an_english_note_about_a_portuguese_log_is_grounded(self):
        claim = (
            "The .pem chain carried no private key, so openssl pkcs12 with -legacy "
            "opened the PKCS#12 file for mTLS. The certificate then authenticated."
        )

        self.assertTrue(grounding.is_grounded(claim, PORTUGUESE_LOG))

    def test_identifiers_are_what_gets_checked(self):
        claim = (
            "The .pem chain carried no private key, so openssl pkcs12 with -legacy "
            "opened the PKCS#12 file for mTLS."
        )

        result = grounding.check(claim, PORTUGUESE_LOG)

        self.assertEqual("identifiers", result.basis)
        self.assertIn("pkcs12", result.checked)
        self.assertNotIn("carried", result.checked)

    def test_a_bare_command_name_is_prose_not_an_identifier(self):
        self.assertEqual([], grounding.identifiers("openssl and curl were run"))

    def test_a_flag_a_path_and_a_camel_case_symbol_are_identifiers(self):
        found = grounding.identifiers("Set --no-verify on src/main.py and read auxiliaryBar")

        self.assertIn("no-verify", found)
        self.assertIn("src/main.py", found)
        self.assertIn("auxiliarybar", found)

    def test_invented_identifiers_are_still_caught(self):
        claim = (
            "quote_service.py raised api_client.timeout to the upstream p99 so the "
            "Correios quote stopped failing. The retry_budget.yaml was left alone."
        )

        self.assertFalse(grounding.is_grounded(claim, PORTUGUESE_LOG))

    def test_a_note_naming_nothing_concrete_falls_back_to_its_words(self):
        claim = (
            "The engineer reported the extension was crashing and the workspace "
            "state was reset, which stopped the crash on the next launch."
        )

        result = grounding.check(claim, LOG)

        self.assertEqual("prose", result.basis)


class ReadsInflectionsAsTheSameWord(unittest.TestCase):
    def test_a_log_that_says_barrou_matches_a_note_that_says_barred(self):
        source = "The engineer removed the entry and the panel crashed."
        claim = "Removing the entry stopped the panel from crashing repeatedly."

        result = grounding.check(claim, source)

        self.assertIn("removing", result.found)
        self.assertIn("crashing", result.found)

    def test_stemming_does_not_admit_an_unrelated_word(self):
        result = grounding.check("The carrier quote failed.", "The commit was barred.")

        self.assertIn("carrier", result.missing)
        self.assertIn("quote", result.missing)


class TheFloorIsAdjustable(unittest.TestCase):
    def test_a_strict_floor_rejects_a_partly_grounded_claim(self):
        claim = "The git commit was barred while the Correios carrier quote timed out."

        self.assertFalse(grounding.is_grounded(claim, LOG, floor=0.95))

    def test_a_loose_floor_accepts_it(self):
        claim = "The git commit was barred while the Correios carrier quote timed out."

        self.assertTrue(grounding.is_grounded(claim, LOG, floor=0.1))


if __name__ == "__main__":
    unittest.main()
