from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from ev_agent import focus, i18n
from ev_agent.model import system_prompt


class Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()


class NothingChosenMeansEverything(Base):
    def test_a_fresh_install_keeps_every_kind_of_lesson(self):
        self.assertTrue(focus.load(self.root).focus.everything)

    def test_the_prompt_is_untouched_when_no_focus_is_set(self):
        self.assertNotIn("keeps notes on a few subjects", system_prompt())

    def test_choosing_one_area_stops_it_being_everything(self):
        self.assertFalse(focus.Focus(chosen=("architecture",)).everything)


class KeepsOnlyWhatItUnderstands(Base):
    def test_an_unknown_slug_is_dropped(self):
        picked = focus.Focus.of(["architecture", "astrologia"], [])

        self.assertEqual(("architecture",), picked.chosen)

    def test_a_slug_is_not_stored_twice(self):
        picked = focus.Focus.of(["data", "data"], [])

        self.assertEqual(("data",), picked.chosen)

    def test_free_text_survives_because_focus_is_not_only_for_programmers(self):
        picked = focus.Focus.of([], ["Vinhos naturais", "Direito tributário"])

        self.assertEqual(("Vinhos naturais", "Direito tributário"), picked.custom)

    def test_blank_free_text_is_discarded(self):
        self.assertEqual((), focus.Focus.of([], ["   ", ""]).custom)

    def test_a_flood_of_custom_areas_is_capped(self):
        picked = focus.Focus.of([], [f"area {n}" for n in range(50)])

        self.assertEqual(focus._MAX_CUSTOM, len(picked.custom))

    def test_a_junk_payload_does_not_raise(self):
        self.assertEqual((), focus.Focus.of("not a list", 7).chosen)


class RemembersAcrossRuns(Base):
    def test_what_was_saved_comes_back(self):
        wanted = focus.Preferences(
            focus=focus.Focus(chosen=("infra",), custom=("Fotografia",)),
            note_language="pt-BR",
        )
        focus.save(self.root, wanted)

        self.assertEqual(wanted, focus.load(self.root))

    def test_a_corrupt_file_falls_back_to_defaults(self):
        (self.root / "preferences.json").write_text("{ broken", encoding="utf-8")

        self.assertEqual(focus.Preferences(), focus.load(self.root))

    def test_a_file_that_is_not_an_object_falls_back_to_defaults(self):
        (self.root / "preferences.json").write_text("[1, 2]", encoding="utf-8")

        self.assertEqual(focus.Preferences(), focus.load(self.root))


class ShapesWhatTheModelIsAskedFor(Base):
    def test_the_chosen_subjects_reach_the_prompt(self):
        prompt = system_prompt(focus.Focus(chosen=("architecture",), custom=("Vinhos naturais",)))

        self.assertIn("how a system is structured", prompt)
        self.assertIn("Vinhos naturais", prompt)

    def test_an_off_topic_session_is_told_to_skip(self):
        prompt = system_prompt(focus.Focus(chosen=("data",)))

        self.assertIn("belongs to none of them, reply with exactly SKIP", prompt)

    def test_the_note_language_is_stated(self):
        self.assertIn("Write in Brazilian Portuguese.", system_prompt(language="Brazilian Portuguese"))

    def test_the_answer_template_survives_every_composition(self):
        prompt = system_prompt(focus.Focus(chosen=("process",)), "Brazilian Portuguese")

        for field in ("TITLE:", "WHEN:", "PATTERN:", "CASE:", "WHY:"):
            self.assertIn(field, prompt)


class SpeaksBothLanguages(Base):
    def test_portuguese_is_matched_from_any_spelling(self):
        for spelling in ("pt", "pt-BR", "PT-br", "pt_br"):
            self.assertEqual(focus.PT, i18n.normalise(spelling))

    def test_anything_unknown_falls_back_to_english(self):
        self.assertEqual(focus.EN, i18n.normalise("klingon"))

    def test_every_string_exists_in_both_languages(self):
        english, portuguese = i18n.table(focus.EN), i18n.table(focus.PT)

        self.assertEqual(set(english), set(portuguese))
        self.assertTrue(all(value for value in portuguese.values()))

    def test_the_two_tables_are_actually_different(self):
        english, portuguese = i18n.table(focus.EN), i18n.table(focus.PT)
        differing = [key for key in english if english[key] != portuguese[key]]

        self.assertGreater(len(differing), 10)

    def test_an_area_carries_a_label_in_each_language(self):
        area = focus.BUILTIN[0]

        self.assertEqual("Arquitetura", area.label(focus.PT))
        self.assertEqual("Architecture", area.label(focus.EN))


if __name__ == "__main__":
    unittest.main()
