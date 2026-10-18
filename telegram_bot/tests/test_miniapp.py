"""Keyboard Mini App intake: real sender binding and untrusted payload checks."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from telegram_bot.bot import Bot, Store


class MiniAppTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = Store(Path(self.temp.name) / 'requests.sqlite3')
        self.addCleanup(self.store.close)
        self.bot = Bot(self.store, 999, clock=lambda: 1800000000,
                       miniapp_url='https://example.test/miniapp/')
        self.sequence = 0

    def packet(self, **changes):
        value = {'version': 1, 'type': 'request', 'consent': True,
                 'service_id': 'websites', 'details': 'Нужен сайт для мастерской',
                 'contact': '@example_visitor'}
        value.update(changes)
        return value

    def send(self, data, identifier=None, chat=101, chat_type='private'):
        self.sequence += 1
        update = {'update_id': identifier or self.sequence,
                  'message': {'chat': {'id': chat, 'type': chat_type},
                              'from': {'id': chat, 'username': 'visitor'},
                              'web_app_data': {'data': data if isinstance(data, str) else json.dumps(data, ensure_ascii=False)}}}
        self.bot.process(update)

    def count(self):
        return self.store.db.execute('SELECT COUNT(*) FROM requests').fetchone()[0]

    def test_submit_binds_sender_and_recipient_on_server(self):
        self.send(self.packet(chat_id=777, owner_chat_id=777, source='forged', price='0'))
        request = self.store.db.execute('SELECT * FROM requests').fetchone()
        self.assertEqual(request['chat_id'], 101)
        self.assertEqual(request['source'], 'miniapp')
        self.assertEqual(request['service_id'], 'websites')
        messages = self.store.db.execute('SELECT chat_id,request_id FROM outbox ORDER BY id').fetchall()
        self.assertEqual([(x['chat_id'], x['request_id']) for x in messages], [(999, request['id']), (101, None)])
        self.assertEqual(self.store.session(101, 1800000000), ('', {}))

    def test_repeated_telegram_update_does_not_repeat_request(self):
        self.send(self.packet(), identifier=42)
        self.send(self.packet(), identifier=42)
        self.assertEqual(self.count(), 1)
        self.assertEqual(self.store.db.execute('SELECT COUNT(*) FROM outbox').fetchone()[0], 2)

    def test_untrusted_packets_never_create_a_request(self):
        invalid = ['not json', '[]', self.packet(consent=False), self.packet(version=True),
                   self.packet(type='other'), self.packet(service_id='unknown'),
                   self.packet(service_id=[]), self.packet(details='tiny'),
                   self.packet(details=42), self.packet(contact='\nowner@example.test'),
                   self.packet(contact='!!!!!!!'), self.packet(contact='x'*161),
                   self.packet(details='😀'*1500)]
        for value in invalid:
            with self.subTest(kind=type(value).__name__):
                self.send(value)
                self.assertEqual(self.count(), 0)

    def test_owner_is_required_and_groups_are_ignored(self):
        self.send(self.packet(), chat_type='group')
        self.bot.owner = None
        self.send(self.packet())
        self.assertEqual(self.count(), 0)
        self.assertTrue(all(x[0] == 101 for x in self.store.db.execute('SELECT chat_id FROM outbox')))

    def test_daily_limit_applies_to_miniapp(self):
        for _ in range(4):
            self.send(self.packet())
        self.assertEqual(self.count(), 3)

    def test_creation_and_outgoing_queue_are_atomic(self):
        with patch.object(self.store, 'enqueue', side_effect=RuntimeError('simulated disk failure')):
            with self.assertRaises(RuntimeError):
                self.send(self.packet(), identifier=42)
        self.assertEqual(self.count(), 0)
        self.assertEqual(self.store.offset, 0)
        self.send(self.packet(), identifier=42)
        self.assertEqual(self.count(), 1)

    def test_keyboard_url_is_explicit_and_requires_https(self):
        self.bot.process({'update_id': 1, 'message': {'chat': {'id': 101, 'type': 'private'}, 'from': {'id': 101}, 'text': '/menu'}})
        payload = json.loads(self.store.db.execute('SELECT payload FROM outbox').fetchone()[0])
        button = payload['reply_markup']['keyboard'][0][0]
        self.assertEqual(button['web_app']['url'], 'https://example.test/miniapp/')
        for value in ('http://example.test', 'javascript:alert(1)', 'https://user:password@example.test/', 'https://example.test/#secret'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                Bot(self.store, 999, miniapp_url=value)

    def test_assistant_answers_with_current_site_price(self):
        self.bot.process({'update_id': 1, 'message': {'chat': {'id': 101, 'type': 'private'}, 'from': {'id': 101}, 'text': 'Сколько стоит сайт?'}})
        payload = json.loads(self.store.db.execute('SELECT payload FROM outbox').fetchone()[0])
        self.assertIn(self.bot.by_id['websites']['price'], payload['text'])
        self.assertIn('/services.html#websites', payload['text'])
        self.assertEqual(self.count(), 0)

    def test_about_and_site_buttons_open_real_site_sections(self):
        for identifier, text, suffix in ((1, '/about', '/about.html'), (2, 'Перейти на сайт', '/')):
            self.bot.process({'update_id': identifier, 'message': {'chat': {'id': 101, 'type': 'private'}, 'from': {'id': 101}, 'text': text}})
            payload = json.loads(self.store.db.execute('SELECT payload FROM outbox ORDER BY id DESC').fetchone()[0])
            self.assertEqual(payload['reply_markup']['inline_keyboard'][0][0]['url'], self.bot.website + suffix)

    def test_bot_service_answers_distinguish_setup_and_hosting_costs(self):
        for identifier, text in ((1, 'Нужен Telegram-бот под мой бренд'), (2, 'Бот будет работать бесплатно?')):
            self.bot.process({'update_id': identifier, 'message': {'chat': {'id': 101, 'type': 'private'}, 'from': {'id': 101}, 'text': text}})
            payload = json.loads(self.store.db.execute('SELECT payload FROM outbox ORDER BY id DESC').fetchone()[0])
            self.assertIn(self.bot.by_id['telegram-bots']['price'], payload['text'])
            if identifier == 1:
                self.assertIn('/services.html#telegram-bots', payload['text'])
            else:
                self.assertIn(self.bot.by_id['telegram-bots']['separate'], payload['text'])


if __name__ == '__main__':
    unittest.main()
