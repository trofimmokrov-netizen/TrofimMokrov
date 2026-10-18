"""Pilot requests remain opt-in, individually scoped, and distinct from publication consent."""
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from telegram_bot.bot import Bot, Store


class PilotTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'requests.sqlite3'
        self.store = Store(self.path)
        self.addCleanup(self.store.close)
        self.bot = Bot(self.store, 999, clock=lambda: 1800000000)
        self.sequence = 0

    def message(self, text=None, data=None, identifier=None):
        self.sequence += 1
        message = {'chat': {'id': 101, 'type': 'private'}, 'from': {'id': 101, 'username': 'visitor'}}
        if text is not None:
            message['text'] = text
        if data is not None:
            message['web_app_data'] = {'data': json.dumps(data, ensure_ascii=False)}
        self.bot.process({'update_id': identifier or self.sequence, 'message': message})

    def packet(self, **values):
        packet = {'version': 1, 'type': 'request', 'consent': True, 'service_id': 'websites',
                  'details': 'Нужен один экран для проверки направления', 'contact': '@example_visitor',
                  'request_format': 'pilot', 'portfolio_interest': False}
        packet.update(values)
        return packet

    def request(self):
        return self.store.db.execute('SELECT * FROM requests').fetchone()

    def reach_portfolio(self):
        self.message('/start pilot_websites')
        self.message('Нужен один экран для мастерской')
        self.message('@example_visitor')

    def test_chat_pilot_keeps_format_through_edit_and_requires_confirmation(self):
        self.reach_portfolio()
        self.assertEqual(self.store.session(101, 1800000000)[0], 'portfolio')
        self.message('Без обсуждения кейса')
        self.assertIsNone(self.request())
        self.message('Изменить заявку')
        self.assertEqual(self.store.session(101, 1800000000)[1]['request_format'], 'pilot')
        self.message('Нужен один согласованный экран с контактами')
        self.message('@example_visitor')
        self.message('Можно обсудить кейс')
        self.assertIsNone(self.request())
        self.message('Отправить заявку')
        request = self.request()
        self.assertEqual(request['request_format'], 'pilot')
        self.assertEqual(request['portfolio_interest'], 1)
        self.assertEqual(request['source'], 'site_pilot')
        owner = json.loads(self.store.db.execute('SELECT payload FROM outbox WHERE request_id=?', (request['id'],)).fetchone()[0])
        self.assertIn('объём, срок и стоимость нужно согласовать', owner['text'])
        self.assertIn('Это не разрешение на публикацию', owner['text'])

    def test_cancel_and_new_standard_request_clear_pilot_context(self):
        self.reach_portfolio()
        self.message('Отмена')
        self.assertIsNone(self.request())
        self.message('/request')
        state, data = self.store.session(101, 1800000000)
        self.assertEqual(state, 'service')
        self.assertEqual(data['request_format'], 'standard')
        self.assertFalse(data['portfolio_interest'])

    def test_miniapp_records_interest_without_claiming_publication_permission(self):
        self.message(data=self.packet(portfolio_interest=True), identifier=42)
        self.message(data=self.packet(portfolio_interest=True), identifier=42)
        request = self.request()
        self.assertEqual(request['request_format'], 'pilot')
        self.assertEqual(request['portfolio_interest'], 1)
        self.assertEqual(self.store.db.execute('SELECT COUNT(*) FROM requests').fetchone()[0], 1)

    def test_miniapp_portfolio_choice_is_optional(self):
        self.message(data=self.packet())
        self.assertEqual(self.request()['request_format'], 'pilot')
        self.assertEqual(self.request()['portfolio_interest'], 0)

    def test_invalid_format_and_nonboolean_interest_are_rejected(self):
        for changes in ({'request_format': 'free'}, {'request_format': []}, {'portfolio_interest': 'yes'},
                        {'portfolio_interest': 1}, {'request_format': 'standard', 'portfolio_interest': True}):
            with self.subTest(changes=changes):
                self.message(data=self.packet(**changes))
                self.assertIsNone(self.request())

    def test_old_miniapp_payload_stays_standard(self):
        packet = self.packet()
        packet.pop('request_format'); packet.pop('portfolio_interest')
        self.message(data=packet)
        self.assertEqual(self.request()['request_format'], 'standard')
        self.assertEqual(self.request()['portfolio_interest'], 0)

    def test_owner_can_test_ten_requests_without_changing_client_limit(self):
        self.bot.owner = 101
        for _ in range(11):
            self.message(data=self.packet())
        self.assertEqual(self.store.db.execute('SELECT COUNT(*) FROM requests').fetchone()[0], 10)

    def test_migration_preserves_previous_requests_and_defaults(self):
        old = Path(self.temp.name) / 'old.sqlite3'
        with sqlite3.connect(old) as db:
            db.execute('''CREATE TABLE requests (id INTEGER PRIMARY KEY,update_id INTEGER UNIQUE NOT NULL,
                created INTEGER NOT NULL,chat_id INTEGER NOT NULL,username TEXT NOT NULL,service_id TEXT NOT NULL,
                details TEXT NOT NULL,contact TEXT NOT NULL,source TEXT NOT NULL,
                notification_status TEXT NOT NULL DEFAULT 'pending')''')
            db.execute("INSERT INTO requests VALUES (7,17,1800000000,101,'visitor','websites','Existing request','@example','bot','sent')")
        for _ in range(2):
            store = Store(old)
            try:
                rows = store.db.execute('SELECT * FROM requests').fetchall()
                self.assertEqual(len(rows), 1)
                self.assertEqual(rows[0]['id'], 7)
                self.assertEqual(rows[0]['notification_status'], 'sent')
                self.assertEqual(rows[0]['request_format'], 'standard')
                self.assertEqual(rows[0]['portfolio_interest'], 0)
            finally:
                store.close()


if __name__ == '__main__':
    unittest.main()
