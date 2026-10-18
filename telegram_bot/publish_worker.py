"""Durable publication delivery to a static Git site and Instagram Login API.

Each public write is marked in-flight before network I/O. Ambiguous Instagram
publishes are never automatically retried. A deterministic site post ID permits
safe inspection after a Git push with an unknown outcome.
"""
from __future__ import annotations

import hashlib
import http.client
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .publishing import accounts
from .bot import DeliveryUnknown, TelegramRejected


class PublishFailure(Exception):
    pass


class PublishUnknown(Exception):
    pass


class Instagram:
    def __init__(self, account):
        self.account = account
        self.version = os.environ.get("INSTAGRAM_GRAPH_VERSION", "v24.0")
        if not re.fullmatch(r"v[0-9]+\.0", self.version):
            raise PublishFailure("Некорректная версия Instagram API.")

    def request(self, path, payload=None, *, publishing=False):
        token = os.environ.get(f"INSTAGRAM_{self.account['slot']}_TOKEN")
        if not token:
            raise PublishFailure("Instagram ожидает подключения через Meta.")
        url = f"https://graph.instagram.com/{self.version}/{path}"
        request = Request(url, data=urlencode(payload).encode() if payload is not None else None,
                          headers={"Authorization": "Bearer " + token})
        try:
            with urlopen(request, timeout=30) as response:
                result = json.loads(response.read(1_000_000))
        except HTTPError as error:
            code = error.code
            error.close()
            if publishing and code >= 500:
                raise PublishUnknown("Instagram не подтвердил публикацию. Проверьте аккаунт вручную; автоматического повтора нет.") from None
            raise PublishFailure(f"Instagram отклонил запрос (HTTP {code}). Проверьте разрешения, лимит и срок доступа.") from None
        except (URLError, OSError, ValueError, http.client.HTTPException):
            if publishing:
                raise PublishUnknown("Ответ Instagram потерян. Проверьте аккаунт вручную; автоматического повтора нет.") from None
            raise PublishFailure("Не получен ответ Instagram. Публикация не подтверждена.") from None
        if not isinstance(result, dict) or result.get("error"):
            if publishing:
                raise PublishUnknown("Instagram вернул неподтверждённый результат публикации.")
            raise PublishFailure("Instagram вернул некорректный результат.")
        return result

    def verify(self):
        identity = self.request("me?fields=user_id,username")
        user_id = str(identity.get("user_id", ""))
        if not user_id.isdigit() or (self.account["user_id"] and user_id != self.account["user_id"]) or identity.get("username", "").lower() != self.account["username"].lower():
            raise PublishFailure("Доступ Instagram принадлежит другому аккаунту. Публикация остановлена.")
        self.account["user_id"] = user_id
        return user_id

    def create(self, image, caption):
        user_id = self.verify()
        result = self.request(user_id + "/media", {"image_url": image, "caption": caption})
        identifier = result.get("id", "")
        if not isinstance(identifier, str) or not identifier.isdigit():
            raise PublishFailure("Instagram не подтвердил создание контейнера.")
        return identifier

    def status(self, container):
        return self.request(container + "?fields=status_code").get("status_code")

    def publish(self, container):
        user_id = self.verify()
        result = self.request(user_id + "/media_publish", {"creation_id": container}, publishing=True)
        identifier = result.get("id", "")
        if not isinstance(identifier, str) or not identifier.isdigit():
            raise PublishUnknown("Instagram не подтвердил ID опубликованного материала.")
        # A permalink lookup must never turn a successful publish into a retry.
        try:
            url = self.request(identifier + "?fields=permalink").get("permalink", "")
            if isinstance(url, str) and re.fullmatch(r"https://(?:www\.)?instagram\.com/[A-Za-z0-9_/-]+/?", url):
                return url
        except PublishFailure:
            pass
        return "Instagram media ID: " + identifier


class SitePublisher:
    def __init__(self, directory):
        self.path = Path(directory).resolve() / "site-publisher"
        self.root = Path(__file__).resolve().parents[1]
        self.base = json.loads((self.root / "content/site.json").read_text())["base_url"].rstrip("/")

    def git(self, *args, cwd=None):
        try:
            return subprocess.run(["git", *args], cwd=cwd or self.path, check=True,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=90).stdout.decode().strip()
        except (subprocess.SubprocessError, OSError):
            raise PublishFailure("Не удалось обновить сайт через Git. Проверьте доступ к репозиторию; содержимое ошибки скрыто.") from None

    def prepare(self):
        if not self.path.exists():
            origin = self.git("remote", "get-url", "origin", cwd=self.root)
            self.git("clone", "--quiet", "--single-branch", "--branch", "main", origin, str(self.path), cwd=self.root)
        if self.git("status", "--porcelain"):
            raise PublishFailure("В рабочей копии публикаций есть незавершённые изменения. Нужна проверка владельцем.")
        self.git("pull", "--ff-only", "origin", "main")

    def write(self, identifier, data, created, image=None, *, post):
        self.prepare()
        (self.path / "content/updates").mkdir(parents=True, exist_ok=True)
        (self.path / "assets/updates").mkdir(parents=True, exist_ok=True)
        if image is not None:
            (self.path / f"assets/updates/{identifier}.jpg").write_bytes(image)
        if post:
            text = data["text"]
            item = {"id": identifier, "date": datetime.fromtimestamp(created, timezone.utc).date().isoformat(),
                    "title": text.splitlines()[0][:120], "text": text}
            if data.get("photo"):
                item["image"] = f"assets/updates/{identifier}.jpg"
            (self.path / f"content/updates/{identifier}.json").write_text(json.dumps(item, ensure_ascii=False, indent=2) + "\n")
        try:
            subprocess.run([sys.executable, "scripts/build.py"], cwd=self.path, check=True, capture_output=True, timeout=45)
            subprocess.run([sys.executable, "scripts/check.py"], cwd=self.path, check=True, capture_output=True, timeout=45)
        except (subprocess.SubprocessError, OSError):
            raise PublishFailure("Проверка сайта перед публикацией не прошла. Изменения не отправлены.") from None
        self.git("add", "--all")
        if self.git("diff", "--cached", "--name-only"):
            self.git("-c", "user.name=TrofimAI", "-c", "user.email=trofimai@users.noreply.github.com", "commit", "-m", "Publish owner-approved update " + identifier[:8])
        self.git("push", "origin", "HEAD:main")
        return self.base + "/updates.html#post-" + identifier

    def image_url(self, identifier):
        return self.base + f"/assets/updates/{identifier}.jpg"

    def live(self, identifier, data, *, post):
        try:
            if data.get("photo"):
                with urlopen(self.image_url(identifier), timeout=10) as response:
                    payload = response.read(8_000_001)
                if hashlib.sha256(payload).hexdigest() != data.get("image_hash"):
                    return False
            if post:
                with urlopen(self.base + "/updates.html", timeout=10) as response:
                    return ("post-" + identifier).encode() in response.read(10_000_000)
            return True
        except (URLError, OSError):
            return False


class PublishWorker:
    def __init__(self, store, telegram, directory):
        self.store = store
        self.telegram = telegram
        self.site = SitePublisher(directory)
        self.accounts = {str(a["slot"]): a for a in accounts()}
        # Sending may have succeeded immediately before a crash.
        with store.db:
            rows = store.db.execute("SELECT d.job_id,d.target,j.chat_id FROM publication_deliveries d JOIN publication_jobs j ON j.id=d.job_id WHERE d.state='sending'").fetchall()
            for row in rows:
                store.db.execute("UPDATE publication_deliveries SET state='unknown',result=? WHERE job_id=? AND target=?", ("Процесс прерван во время отправки. Проверьте площадку вручную.", row["job_id"], row["target"]))
                store.enqueue(row["chat_id"], "Публикация №" + row["job_id"][:8] + " · " + row["target"] + ": результат неизвестен. Проверьте площадку вручную; повтор отключён.")
            store.db.execute("UPDATE publication_jobs SET media_state='failed' WHERE media_state='preparing'")
            interrupted = store.db.execute("SELECT chat_id,id FROM publication_generations WHERE state='running'").fetchall()
            for row in interrupted:
                state, data = store.session(row['chat_id'], int(time.time()))
                if state == 'publish:generating' and data.get('generation') == row['id']:
                    store.clear_session(row['chat_id'])
                    store.enqueue(row['chat_id'], 'Подготовка AI-текста была прервана. Начните заново /publish; ничего не опубликовано.')
            store.db.execute("UPDATE publication_generations SET state='failed' WHERE state='running'")

    def generate(self):
        row = self.store.db.execute("SELECT * FROM publication_generations WHERE state='pending' LIMIT 1").fetchone()
        if not row:
            return
        state, session = self.store.session(row['chat_id'], int(time.time()))
        if state != 'publish:generating' or session.get('generation') != row['id']:
            with self.store.db:
                self.store.db.execute("UPDATE publication_generations SET state='cancelled' WHERE id=?", (row['id'],))
            return
        with self.store.db:
            self.store.db.execute("UPDATE publication_generations SET state='running' WHERE id=?", (row['id'],))
        try:
            token = os.environ.get('TROFIM_OPENAI_TOKEN')
            if not token:
                raise PublishFailure('OpenAI API не подключён. Можно прислать готовый текст через /publish.')
            payload = {'model': os.environ.get('TROFIM_TEXT_MODEL', 'gpt-4.1-mini'), 'store': False,
                       'instructions': 'Напиши на русском черновик поста от лица Трофима Мокрова для Instagram и его сайта. Первая строка — короткий заголовок. Не более 2200 символов. Только текст публикации без Markdown. Используй только факты из идеи пользователя: не выдумывай выполненные работы, отзывы, цены, гарантии или результаты. Не обещай публикацию. Не включай секреты и персональные данные третьих лиц.',
                       'input': row['idea'], 'max_output_tokens': 1100}
            request = Request('https://api.openai.com/v1/responses', data=json.dumps(payload).encode(),
                              headers={'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'})
            with urlopen(request, timeout=45) as response:
                result = json.loads(response.read(1_000_000))
            text = '\n'.join(part['text'] for item in result.get('output', []) if item.get('type') == 'message'
                             for part in item.get('content', []) if part.get('type') == 'output_text').strip()
            if not 1 <= len(text) <= 2200:
                raise PublishFailure('AI не вернул текст нужной длины. Начните заново /publish или пришлите готовый текст.')
            with self.store.db:
                self.store.db.execute("UPDATE publication_generations SET state='done' WHERE id=?", (row['id'],))
                self.store.save_session(row['chat_id'], 'publish:photo', {'text': text, 'targets': [], 'labels': []}, int(time.time()))
                self.store.enqueue(row['chat_id'], 'AI-ЧЕРНОВИК — проверьте факты:\n\n' + text + '\n\nТеперь пришлите одну фотографию или выберите «Без фотографии». Перед размещением можно изменить текст.',
                                   {'keyboard': [['Без фотографии'], ['Отмена']], 'resize_keyboard': True})
        except (PublishFailure, URLError, OSError, ValueError, http.client.HTTPException):
            with self.store.db:
                self.store.db.execute("UPDATE publication_generations SET state='failed' WHERE id=?", (row['id'],))
                self.store.clear_session(row['chat_id'])
                self.store.enqueue(row['chat_id'], 'AI-черновик не получен. Проверьте доступ и баланс OpenAI API. Можно начать /publish с готовым текстом. Ничего не опубликовано.')

    def finish(self, job, target, state, result):
        with self.store.db:
            self.store.db.execute("UPDATE publication_deliveries SET state=?,result=? WHERE job_id=? AND target=?", (state, result, job["id"], target))
            self.store.enqueue(job["chat_id"], "Публикация №" + job["id"][:8] + " · " + target + ": " + state + "\n" + result)

    def step(self):
        self.generate()
        jobs = self.store.db.execute("SELECT DISTINCT j.* FROM publication_jobs j JOIN publication_deliveries d ON d.job_id=j.id WHERE d.state IN ('pending','container') ORDER BY j.created LIMIT 1").fetchall()
        for job in jobs:
            data = json.loads(job["data"])
            deliveries = self.store.db.execute("SELECT * FROM publication_deliveries WHERE job_id=?", (job["id"],)).fetchall()
            post = any(d["target"] == "site" for d in deliveries)
            try:
                if job["media_state"] == "failed":
                    raise PublishFailure("Подготовка сайта прервана. Нужна проверка рабочей копии; автоматический повтор отключён.")
                if job["media_state"] == "pending":
                    with self.store.db:
                        self.store.db.execute("UPDATE publication_jobs SET media_state='preparing' WHERE id=?", (job["id"],))
                    image = self.telegram.photo_bytes(data["photo"]["file_id"]) if data.get("photo") else None
                    if image:
                        data["image_hash"] = hashlib.sha256(image).hexdigest()
                    self.site.write(job["id"], data, job["created"], image, post=post)
                    data["prepared_at"] = int(time.time())
                    with self.store.db:
                        self.store.db.execute("UPDATE publication_jobs SET media_state='waiting',data=? WHERE id=?", (json.dumps(data, ensure_ascii=False), job["id"]))
                    return
                if not self.site.live(job["id"], data, post=post):
                    if time.time() - data.get("prepared_at", job["created"]) > 1800:
                        raise PublishFailure("Сайт не подтвердил обновление за 30 минут. Проверьте GitHub Pages; повторное размещение отключено.")
                    return
                for delivery in deliveries:
                    target = delivery["target"]
                    if delivery["state"] not in ("pending", "container"):
                        continue
                    if target == "site":
                        self.finish(job, target, "sent", self.site.base + "/updates.html#post-" + job["id"])
                        continue
                    account = self.accounts.get(target.split(":")[-1])
                    if not account:
                        self.finish(job, target, "failed", "Аккаунт больше не настроен.")
                        continue
                    instagram = Instagram(account)
                    try:
                        if delivery["state"] == "pending":
                            container = instagram.create(self.site.image_url(job["id"]), data["text"])
                            with self.store.db:
                                self.store.db.execute("UPDATE publication_deliveries SET state='container',container_id=? WHERE job_id=? AND target=?", (container, job["id"], target))
                            continue
                        status = instagram.status(delivery["container_id"])
                        if status == "IN_PROGRESS":
                            if time.time() - data.get("prepared_at", job["created"]) > 3600:
                                raise PublishFailure("Instagram слишком долго готовит фото. Публикация остановлена.")
                            continue
                        if status != "FINISHED":
                            raise PublishFailure("Контейнер Instagram не готов или уже опубликован. Проверьте аккаунт вручную.")
                        with self.store.db:
                            self.store.db.execute("UPDATE publication_deliveries SET state='sending' WHERE job_id=? AND target=?", (job["id"], target))
                        result = instagram.publish(delivery["container_id"])
                        self.finish(job, target, "sent", result)
                    except PublishUnknown as error:
                        self.finish(job, target, "unknown", str(error))
                    except PublishFailure as error:
                        self.finish(job, target, "failed", str(error))
            except (PublishFailure, DeliveryUnknown, TelegramRejected) as error:
                with self.store.db:
                    self.store.db.execute("UPDATE publication_jobs SET media_state='failed' WHERE id=?", (job["id"],))
                for delivery in deliveries:
                    if delivery["state"] in ("pending", "container"):
                        self.finish(job, delivery["target"], "failed", str(error))
