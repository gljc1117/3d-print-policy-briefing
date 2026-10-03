"""Offline regression checks; all search, model and SMTP calls are mocked."""

import contextlib
import importlib
import io
import json
import os
from pathlib import Path
import smtplib
import sys
import tempfile
import types
import unittest
from unittest.mock import Mock, patch


MODULES = ("jiaoyuting", "fagaiwei", "caizhengtng")
SAMPLE = [{"title": "项目申报通知", "url": "https://example.org/notice"}]


class BriefingFailureTests(unittest.TestCase):
    @contextlib.contextmanager
    def isolated_briefing(self, name, items=None, generation_error=None):
        search = types.ModuleType("search_utils")
        search.apify_google_search = Mock(return_value=[{"title": "来源"}])
        search.summarize_with_claude = Mock(
            return_value=items, side_effect=generation_error
        )
        env = {
            "GMAIL_ADDRESS": "sender@example.org",
            "GMAIL_APP_PASSWORD": "test-only-password",
            "RECIPIENT_EMAIL": "recipient@example.org",
        }
        cwd = Path.cwd()
        previous_module = sys.modules.pop(name, None)
        try:
            with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, env), \
                    patch.dict(sys.modules, {"search_utils": search}):
                module = importlib.import_module(name)
                os.chdir(temp)
                path = Path("docs/data") / f"{name}.json"
                path.parent.mkdir(parents=True)
                old = json.dumps({"updated": "2026-09-01", "count": 1,
                                  "items": SAMPLE}).encode()
                path.write_bytes(old)
                with patch.object(module.smtplib, "SMTP_SSL") as smtp, \
                        contextlib.redirect_stdout(io.StringIO()) as logs:
                    yield module, path, old, smtp, logs
        finally:
            os.chdir(cwd)
            sys.modules.pop(name, None)
            if previous_module is not None:
                sys.modules[name] = previous_module

    def test_generation_failure_preserves_data_and_never_contacts_smtp(self):
        for name in MODULES:
            with self.subTest(briefing=name), self.isolated_briefing(
                name, generation_error=RuntimeError("credit balance is too low")
            ) as (module, path, old, smtp, logs):
                with self.assertRaises(SystemExit) as error:
                    module.main()
                self.assertEqual(error.exception.code, 1)
                self.assertEqual(path.read_bytes(), old)
                smtp.assert_not_called()
                self.assertNotIn("[INFO] 完成", logs.getvalue())

    def test_success_generates_data_and_sends_real_mime_message(self):
        for name in MODULES:
            with self.subTest(briefing=name), self.isolated_briefing(
                name, items=SAMPLE
            ) as (module, path, old, smtp, logs):
                module.main()
                payload = json.loads(path.read_text())
                self.assertEqual(payload, {"updated": module.TODAY,
                                           "count": 1, "items": SAMPLE})
                server = smtp.return_value.__enter__.return_value
                server.login.assert_called_once_with(
                    "sender@example.org", "test-only-password"
                )
                server.send_message.assert_called_once()
                message = server.send_message.call_args.args[0]
                self.assertEqual(message["To"], "recipient@example.org")
                html = message.get_payload()[0].get_payload(decode=True).decode()
                self.assertIn("项目申报通知", html)
                self.assertIn("https://example.org/notice", html)
                self.assertIn("[INFO] 完成", logs.getvalue())

    def test_valid_empty_result_remains_a_success(self):
        for name in MODULES:
            with self.subTest(briefing=name), self.isolated_briefing(
                name, items=[]
            ) as (module, path, old, smtp, logs):
                module.main()
                self.assertEqual(json.loads(path.read_text())["count"], 0)
                smtp.return_value.__enter__.return_value.send_message.assert_called_once()

    def test_smtp_failures_are_not_reported_as_success(self):
        failures = (
            smtplib.SMTPAuthenticationError(535, b"5.7.8 BadCredentials"),
            smtplib.SMTPServerDisconnected("Connection unexpectedly closed"),
        )
        for name in MODULES:
            for failure in failures:
                with self.subTest(briefing=name, failure=type(failure).__name__), \
                        self.isolated_briefing(name, items=SAMPLE) as state:
                    module, path, old, smtp, logs = state
                    server = smtp.return_value.__enter__.return_value
                    server.login.side_effect = failure
                    with self.assertRaises(SystemExit) as error:
                        module.main()
                    self.assertEqual(error.exception.code, 1)
                    server.send_message.assert_not_called()
                    self.assertNotIn("[INFO] 完成", logs.getvalue())


if __name__ == "__main__":
    unittest.main()
