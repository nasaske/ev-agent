from __future__ import annotations

import unittest

from ev_agent.bench import Measurement, report
from ev_agent.render import Candidate, claim_of

LOG = """# Session claude:abcd1234
outcome: praised

## What the user asked for
- asked: o hook do git barrou meu commit

## What was actually done
- Bash npx block-no-verify
- Bash git commit
- Write settings.json
"""

GROUNDED = Candidate(
    title="Let the pre-commit hook run instead of bypassing it",
    when="A commit is barred by a local hook.",
    pattern="When a hook blocks a commit, fix what it flagged rather than passing a bypass flag.",
    case="The npx block-no-verify hook barred the git commit until settings.json was edited.",
    why="The commit succeeded after settings.json changed.",
)

INVENTED = Candidate(
    title="Raise the carrier timeout before adding retries",
    when="An upstream quote call fails intermittently under load.",
    pattern="Raise the client timeout to the upstream published p99 before adding retries.",
    case="The Correios carrier quote failed under load until the timeout reached 30 seconds.",
    why="The quote stopped failing.",
)


class BuildsTheClaimTheGateJudges(unittest.TestCase):
    def test_the_claim_is_what_happened_and_the_evidence_for_it(self):
        text = claim_of(GROUNDED)

        self.assertIn(GROUNDED.case, text)
        self.assertIn(GROUNDED.why, text)

    def test_the_generalised_pattern_is_never_judged(self):
        self.assertNotIn(GROUNDED.pattern, claim_of(GROUNDED))

    def test_the_title_is_not_part_of_the_claim(self):
        self.assertNotIn(GROUNDED.title, claim_of(GROUNDED))


class ScoresGroundingPerModel(unittest.TestCase):
    def test_a_grounded_candidate_scores_above_the_floor(self):
        measurement = Measurement("gemma3:4b", 116.0, GROUNDED, LOG)

        self.assertGreaterEqual(measurement.grounding, 0.40)
        self.assertEqual(measurement.outcome, "wrote")

    def test_an_invented_candidate_scores_below_the_floor(self):
        measurement = Measurement("qwen2.5:7b", 200.0, INVENTED, LOG)

        self.assertLess(measurement.grounding, 0.40)

    def test_a_skip_has_no_grounding_to_report(self):
        measurement = Measurement("qwen3:1.7b", 63.0, None, LOG)

        self.assertEqual(measurement.outcome, "skip")
        self.assertEqual(measurement.grounding, 0.0)


class ReportsWhatTheGateWouldDo(unittest.TestCase):
    def test_the_report_states_the_grounding_share(self):
        line = report(Measurement("gemma3:4b", 116.0, GROUNDED, LOG))

        self.assertIn("grounding", line)
        self.assertIn("gemma3:4b", line)

    def test_an_ungrounded_candidate_is_marked_as_rejected(self):
        line = report(Measurement("qwen2.5:7b", 200.0, INVENTED, LOG))

        self.assertIn("ungrounded", line)

    def test_a_grounded_candidate_is_not_marked_as_rejected(self):
        line = report(Measurement("gemma3:4b", 116.0, GROUNDED, LOG))

        self.assertNotIn("ungrounded", line)

    def test_an_error_still_reports(self):
        line = report(Measurement("phi4-mini", 1.0, None, LOG, error="connection refused"))

        self.assertIn("connection refused", line)


if __name__ == "__main__":
    unittest.main()
