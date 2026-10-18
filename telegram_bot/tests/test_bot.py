"""Offline checks for consent, durable intake, and conservative delivery."""
from __future__ import annotations

import io
import http.client
import json
import tempfile
import traceback
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from telegram_bot.bot import Bot, DeliveryUnknown, Store, TelegramAPI, TelegramRejected


class FakeAPI:
    def __init__(self, *outcomes):
        self.outcomes = list(outcomes)
        self.calls = []

    def call(self, method, **payload):
        self.calls.append((method, payload))
        outcome = self.outcomes.pop(0) if self.outcomes else {"message_id": len(self.calls)}
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


class BotWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        content = self.directory / "content"
        content.mkdir()
        (content / "site.json").write_text(json.dumps({
            "base_url": "https://example.test", "telegram": "https://t.me/example",
            "email": "owner@example.test",
        }))
        (content / "services.json").write_text(json.dumps([
            {"id": "websites", "name": "Сайты с помощью AI", "price": "от 10 000 ₽"},
            {"id": "automation", "name": "Автоматизация", "price": "от 10 000 ₽"},
        ], ensure_ascii=False))
        self.content = content
        self.db_path = self.directory / "private" / "requests.sqlite3"
        self.store = Store(self.db_path)
        self.addCleanup(lambda: self.store.close())
        self.now = 1_800_000_000
        self.bot = Bot(self.store, 999, content=content, clock=lambda: self.now)
        self.update_id = 0

    def message(self, text=None, *, chat=101, contact=None, chat_type="private", user=None, update_id=None):
        if update_id is None:
            self.update_id += 1
            update_id = self.update_id
        message = {
            "chat": {"id": chat, "type": chat_type},
            "from": user if user is not None else {"id": chat, "username": "visitor", "is_bot": False},
        }
        if text is not None:
            message["text"] = text
        if contact is not None:
            message["contact"] = contact
        update = {"update_id": update_id, "message": message}
        self.bot.process(update)
        return update

    def reach_confirmation(self, *, chat=101, service="websites", contact="visitor@example.test"):
        self.message("/start service_" + service, chat=chat)
        self.message("Нужен сайт для небольшой компании", chat=chat)
        self.message(contact, chat=chat)

    def rows(self, table):
        return self.store.db.execute("SELECT * FROM " + table + " ORDER BY rowid").fetchall()

    def payloads(self):
        return [json.loads(row["payload"]) for row in self.rows("outbox")]

    def test_service_deep_link_requires_explicit_confirmation_then_notifies_owner(self):
        self.reach_confirmation()
        self.assertEqual(self.rows("requests"), [])
        self.assertEqual(self.store.session(101, self.now)[0], "confirm")
        self.assertTrue(all(payload["chat_id"] == 101 for payload in self.payloads()))
        self.message("Отправить заявку")
        requests = self.rows("requests")
        self.assertEqual(len(requests), 1)
        self.assertEqual(requests[0]["service_id"], "websites")
        self.assertEqual(requests[0]["source"], "service_websites")
        self.assertEqual(requests[0]["contact"], "visitor@example.test")
        owner_messages = [row for row in self.rows("outbox") if row["chat_id"] == 999]
        self.assertEqual(len(owner_messages), 1)
        self.assertEqual(owner_messages[0]["request_id"], requests[0]["id"])
        self.assertIn("Новая заявка №1", json.loads(owner_messages[0]["payload"])["text"])
        self.assertEqual(self.store.session(101, self.now), ("", {}))

    def test_unrecognised_confirmation_and_cancel_never_create_request(self):
        self.reach_confirmation()
        self.message("да")
        self.assertEqual(self.store.session(101, self.now)[0], "confirm")
        self.assertEqual(self.rows("requests"), [])
        self.message("Отмена")
        self.message("Отправить заявку")
        self.assertEqual(self.rows("requests"), [])
        self.assertTrue(all(payload["chat_id"] != 999 for payload in self.payloads()))

    def test_same_confirmation_update_is_processed_once(self):
        self.reach_confirmation()
        update = self.message("Отправить заявку")
        counts = self.store.counts()
        self.bot.process(update)
        self.assertEqual(self.store.counts(), counts)
        self.assertEqual(len(self.rows("requests")), 1)
        self.assertEqual(self.store.offset, update["update_id"] + 1)

    def test_failure_before_commit_rolls_back_request_notification_and_update(self):
        self.reach_confirmation()
        offset = self.store.offset
        queued = len(self.rows("outbox"))
        update = {"update_id": 100, "message": {
            "chat": {"id": 101, "type": "private"}, "from": {"id": 101},
            "text": "Отправить заявку",
        }}
        with patch.object(self.bot, "reply", side_effect=RuntimeError("simulated failure")):
            with self.assertRaises(RuntimeError):
                self.bot.process(update)
        self.assertEqual(self.store.offset, offset)
        self.assertEqual(self.rows("requests"), [])
        self.assertEqual(len(self.rows("outbox")), queued)
        self.assertEqual(self.store.session(101, self.now)[0], "confirm")
        self.bot.process(update)
        self.assertEqual(len(self.rows("requests")), 1)
        self.assertEqual(self.store.offset, 101)

    def test_restart_preserves_session_offset_and_deduplication(self):
        self.message("/start service_websites")
        details_update = self.message("Нужно сделать современный сайт")
        offset = self.store.offset
        self.store.close()
        self.store = Store(self.db_path)
        self.bot = Bot(self.store, 999, content=self.content, clock=lambda: self.now)
        self.assertEqual(self.store.offset, offset)
        self.assertEqual(self.store.session(101, self.now)[0], "contact")
        count = len(self.rows("outbox"))
        self.bot.process(details_update)
        self.assertEqual(len(self.rows("outbox")), count)
        self.message("visitor@example.test")
        self.message("Отправить заявку")
        self.assertEqual(len(self.rows("requests")), 1)

    def test_only_real_sender_in_own_private_chat_can_use_workflow(self):
        for chat_type, user in [
            ("group", {"id": 101}), ("supergroup", {"id": 101}),
            ("channel", {"id": 101}), ("private", {"id": 202}),
            ("private", {"id": 101, "is_bot": True}),
        ]:
            with self.subTest(chat_type=chat_type, user=user):
                self.message("/start service_websites", chat_type=chat_type, user=user)
        self.assertEqual(self.rows("sessions"), [])
        self.assertEqual(self.rows("outbox"), [])
        self.assertEqual(self.rows("requests"), [])
        self.assertEqual(self.store.offset, self.update_id + 1)

    def test_malformed_update_fields_are_acknowledged_without_replies(self):
        malformed_messages = [None, [], "bad", {"chat": []}, {"chat": "bad"},
                              {"chat": {"id": 101, "type": "private"}, "from": []}]
        for identifier, message in enumerate(malformed_messages, start=100):
            with self.subTest(message=message):
                self.bot.process({"update_id": identifier, "message": message})
                self.assertEqual(self.store.offset, identifier + 1)
        self.assertEqual(self.rows("requests"), [])
        self.assertEqual(self.rows("outbox"), [])

    def test_non_string_username_cannot_break_confirming_request(self):
        self.reach_confirmation()
        self.message("Отправить заявку", user={"id": 101, "username": {"bad": "value"}})
        self.assertEqual(len(self.rows("requests")), 1)
        self.assertEqual(self.rows("requests")[0]["username"], "")

    def test_shared_contact_must_belong_to_sender(self):
        self.message("/start service_websites")
        self.message("Нужно сделать современный сайт")
        self.message(contact={"user_id": 202, "phone_number": "+79990000000"})
        self.assertEqual(self.store.session(101, self.now)[0], "contact")
        self.message(contact={"user_id": 101, "phone_number": "+79990000001"})
        state, data = self.store.session(101, self.now)
        self.assertEqual(state, "confirm")
        self.assertEqual(data["contact"], "+79990000001")
        self.assertEqual(self.rows("requests"), [])

    def test_missing_owner_disables_intake_but_leaves_menu_usable(self):
        self.bot.owner = None
        for text in ("/request", "/start site", "/start service_websites"):
            self.message(text)
        self.assertEqual(self.rows("sessions"), [])
        self.assertEqual(self.rows("requests"), [])
        self.message("Сайт")
        self.assertIn("https://example.test/", self.payloads()[-1]["text"])

    def test_owner_disappearing_before_confirmation_does_not_create_request(self):
        self.reach_confirmation()
        self.bot.owner = None
        self.message("Отправить заявку")
        self.assertEqual(self.rows("requests"), [])
        self.assertEqual(self.store.session(101, self.now), ("", {}))

    def test_simultaneous_chats_have_independent_drafts(self):
        self.message("/start service_websites", chat=101)
        self.message("/start service_automation", chat=202)
        self.message("Нужен сайт для небольшой компании", chat=101)
        self.message("Нужен сценарий обработки заявок", chat=202)
        self.message("first@example.test", chat=101)
        self.message("second@example.test", chat=202)
        self.message("Отмена", chat=101)
        self.message("Отправить заявку", chat=202)
        requests = self.rows("requests")
        self.assertEqual(len(requests), 1)
        self.assertEqual(requests[0]["chat_id"], 202)
        self.assertEqual(requests[0]["service_id"], "automation")
        self.assertEqual(requests[0]["contact"], "second@example.test")

    def test_daily_limit_is_per_chat_and_expires(self):
        for _ in range(4):
            self.reach_confirmation()
            self.message("Отправить заявку")
        self.assertEqual(len(self.rows("requests")), 3)
        self.assertIn("три заявки", self.payloads()[-1]["text"])
        self.reach_confirmation(chat=202)
        self.message("Отправить заявку", chat=202)
        self.assertEqual(len(self.rows("requests")), 4)
        self.now += 86401
        self.reach_confirmation()
        self.message("Отправить заявку")
        self.assertEqual(len(self.rows("requests")), 5)

    def test_invalid_fields_and_expired_drafts_cannot_skip_consent(self):
        self.message("/start service_websites")
        for details in ("short", "x" * 1501):
            self.message(details)
            self.assertEqual(self.store.session(101, self.now)[0], "details")
        self.message("Нужен сайт для небольшой компании")
        for contact in ("abc", "person\n@example.test", "-----"):
            self.message(contact)
            self.assertEqual(self.store.session(101, self.now)[0], "contact")
        self.message("visitor@example.test")
        self.now += 86401
        self.message("Отправить заявку")
        self.assertEqual(self.rows("requests"), [])


class DeliveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "requests.sqlite3"
        self.store = Store(self.path)
        self.addCleanup(lambda: self.store.close())
        with self.store.transaction():
            cursor = self.store.db.execute(
                "INSERT INTO requests (update_id,created,chat_id,username,service_id,details,contact,source) "
                "VALUES (1,1000,101,'visitor','websites','task details','contact','site')"
            )
            self.request_id = cursor.lastrowid
            self.store.enqueue(999, "Owner notification", request_id=self.request_id)

    def state(self):
        return self.store.db.execute("SELECT * FROM outbox WHERE request_id=?", (self.request_id,)).fetchone()

    def notification(self):
        return self.store.db.execute("SELECT notification_status FROM requests WHERE id=?", (self.request_id,)).fetchone()[0]

    def test_success_marks_queue_and_notification_sent_only_once(self):
        api = FakeAPI()
        self.store.flush(api, now=1000)
        self.store.flush(api, now=1001)
        self.assertEqual(self.state()["state"], "sent")
        self.assertEqual(self.state()["attempts"], 1)
        self.assertEqual(self.notification(), "sent")
        self.assertEqual(api.calls, [("sendMessage", {"chat_id": 999, "text": "Owner notification", "link_preview_options": {"is_disabled": True}})])

    def test_rate_limit_respects_delay_and_stops_other_sends(self):
        with self.store.transaction():
            self.store.enqueue(101, "Receipt")
        api = FakeAPI(TelegramRejected(429, 45))
        self.store.flush(api, now=1000)
        self.assertEqual(self.state()["state"], "pending")
        self.assertEqual(self.state()["available"], 1045)
        self.assertEqual(self.notification(), "pending")
        self.assertEqual(len(api.calls), 1)
        # The cooldown applies to all chats and survives a worker restart.
        self.store.close()
        self.store = Store(self.path)
        self.store.flush(api, now=1044)
        self.assertEqual(len(api.calls), 1)
        self.store.flush(api, now=1045)
        self.assertEqual(len(api.calls), 3)
        self.assertEqual(self.state()["state"], "sent")
        self.assertEqual(self.state()["attempts"], 2)

    def test_explicit_server_rejection_retries_at_most_five_times(self):
        api = FakeAPI(*(TelegramRejected(503) for _ in range(5)))
        now = 1000
        for attempt in range(1, 6):
            self.store.flush(api, now=now)
            self.assertEqual(len(api.calls), attempt)
            self.assertEqual(self.state()["attempts"], attempt)
            if attempt < 5:
                self.assertEqual(self.state()["state"], "pending")
                available = self.state()["available"]
                self.assertGreater(available, now)
                self.store.flush(api, now=available - 1)
                self.assertEqual(len(api.calls), attempt)
                now = available
        self.assertEqual(self.state()["state"], "failed")
        self.assertEqual(self.notification(), "failed")
        self.store.flush(api, now=now + 10000)
        self.assertEqual(len(api.calls), 5)

    def test_forbidden_delivery_is_failed_and_is_not_retried(self):
        with self.store.transaction():
            self.store.enqueue(101, "Receipt")
        api = FakeAPI(TelegramRejected(403))
        self.store.flush(api, now=1000)
        self.store.flush(api, now=2000)
        self.assertEqual(self.state()["state"], "failed")
        self.assertEqual(self.notification(), "failed")
        self.assertEqual(len(api.calls), 2)  # The other chat's receipt still gets sent.

    def test_uncertain_delivery_is_not_automatically_repeated(self):
        api = FakeAPI(DeliveryUnknown("Simulated lost acknowledgement"))
        self.store.flush(api, now=1000)
        self.store.flush(api, now=2000)
        self.assertEqual(self.state()["state"], "unknown")
        self.assertEqual(self.notification(), "unknown")
        self.assertEqual(len(api.calls), 1)

    def test_crash_during_send_recovers_as_unknown_after_restart(self):
        api = FakeAPI(KeyboardInterrupt())
        with self.assertRaises(KeyboardInterrupt):
            self.store.flush(api, now=1000)
        self.assertEqual(self.state()["state"], "sending")
        self.store.close()
        self.store = Store(self.path)
        self.store.recover()
        self.assertEqual(self.state()["state"], "unknown")
        self.assertEqual(self.notification(), "unknown")
        self.store.flush(api, now=2000)
        self.assertEqual(len(api.calls), 1)


class TelegramAPITests(unittest.TestCase):
    TOKEN = "unit-test-token"

    def setUp(self):
        self.api = TelegramAPI(self.TOKEN)

    def assert_safe_exception(self, exception):
        rendered = "".join(traceback.format_exception(exception))
        self.assertNotIn(self.TOKEN, rendered)
        self.assertNotIn("private-message", rendered)

    def test_response_success_and_payload_encoding(self):
        with patch("telegram_bot.bot.urlopen") as transport:
            transport.return_value.__enter__.return_value.read.return_value = b'{"ok":true,"result":{"id":123}}'
            self.assertEqual(self.api.call("sendMessage", chat_id=101, text="Привет"), {"id": 123})
            request = transport.call_args.args[0]
            self.assertEqual(json.loads(request.data), {"chat_id": 101, "text": "Привет"})
            self.assertEqual(transport.call_args.kwargs["timeout"], 45)

    def test_http_rejection_is_sanitized_and_keeps_retry_delay(self):
        body = json.dumps({"ok": False, "error_code": 429, "description": self.TOKEN + " private-message", "parameters": {"retry_after": 17}}).encode()
        error = HTTPError("https://example.test/" + self.TOKEN, 429, "private-message", {}, io.BytesIO(body))
        with patch("telegram_bot.bot.urlopen", side_effect=error):
            with self.assertRaises(TelegramRejected) as caught:
                self.api.call("sendMessage", text="private-message")
        self.assertEqual(caught.exception.code, 429)
        self.assertEqual(caught.exception.retry_after, 17)
        self.assert_safe_exception(caught.exception)

    def test_network_and_invalid_response_errors_never_expose_token(self):
        for error in (URLError(self.TOKEN + " private-message"), OSError(self.TOKEN + " private-message"),
                      http.client.HTTPException(self.TOKEN + " private-message")):
            with self.subTest(error=type(error).__name__):
                with patch("telegram_bot.bot.urlopen", side_effect=error):
                    with self.assertRaises(DeliveryUnknown) as caught:
                        self.api.call("getMe")
                self.assert_safe_exception(caught.exception)
        for body in (b"invalid-json", b"[]", b'{"ok":false}', b'{"ok":true}'):
            with self.subTest(body=body):
                with patch("telegram_bot.bot.urlopen") as transport:
                    transport.return_value.__enter__.return_value.read.return_value = body
                    with self.assertRaises(DeliveryUnknown) as caught:
                        self.api.call("getMe")
                self.assert_safe_exception(caught.exception)

    def test_malformed_http_error_is_unknown_and_sanitized(self):
        error = HTTPError("https://example.test/" + self.TOKEN, 502, self.TOKEN, {}, io.BytesIO(b"invalid-json"))
        with patch("telegram_bot.bot.urlopen", side_effect=error):
            with self.assertRaises(DeliveryUnknown) as caught:
                self.api.call("getMe")
        self.assert_safe_exception(caught.exception)

    def test_url_construction_error_is_sanitized(self):
        with patch("telegram_bot.bot.Request", side_effect=ValueError(self.TOKEN + " private-message")):
            with self.assertRaises(DeliveryUnknown) as caught:
                self.api.call("getMe")
        self.assert_safe_exception(caught.exception)

    def test_incomplete_http_error_body_is_sanitized(self):
        error = HTTPError("https://example.test/" + self.TOKEN, 502, self.TOKEN, {}, io.BytesIO())
        with patch.object(error, "read", side_effect=http.client.IncompleteRead(self.TOKEN.encode(), 99)):
            with patch("telegram_bot.bot.urlopen", side_effect=error):
                with self.assertRaises(DeliveryUnknown) as caught:
                    self.api.call("sendMessage", text="private-message")
        self.assert_safe_exception(caught.exception)

    def test_unsupported_method_is_rejected_before_network(self):
        with patch("telegram_bot.bot.urlopen") as transport:
            with self.assertRaises(ValueError):
                self.api.call("deleteWebhook")
            transport.assert_not_called()


if __name__ == "__main__":
    unittest.main()
