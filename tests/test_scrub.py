from __future__ import annotations

import unittest

from ev_agent.scrub import scrub, verify

_MARKER = "-" * 5
_BODY = "MIIEowIBAAKCAQEA" + "x7Vn9dQ2mKp0LrTf" * 2
FAKE_PEM = f"{_MARKER}BEGIN RSA PRIVATE KEY{_MARKER}\n{_BODY}\n{_MARKER}END RSA PRIVATE KEY{_MARKER}"


class RedactsKnownSecretShapes(unittest.TestCase):
    def test_private_key_block_is_removed_whole(self):
        result = scrub(f"here is the key:\n{FAKE_PEM}\ndone")

        self.assertNotIn("MIIEowIBAAKCAQEA", result.text)
        self.assertIn("private-key", result.hits)
        self.assertTrue(result.safe)

    def test_certificate_block_is_removed(self):
        text = "-----BEGIN CERTIFICATE-----\nQUJDREVGR0hJSktMTU5PUFFS\n-----END CERTIFICATE-----"

        result = scrub(text)

        self.assertNotIn("QUJDREVGR0hJSktMTU5PUFFS", result.text)
        self.assertIn("certificate", result.hits)

    def test_assigned_secret_keeps_the_key_name_but_drops_the_value(self):
        result = scrub('client_secret = "kBfzsj9cGvH5CRA6xxxxxxxx"')

        self.assertNotIn("kBfzsj9cGvH5CRA6", result.text)
        self.assertIn("client_secret", result.text)
        self.assertTrue(result.safe)

    def test_bearer_header_is_removed(self):
        result = scrub("Authorization: Bearer abcdefghijklmnop1234567890")

        self.assertNotIn("abcdefghijklmnop", result.text)
        self.assertTrue(result.safe)

    def test_provider_tokens_are_removed(self):
        samples = (
            "ghp_" + "A" * 36,
            "sk-ant-" + "B" * 40,
            "sk-or-v1-" + "e" * 64,
            "AKIA" + "C" * 16,
            "AIza" + "D" * 35,
            "xoxb-" + "1" * 20,
        )

        for sample in samples:
            with self.subTest(sample=sample[:8]):
                result = scrub(f"token is {sample} ok")
                self.assertNotIn(sample, result.text)

    def test_credentials_inside_a_url_are_removed(self):
        result = scrub("psql postgres://admin:hunter2pass@db.internal:5432/app")

        self.assertNotIn("hunter2pass", result.text)
        self.assertTrue(result.safe)

    def test_brazilian_documents_are_removed(self):
        result = scrub("CNPJ 40.920.573/0001-58 e CPF 123.456.789-09")

        self.assertNotIn("40.920.573/0001-58", result.text)
        self.assertNotIn("123.456.789-09", result.text)

    def test_high_entropy_token_is_caught_even_without_a_matching_rule(self):
        result = scrub("the value ADAw0cZhMrWIds58bq6iD4pZUmJzpIc9 was pasted")

        self.assertNotIn("ADAw0cZhMrWIds58bq6iD4pZUmJzpIc9", result.text)
        self.assertTrue(result.safe)


class LeavesOrdinaryTextAlone(unittest.TestCase):
    def test_prose_survives_untouched(self):
        text = "The build failed because the migration ran before the schema existed."

        result = scrub(text)

        self.assertEqual(text, result.text)
        self.assertEqual((), result.hits)
        self.assertTrue(result.safe)

    def test_session_uuid_is_not_treated_as_a_secret(self):
        text = "session c74d6480-8b09-4130-9d5b-c03d5b6b50bf finished"

        result = scrub(text)

        self.assertIn("c74d6480-8b09-4130-9d5b-c03d5b6b50bf", result.text)

    def test_file_paths_and_commands_survive(self):
        text = "run `npm run deploy:cloud-run` from ~/projetos/smartauto"

        result = scrub(text)

        self.assertEqual(text, result.text)

    def test_long_file_paths_are_not_mistaken_for_secrets(self):
        text = "edit home/user/Documentos/Obsidian/smartautomations/src/main.py now"

        result = scrub(text)

        self.assertEqual(text, result.text)
        self.assertTrue(result.safe)

    def test_snake_case_identifiers_are_not_mistaken_for_secrets(self):
        text = "the flag observed_from_primary_session controls the runner"

        result = scrub(text)

        self.assertEqual(text, result.text)

    def test_kebab_case_names_are_not_mistaken_for_secrets(self):
        text = "bucket smart-caixa-teste-imoveis-gmail-state was created"

        result = scrub(text)

        self.assertEqual(text, result.text)

    def test_project_names_containing_digits_survive(self):
        text = "deployed to smart-458916-automations-state"

        result = scrub(text)

        self.assertEqual(text, result.text)

    def test_camel_case_function_names_survive(self):
        text = "call parseBitrixDialogEntityData then apiProcAppendSupabaseLog_"

        result = scrub(text)

        self.assertEqual(text, result.text)

    def test_git_sha_is_not_redacted(self):
        text = "reverted 650926168d68c7133f9d9fc0c0af0185e39a60f3 on main"

        result = scrub(text)

        self.assertEqual(text, result.text)

    def test_thirty_two_char_hex_is_still_treated_as_a_key(self):
        text = "token 0123456789abcdef0123456789abcdef here"

        result = scrub(text)

        self.assertNotIn("0123456789abcdef0123456789abcdef", result.text)


class FailsClosed(unittest.TestCase):
    def test_verify_reports_residue_on_raw_text(self):
        residue = verify(f"key: {'Z' * 40}")

        self.assertTrue(residue)

    def test_verify_is_clean_after_scrubbing(self):
        result = scrub(f"key: {'Z' * 40}\n{FAKE_PEM}")

        self.assertEqual([], verify(result.text))
        self.assertTrue(result.safe)

    def test_scrubbed_output_never_contains_the_original_secret(self):
        secret = "sk-proj-" + "9aZ" * 12
        result = scrub(f"OPENAI_API_KEY={secret}")

        self.assertNotIn(secret, result.text)
        self.assertTrue(result.safe)


if __name__ == "__main__":
    unittest.main()
