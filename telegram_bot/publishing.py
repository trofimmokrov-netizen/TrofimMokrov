"""Owner-only publishing drafts. No network calls inside intake transactions."""
from __future__ import annotations

import json
import os
import re
import uuid
from pathlib import Path


def accounts():
    """Identifiers live in a private config; credentials remain in environment."""
    path = os.environ.get("TROFIM_PUBLISH_ACCOUNTS")
    if not path:
        return []
    root = Path(__file__).resolve().parents[1]
    source = Path(path).expanduser().resolve()
    if source.is_relative_to(root):
        raise ValueError("Конфигурация аккаунтов должна находиться вне публичного сайта.")
    entries = json.loads(source.read_text())
    if not isinstance(entries, list) or len(entries) > 3:
        raise ValueError("Разрешено до трёх Instagram-аккаунтов.")
    result = []
    for item in entries:
        slot = item.get("slot")
        if type(slot) is not int or not 1 <= slot <= 3 or any(a["slot"] == slot for a in result):
            raise ValueError("У каждого Instagram-аккаунта должен быть свой слот 1–3.")
        username = item.get("username", "").lstrip("@")
        user_id = item.get("user_id", "")
        if not re.fullmatch(r"[A-Za-z0-9_.]{1,30}", username) or (user_id and not re.fullmatch(r"[0-9]+", user_id)):
            raise ValueError("Проверьте имя и числовой ID Instagram-аккаунта.")
        result.append({"slot": slot, "username": username, "user_id": user_id,
                       "ready": bool(os.environ.get(f"INSTAGRAM_{slot}_TOKEN"))})
    return result


def initialize(store):
    store.db.executescript("""
        CREATE TABLE IF NOT EXISTS publication_jobs (
            id TEXT PRIMARY KEY, chat_id INTEGER NOT NULL,
            created INTEGER NOT NULL, data TEXT NOT NULL,
            media_state TEXT NOT NULL DEFAULT 'pending'
        );
        CREATE TABLE IF NOT EXISTS publication_deliveries (
            job_id TEXT NOT NULL, target TEXT NOT NULL, state TEXT NOT NULL DEFAULT 'pending',
            container_id TEXT, result TEXT NOT NULL DEFAULT '',
            PRIMARY KEY(job_id,target), FOREIGN KEY(job_id) REFERENCES publication_jobs(id)
        );
        CREATE TABLE IF NOT EXISTS publication_generations (
            id TEXT PRIMARY KEY, chat_id INTEGER NOT NULL,
            idea TEXT NOT NULL, state TEXT NOT NULL DEFAULT 'pending'
        );
    """)
    store.db.commit()


class PublisherMenu:
    def __init__(self, bot):
        self.bot = bot
        self.store = bot.store
        self.accounts = accounts()
        initialize(self.store)

    def keyboard(self, rows):
        return {"keyboard": [[text] for text in rows] + [["Отмена"]], "resize_keyboard": True}

    def say(self, chat, text, rows=()):
        self.bot.reply(chat, text, self.keyboard(rows))

    def save(self, chat, state, data, now):
        self.store.save_session(chat, "publish:" + state, data, now)

    def destinations(self, chat, data, now):
        self.save(chat, "targets", data, now)
        labels = ["Сайт"] + ["Instagram @" + a["username"] for a in self.accounts if a["ready"]]
        self.say(chat, "Выберите площадки. Повторное нажатие снимает выбор.\nВыбрано: " +
                 (", ".join(data.get("labels", [])) or "ничего"), labels + ["Предпросмотр"])

    def handle(self, chat, message, now):
        text = message.get("text", "")
        text = text.strip() if isinstance(text, str) else ""
        command = text.split(maxsplit=1)[0].split("@", 1)[0] if text else ""
        state, data = self.store.session(chat, now)
        entry = command in ("/publish", "/accounts", "/publications") or text == "Мои публикации"
        if chat != self.bot.owner:
            if entry:
                self.bot.reply(chat, "Редактор публикаций доступен только владельцу бота.")
                return True
            return False
        if command == "/accounts":
            details = ["Сайт — подключён к очереди публикаций."]
            details += [f"Instagram @{a['username']} — " + ("доступ настроен; проверка при отправке" if a["ready"] else "ожидает подключения через Meta") for a in self.accounts]
            self.bot.reply(chat, "Площадки (до трёх Instagram-аккаунтов):\n" + "\n".join(details))
            return True
        if command == "/publications":
            rows = self.store.db.execute("SELECT j.id,d.target,d.state,d.result FROM publication_jobs j JOIN publication_deliveries d ON d.job_id=j.id WHERE j.chat_id=? ORDER BY j.created DESC LIMIT 12", (chat,)).fetchall()
            self.bot.reply(chat, "Последние отправки:\n" + ("\n".join(f"{r['id'][:8]} · {r['target']} · {r['state']} {r['result']}" for r in rows) or "Публикаций пока нет."))
            return True
        if command == "/publish" or text == "Мои публикации":
            self.save(chat, "text", {}, now)
            ai = "Для AI-черновика начните сообщение с «Идея:» и опишите задачу." if os.environ.get("TROFIM_OPENAI_TOKEN") else "AI-генерация ожидает подключения OpenAI API; готовый текст можно публиковать уже сейчас."
            self.say(chat, "Новая публикация. Пришлите готовый текст (1–2200 символов). Первая строка станет заголовком на сайте.\n\nПосле текста добавим фотографию и выберем площадки. " + ai)
            return True
        if not state.startswith("publish:"):
            return False
        if command in ("/cancel", "/menu", "/start") or text == "Отмена":
            return False  # Existing global navigation clears the draft.
        if command.startswith("/"):
            self.say(chat, "Завершите публикацию или нажмите «Отмена».")
            return True
        if state == "publish:text":
            if not 1 <= len(text) <= 2200:
                self.say(chat, "Нужен текст от 1 до 2200 символов.")
                return True
            if text.lower().startswith("идея:"):
                if not os.environ.get("TROFIM_OPENAI_TOKEN"):
                    self.say(chat, "OpenAI API ещё не подключён. Пришлите готовый текст без префикса «Идея:».")
                    return True
                idea = text[5:].strip()
                if not idea:
                    self.say(chat, "После «Идея:» опишите, о чём написать.")
                    return True
                generation = uuid.uuid4().hex
                self.store.db.execute("INSERT INTO publication_generations(id,chat_id,idea) VALUES(?,?,?)", (generation, chat, idea))
                self.save(chat, "generating", {"generation": generation}, now)
                self.say(chat, "Готовлю AI-черновик. Он не будет опубликован без вашего подтверждения.")
                return True
            data = {"text": text, "targets": [], "labels": []}
            self.save(chat, "photo", data, now)
            self.say(chat, "Пришлите одну фотографию обычным фото в Telegram. Для Instagram подходит JPEG с соотношением сторон от 4:5 до 1.91:1. Альбомы и видео пока не поддерживаются.\nДля текстовой заметки только на сайте нажмите «Без фотографии».", ["Без фотографии"])
        elif state == "publish:photo":
            photo = message.get("photo")
            if message.get("media_group_id"):
                self.say(chat, "Отправьте одно отдельное фото, без альбома.")
                return True
            if isinstance(photo, list) and photo:
                image = photo[-1]
                if not isinstance(image.get("file_id"), str) or not image.get("width") or not image.get("height") or image.get("file_size", 0) > 8_000_000:
                    self.say(chat, "Нужно фото до 8 МБ с корректными размерами.")
                    return True
                data["photo"] = {key: image[key] for key in ("file_id", "width", "height")}
            elif text != "Без фотографии":
                self.say(chat, "Пришлите фото или нажмите «Без фотографии».", ["Без фотографии"])
                return True
            self.destinations(chat, data, now)
        elif state == "publish:targets":
            mapping = {"Сайт": "site"}
            mapping.update({"Instagram @" + a["username"]: "instagram:" + str(a["slot"]) for a in self.accounts if a["ready"]})
            if text in mapping:
                target = mapping[text]
                if target.startswith("instagram:"):
                    photo = data.get("photo", {})
                    if not photo or not 0.8 <= photo["width"] / photo["height"] <= 1.91:
                        self.say(chat, "Для Instagram нужно фото от 4:5 до 1.91:1. Начните заново /publish с подходящим фото. На сайте можно разместить текущую заметку.", list(mapping) + ["Предпросмотр"])
                        return True
                if target in data["targets"]:
                    data["targets"].remove(target); data["labels"].remove(text)
                else:
                    data["targets"].append(target); data["labels"].append(text)
                self.destinations(chat, data, now)
            elif text == "Предпросмотр" and data["targets"]:
                self.save(chat, "confirm", data, now)
                self.say(chat, "ПРЕДПРОСМОТР\n\n" + data["text"] + "\n\nФотография: " + ("последняя принятая ботом; будет доступна по публичной ссылке на сайте, в том числе при отправке только в Instagram" if data.get("photo") else "нет") + "\nПлощадки: " + ", ".join(data["labels"]) + "\n\nПосле подтверждения материал станет публичным. Площадки отправляются независимо; результат будет в /publications.", ["Подтвердить публикацию", "Изменить текст", "Выбрать площадки"])
            else:
                self.destinations(chat, data, now)
        elif state == "publish:confirm":
            if text == "Изменить текст":
                self.save(chat, "edit", data, now)
                self.say(chat, "Пришлите новый текст (1–2200 символов). Фото и площадки сохранятся.")
            elif text == "Выбрать площадки":
                self.destinations(chat, data, now)
            elif text == "Подтвердить публикацию":
                identifier = uuid.uuid4().hex
                self.store.db.execute("INSERT INTO publication_jobs(id,chat_id,created,data) VALUES(?,?,?,?)", (identifier, chat, now, json.dumps(data, ensure_ascii=False)))
                self.store.db.executemany("INSERT INTO publication_deliveries(job_id,target) VALUES(?,?)", [(identifier, target) for target in data["targets"]])
                self.store.clear_session(chat)
                self.bot.reply(chat, "Публикация №" + identifier[:8] + " сохранена в очереди. Это ещё не подтверждение размещения; бот сообщит результат отдельно по каждой площадке.")
            else:
                self.say(chat, "Подтвердите публикацию или измените черновик.", ["Подтвердить публикацию", "Изменить текст", "Выбрать площадки"])
        elif state == "publish:edit":
            if not 1 <= len(text) <= 2200:
                self.say(chat, "Нужен текст от 1 до 2200 символов.")
            else:
                data["text"] = text
                self.destinations(chat, data, now)
        elif state == "publish:generating":
            self.say(chat, "Черновик готовится. Можно дождаться ответа или нажать «Отмена».")
        return True
