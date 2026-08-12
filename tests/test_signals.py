from __future__ import annotations

import unittest

from ev_agent.signals import (
    APPROVAL,
    CORRECTION,
    ErrorKind,
    classify_error,
    classify_user_message,
    verdict_from,
)


class TellsProbesFromFailures(unittest.TestCase):
    def test_command_v_probe_is_not_a_failure(self):
        kind = classify_error("Exit code 4 (ollama nao responde / nao instalado)", "Bash command -v ollama")

        self.assertIs(ErrorKind.PROBE, kind)

    def test_which_probe_is_not_a_failure(self):
        self.assertIs(ErrorKind.PROBE, classify_error("not found", "Bash which rsvg-convert"))

    def test_grep_with_no_match_is_not_a_failure(self):
        self.assertIs(ErrorKind.PROBE, classify_error("Exit code 1", "Bash grep -q needle file"))

    def test_a_real_build_failure_is_kept(self):
        kind = classify_error("error: cannot find module 'zod'", "Bash npm run build")

        self.assertIs(ErrorKind.REAL, kind)

    def test_a_traceback_is_kept(self):
        kind = classify_error("Traceback (most recent call last): KeyError: 'id'", "Bash python3 run.py")

        self.assertIs(ErrorKind.REAL, kind)

    def test_tool_rejection_is_a_user_signal_not_an_error(self):
        kind = classify_error(
            "The user doesn't want to proceed with this tool use. The tool use was rejected.",
            "AskUserQuestion",
        )

        self.assertIs(ErrorKind.USER_REJECTION, kind)


class ReadsHowTheUserResponded(unittest.TestCase):
    def test_explicit_praise_in_portuguese(self):
        for message in ("perfeito, era isso", "ficou bom demais", "funcionou!", "valeu"):
            with self.subTest(message=message):
                self.assertEqual(APPROVAL, classify_user_message(message))

    def test_explicit_praise_in_english(self):
        self.assertEqual(APPROVAL, classify_user_message("that works, thanks"))

    def test_terse_approval_only_counts_when_short(self):
        self.assertEqual(APPROVAL, classify_user_message("isso"))
        self.assertEqual(APPROVAL, classify_user_message("boa"))

    def test_the_same_word_inside_a_long_request_is_not_praise(self):
        message = "isso aqui precisa mudar porque o build ainda quebra quando roda no cloud run"

        self.assertEqual("", classify_user_message(message))

    def test_corrections_are_detected(self):
        for message in ("na verdade era o lockfile", "mentira, quero outro nome", "ta errado"):
            with self.subTest(message=message):
                self.assertEqual(CORRECTION, classify_user_message(message))

    def test_correction_wins_over_praise_when_both_appear(self):
        message = "ficou bom mas na verdade era para ser o outro arquivo"

        self.assertEqual(CORRECTION, classify_user_message(message))

    def test_a_plain_request_is_neither(self):
        self.assertEqual("", classify_user_message("cria um endpoint de health check"))


class Verdicts(unittest.TestCase):
    def test_praise_without_pushback_is_accepted(self):
        verdict = verdict_from(approvals=2, corrections=0, rejections=0)

        self.assertTrue(verdict.accepted)
        self.assertFalse(verdict.refused)
        self.assertEqual("praised", verdict.label)

    def test_any_correction_refuses_the_session(self):
        verdict = verdict_from(approvals=3, corrections=1, rejections=0)

        self.assertFalse(verdict.accepted)
        self.assertTrue(verdict.refused)
        self.assertEqual("reworked", verdict.label)

    def test_a_tool_rejection_also_refuses(self):
        self.assertTrue(verdict_from(0, 0, 1).refused)

    def test_silence_is_neither_accepted_nor_refused(self):
        verdict = verdict_from(0, 0, 0)

        self.assertFalse(verdict.accepted)
        self.assertFalse(verdict.refused)
        self.assertEqual("unremarked", verdict.label)


if __name__ == "__main__":
    unittest.main()
