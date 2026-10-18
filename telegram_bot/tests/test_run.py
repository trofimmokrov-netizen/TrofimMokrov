"""Runner checks use temporary SQLite files and never contact Telegram."""
from __future__ import annotations

import contextlib
import fcntl
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from telegram_bot import run


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / "private" / "requests.sqlite3"

    def invoke(self, *arguments, owner="999", responses=None):
        stdout, stderr = io.StringIO(), io.StringIO()
        with patch("sys.argv", ["telegram_bot.run", "--db", str(self.db), *arguments]):
            with patch.dict("os.environ", {"TELEGRAM_BOT_TOKEN": "unit-test-token", "TELEGRAM_OWNER_CHAT_ID": owner}):
                with patch.object(run, "TelegramAPI") as factory:
                    api = factory.return_value
                    api.call.side_effect = responses if responses is not None else [
                        {"username": "TrofimAI_bot"}, {"url": ""},
                    ]
                    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                        code = run.main()
                    return code, api.call.call_args_list, stdout.getvalue(), stderr.getvalue(), factory

    def test_check_confirms_bot_and_webhook_without_mutating_telegram(self):
        code, calls, stdout, stderr, _ = self.invoke("--check")
        self.assertEqual(code, 0)
        self.assertEqual([call.args[0] for call in calls], ["getMe", "getWebhookInfo"])
        self.assertIn("подтверждено", stdout)
        self.assertEqual(stderr, "")

    def test_missing_owner_check_is_incomplete_but_does_not_send(self):
        code, calls, stdout, _, _ = self.invoke("--check", owner="")
        self.assertEqual(code, 2)
        self.assertEqual([call.args[0] for call in calls], ["getMe", "getWebhookInfo"])
        self.assertIn("оформление заявок отключено", stdout)

    def test_existing_webhook_is_preserved_and_worker_not_started(self):
        code, calls, _, stderr, _ = self.invoke("--check", responses=[
            {"username": "TrofimAI_bot"}, {"url": "https://existing.example.test/hook"},
        ])
        self.assertEqual(code, 1)
        self.assertEqual([call.args[0] for call in calls], ["getMe", "getWebhookInfo"])
        self.assertIn("уже установлен webhook", stderr)

    def test_unexpected_bot_identity_cannot_be_used(self):
        for identity in ({"username": "another_bot"}, {"username": 42}, None):
            with self.subTest(identity=identity):
                code, calls, _, stderr, _ = self.invoke("--check", responses=[identity])
                self.assertEqual(code, 1)
                self.assertEqual([call.args[0] for call in calls], ["getMe"])
                self.assertIn("другому боту", stderr)

    def test_status_is_local_and_needs_no_credentials(self):
        code, calls, stdout, stderr, factory = self.invoke("--status", owner="not-an-id")
        self.assertEqual(code, 0)
        self.assertEqual(calls, [])
        factory.assert_not_called()
        self.assertEqual(json.loads(stdout), {"requests": 0, "notifications": {}, "outbox": {}})
        self.assertEqual(stderr, "")

    def test_invalid_owner_fails_before_telegram_access(self):
        for owner in ("0", "not-an-id"):
            with self.subTest(owner=owner):
                code, calls, _, stderr, factory = self.invoke("--check", owner=owner)
                self.assertEqual(code, 1)
                self.assertEqual(calls, [])
                factory.assert_not_called()
                self.assertIn("TELEGRAM_OWNER_CHAT_ID", stderr)

    def test_database_cannot_be_created_inside_public_checkout(self):
        public_db = Path(run.__file__).resolve().parents[1] / "should-not-exist.sqlite3"
        self.assertFalse(public_db.exists())
        stderr = io.StringIO()
        with patch("sys.argv", ["telegram_bot.run", "--db", str(public_db), "--status"]):
            with contextlib.redirect_stderr(stderr), self.assertRaises(SystemExit) as caught:
                run.main()
        self.assertEqual(caught.exception.code, 2)
        self.assertFalse(public_db.exists())
        self.assertIn("вне каталога публичного сайта", stderr.getvalue())

    def test_second_worker_on_same_database_is_rejected(self):
        self.db.parent.mkdir(parents=True)
        with self.db.with_suffix(".sqlite3.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            stderr = io.StringIO()
            with patch("sys.argv", ["telegram_bot.run", "--db", str(self.db), "--status"]):
                with contextlib.redirect_stderr(stderr), self.assertRaises(SystemExit) as caught:
                    run.main()
            self.assertEqual(caught.exception.code, 1)
            self.assertIn("уже работает процесс", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
