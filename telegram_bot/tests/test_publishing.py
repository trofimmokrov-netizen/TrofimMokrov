"""Offline publication checks: owner access, confirmation, and ambiguous writes."""
import json
import os
import tempfile
import shutil
import subprocess
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from telegram_bot.bot import Bot, Store
from telegram_bot.publishing import accounts
from telegram_bot.publish_worker import Instagram, PublishFailure, PublishUnknown, PublishWorker, SitePublisher


class PublishingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.config = self.directory / 'accounts.json'
        self.config.write_text(json.dumps([{'slot': 1, 'username': 'zavodclauda', 'user_id': '12345'}]))
        self.env = patch.dict(os.environ, {'TROFIM_PUBLISH_ACCOUNTS': str(self.config), 'INSTAGRAM_1_TOKEN': 'test-secret-not-real'})
        self.env.start(); self.addCleanup(self.env.stop)
        self.store = Store(self.directory / 'private' / 'test.sqlite3')
        self.addCleanup(self.store.close)
        self.bot = Bot(self.store, 999)
        self.counter = 0

    def message(self, text=None, chat=999, **fields):
        self.counter += 1
        self.bot.process({'update_id': self.counter, 'message': {'chat': {'id': chat, 'type': 'private'}, 'from': {'id': chat}, 'text': text, **fields}})

    def jobs(self):
        return self.store.db.execute('SELECT * FROM publication_jobs').fetchall()

    def prepare(self, instagram=False):
        self.message('/publish'); self.message('Мой новый проект\nОписание работы.')
        if instagram:
            self.message(photo=[{'file_id': 'photo-1', 'width': 1080, 'height': 1350}])
            self.message('Instagram @zavodclauda')
        else:
            self.message('Без фотографии')
        self.message('Сайт'); self.message('Предпросмотр')

    def test_visitors_cannot_start_or_confirm_publications(self):
        for text in ['/publish', '/accounts', '/publications', 'Подтвердить публикацию']:
            self.message(text, chat=101)
        self.assertEqual(self.jobs(), [])
        self.assertNotIn('publish:', self.store.session(101, 0)[0])

    def test_confirmation_is_required_and_repeated_update_does_not_duplicate(self):
        self.prepare()
        self.assertEqual(self.jobs(), [])
        self.message('Подтвердить публикацию')
        self.message('Подтвердить публикацию')
        self.assertEqual(len(self.jobs()), 1)
        self.assertEqual(self.store.db.execute('SELECT state FROM publication_deliveries').fetchone()[0], 'pending')

    def test_cancel_has_no_public_side_effect(self):
        self.prepare(); self.message('/cancel')
        self.message('Подтвердить публикацию')
        self.assertEqual(self.jobs(), [])

    def test_edit_keeps_photo_and_requires_new_preview(self):
        self.prepare(instagram=True); self.message('Изменить текст'); self.message('Исправленный текст')
        state, data = self.store.session(999, int(self.bot.clock()))
        self.assertEqual(state, 'publish:targets')
        self.assertEqual(data['photo']['file_id'], 'photo-1')
        self.assertEqual(set(data['targets']), {'site', 'instagram:1'})
        self.assertEqual(self.jobs(), [])

    def test_instagram_requires_supported_photo(self):
        self.message('/publish'); self.message('Текст'); self.message('Без фотографии')
        self.message('Instagram @zavodclauda')
        self.assertEqual(self.store.session(999, int(self.bot.clock()))[1]['targets'], [])

    def test_more_than_three_accounts_or_duplicate_slot_rejected(self):
        for entries in [[{'slot': i, 'username': 'test', 'user_id': ''} for i in range(1, 5)], [{'slot': 1, 'username': 'one'}, {'slot': 1, 'username': 'two'}]]:
            self.config.write_text(json.dumps(entries))
            with self.assertRaises(ValueError): accounts()

    def test_independent_targets_and_no_resend_after_success(self):
        self.prepare(instagram=True); self.message('Подтвердить публикацию')
        worker = PublishWorker(self.store, Mock(), self.directory)
        worker.site = Mock(base='https://example.test')
        worker.site.live.return_value = True
        self.store.db.execute("UPDATE publication_jobs SET media_state='waiting'")
        self.store.db.commit()
        with patch('telegram_bot.publish_worker.Instagram') as factory:
            api = factory.return_value
            api.create.return_value = '5678'
            worker.step()
            api.status.return_value = 'FINISHED'
            api.publish.return_value = 'https://www.instagram.com/p/example/'
            worker.step(); worker.step()
            self.assertEqual(api.publish.call_count, 1)
        self.assertEqual([r[0] for r in self.store.db.execute('SELECT state FROM publication_deliveries')], ['sent', 'sent'])

    def test_unknown_instagram_publish_is_never_automatically_retried(self):
        self.prepare(instagram=True); self.message('Подтвердить публикацию')
        worker = PublishWorker(self.store, Mock(), self.directory)
        worker.site = Mock(base='https://example.test'); worker.site.live.return_value = True
        self.store.db.execute("UPDATE publication_jobs SET media_state='waiting'")
        self.store.db.execute("UPDATE publication_deliveries SET state='container',container_id='5678' WHERE target='instagram:1'")
        self.store.db.commit()
        with patch('telegram_bot.publish_worker.Instagram') as factory:
            api = factory.return_value; api.status.return_value = 'FINISHED'
            api.publish.side_effect = PublishUnknown('Проверьте вручную')
            worker.step(); worker.step()
            self.assertEqual(api.publish.call_count, 1)
        self.assertEqual(self.store.db.execute("SELECT state FROM publication_deliveries WHERE target='instagram:1'").fetchone()[0], 'unknown')
        self.assertEqual(self.store.db.execute("SELECT state FROM publication_deliveries WHERE target='site'").fetchone()[0], 'sent')

    def test_restart_does_not_replay_interrupted_publish(self):
        self.prepare(instagram=True); self.message('Подтвердить публикацию')
        self.store.db.execute("UPDATE publication_deliveries SET state='sending' WHERE target='instagram:1'")
        self.store.db.commit()
        PublishWorker(self.store, Mock(), self.directory)
        self.assertEqual(self.store.db.execute("SELECT state FROM publication_deliveries WHERE target='instagram:1'").fetchone()[0], 'unknown')

    def test_instagram_transport_does_not_expose_token_and_marks_ambiguous_write(self):
        from urllib.error import URLError
        with patch.object(Instagram, 'verify', return_value='12345'), patch('telegram_bot.publish_worker.urlopen', side_effect=URLError('https://test/?secret=test-secret-not-real')):
            with self.assertRaises(PublishUnknown) as caught:
                Instagram(accounts()[0]).publish('5678')
        self.assertNotIn('test-secret', str(caught.exception))

    def test_wrong_instagram_identity_cannot_create_publication(self):
        api = Instagram(accounts()[0])
        api.request = Mock(return_value={'user_id': '456', 'username': 'someone_else'})
        with self.assertRaises(PublishFailure): api.create('https://example.test/photo.jpg', 'Text')
        self.assertEqual(api.request.call_count, 1)

    def test_ai_text_is_only_a_draft_and_does_not_create_public_job(self):
        with patch.dict(os.environ, {'TROFIM_OPENAI_TOKEN': 'test-openai'}):
            self.message('/publish'); self.message('Идея: объяснить пользу ботов')
            self.assertEqual(self.jobs(), [])
            response = Mock()
            response.__enter__ = Mock(return_value=response)
            response.__exit__ = Mock(return_value=False)
            response.read.return_value = json.dumps({'output': [{'type': 'message', 'content': [{'type': 'output_text', 'text': 'Бот для вашего проекта'}]}]}).encode()
            with patch('telegram_bot.publish_worker.urlopen', return_value=response):
                PublishWorker(self.store, Mock(), self.directory).step()
            state, data = self.store.session(999, int(self.bot.clock()))
            self.assertEqual(state, 'publish:photo')
            self.assertEqual(data['text'], 'Бот для вашего проекта')
            self.assertEqual(self.jobs(), [])

    def test_cancelled_ai_generation_cannot_restore_cancelled_draft(self):
        with patch.dict(os.environ, {'TROFIM_OPENAI_TOKEN': 'test-openai'}):
            self.message('/publish'); self.message('Идея: о работе'); self.message('/cancel')
            with patch('telegram_bot.publish_worker.urlopen') as network:
                PublishWorker(self.store, Mock(), self.directory).step()
            network.assert_not_called()
            self.assertEqual(self.store.db.execute('SELECT state FROM publication_generations').fetchone()[0], 'cancelled')

    def test_actual_git_publisher_builds_escaped_post_and_is_idempotent(self):
        root = Path(__file__).resolve().parents[2]
        seed = self.directory / 'seed'; seed.mkdir()
        for entry in ['scripts', 'content', 'assets', 'miniapp', 'articles']:
            shutil.copytree(root / entry, seed / entry, ignore=shutil.ignore_patterns('__pycache__'))
        shutil.copyfile(root / 'logo.svg', seed / 'logo.svg')
        bare = self.directory / 'remote.git'
        def git(*args, cwd=seed):
            return subprocess.run(['git', *args], cwd=cwd, check=True, capture_output=True).stdout.decode()
        git('init', '--bare', str(bare)); git('init', '-b', 'main')
        git('config', 'user.name', 'Test'); git('config', 'user.email', 'test@example.test')
        git('add', '.'); git('commit', '-m', 'Fixture'); git('remote', 'add', 'origin', str(bare)); git('push', 'origin', 'main')
        publisher = SitePublisher(self.directory / 'private')
        publisher.root = seed
        identifier = 'a' * 32
        data = {'text': 'Мой проект\n<script>alert(1)</script>'}
        publisher.write(identifier, data, 1800000000, post=True)
        first = git('rev-parse', 'main', cwd=bare)
        html = git('show', 'main:updates.html', cwd=bare)
        self.assertIn('&lt;script&gt;alert(1)&lt;/script&gt;', html)
        self.assertNotIn('<script>alert(1)</script>', html)
        self.assertIn('post-' + identifier, html)
        publisher.write(identifier, data, 1800000000, post=True)
        self.assertEqual(git('rev-parse', 'main', cwd=bare), first)


if __name__ == '__main__':
    unittest.main()
