"""Private-chat request workflow with durable updates and an outgoing queue.

Only TelegramAPI performs network I/O. Workflow tests can use a fake transport.
Tokens and message bodies are deliberately excluded from exception messages.
"""
from __future__ import annotations

import json
import http.client
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parents[1]
MAIN = {
    "keyboard": [["Услуги и цены", "Портфолио"], ["Оставить заявку", "Обо мне"], ["Перейти на сайт", "Контакты"], ["Помощник"]],
    "resize_keyboard": True,
}
CANCEL = {"keyboard": [["Отмена"]], "resize_keyboard": True}
CONFIRM = {
    "keyboard": [["Отправить заявку"], ["Изменить заявку", "Отмена"]],
    "resize_keyboard": True,
}


class TelegramRejected(Exception):
    """A parsed Telegram response explicitly rejected this API operation."""

    def __init__(self, code: int, retry_after: int = 0):
        self.code = code
        self.retry_after = min(max(int(retry_after), 1), 3600) if retry_after else 0
        super().__init__(f"Telegram отклонил запрос (код {code}).")


class DeliveryUnknown(Exception):
    """No trustworthy acknowledgement; a write might already have happened."""


class TelegramAPI:
    def __init__(self, token: str):
        if not token or any(ord(c) < 33 or ord(c) == 127 for c in token):
            raise ValueError("Задайте TELEGRAM_BOT_TOKEN в защищённых настройках процесса.")
        self._token = token
        self._next_call = 0.0
        self._chat_calls = {}

    def call(self, method: str, **payload: Any) -> Any:
        if method not in {"getMe", "getWebhookInfo", "getUpdates", "sendMessage", "setMyCommands"}:
            raise ValueError("Неизвестный метод Telegram API.")
        if method == "sendMessage":
            now = time.monotonic()
            chat = payload.get("chat_id")
            delay = max(self._next_call - now, self._chat_calls.get(chat, 0) - now, 0)
            if delay:
                time.sleep(delay)
            now = time.monotonic()
            self._next_call = now + 0.05
            self._chat_calls[chat] = now + 1.05
            if len(self._chat_calls) > 10000:
                self._chat_calls = {k: v for k, v in self._chat_calls.items() if v > now}
        try:
            # Never log this URL: Telegram's API puts the token in the path.
            request = Request(
                "https://api.telegram.org/bot" + self._token + "/" + method,
                data=json.dumps(payload, ensure_ascii=False).encode(),
                headers={"Content-Type": "application/json"},
            )
            with urlopen(request, timeout=45) as response:
                data = json.loads(response.read(2_000_000))
        except HTTPError as error:
            try:
                data = json.loads(error.read(100_000))
            except (ValueError, OSError, http.client.HTTPException):
                raise DeliveryUnknown("Нет подтверждённого ответа Telegram.") from None
            finally:
                error.close()
        except (URLError, OSError, ValueError, http.client.HTTPException):
            raise DeliveryUnknown("Не удалось получить подтверждение Telegram.") from None
        if not isinstance(data, dict):
            raise DeliveryUnknown("Некорректный ответ Telegram.")
        if data.get("ok") is not True:
            code = data.get("error_code")
            if not isinstance(code, int):
                raise DeliveryUnknown("Нет подтверждённого результата Telegram.")
            parameters = data.get("parameters") or {}
            retry = parameters.get("retry_after", 0) if isinstance(parameters, dict) else 0
            raise TelegramRejected(code, retry if isinstance(retry, int) else 0)
        if "result" not in data:
            raise DeliveryUnknown("В ответе Telegram отсутствует результат.")
        return data["result"]


class Store:
    def __init__(self, path: str | Path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        path.chmod(0o600)
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS sessions (
                chat_id INTEGER PRIMARY KEY, state TEXT NOT NULL,
                data TEXT NOT NULL, updated INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS updates (
                update_id INTEGER PRIMARY KEY, processed INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS settings (name TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS requests (
                id INTEGER PRIMARY KEY, update_id INTEGER UNIQUE NOT NULL,
                created INTEGER NOT NULL, chat_id INTEGER NOT NULL,
                username TEXT NOT NULL, service_id TEXT NOT NULL,
                details TEXT NOT NULL, contact TEXT NOT NULL, source TEXT NOT NULL,
                notification_status TEXT NOT NULL DEFAULT 'pending'
            );
            CREATE TABLE IF NOT EXISTS outbox (
                id INTEGER PRIMARY KEY, chat_id INTEGER NOT NULL,
                payload TEXT NOT NULL, request_id INTEGER,
                state TEXT NOT NULL DEFAULT 'pending', attempts INTEGER NOT NULL DEFAULT 0,
                available INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY(request_id) REFERENCES requests(id)
            );
        """)
        self.db.commit()

    def close(self):
        self.db.close()

    @contextmanager
    def transaction(self):
        with self.db:
            yield

    def session(self, chat_id: int, now: int):
        row = self.db.execute("SELECT * FROM sessions WHERE chat_id=?", (chat_id,)).fetchone()
        if row and row["updated"] > now - 86400:
            return row["state"], json.loads(row["data"])
        self.db.execute("DELETE FROM sessions WHERE chat_id=?", (chat_id,))
        return "", {}

    def save_session(self, chat_id, state, data, now):
        self.db.execute(
            "INSERT OR REPLACE INTO sessions VALUES (?,?,?,?)",
            (chat_id, state, json.dumps(data, ensure_ascii=False), now),
        )

    def clear_session(self, chat_id):
        self.db.execute("DELETE FROM sessions WHERE chat_id=?", (chat_id,))

    def enqueue(self, chat_id, text, keyboard=None, request_id=None):
        payload = {"chat_id": chat_id, "text": text, "link_preview_options": {"is_disabled": True}}
        if keyboard:
            payload["reply_markup"] = keyboard
        self.db.execute(
            "INSERT INTO outbox (chat_id,payload,request_id) VALUES (?,?,?)",
            (chat_id, json.dumps(payload, ensure_ascii=False), request_id),
        )

    @property
    def offset(self):
        row = self.db.execute("SELECT value FROM settings WHERE name='offset'").fetchone()
        return int(row[0]) if row else 0

    def recover(self):
        """A crash during sending is ambiguous; never resend it automatically."""
        with self.db:
            self.db.execute(
                "UPDATE requests SET notification_status='unknown' WHERE id IN "
                "(SELECT request_id FROM outbox WHERE state='sending')"
            )
            self.db.execute("UPDATE outbox SET state='unknown' WHERE state='sending'")

    def flush(self, api, now=None):
        now = int(time.time()) if now is None else now
        pause = self.db.execute("SELECT value FROM settings WHERE name='send_pause_until'").fetchone()
        if pause and int(pause[0]) > now:
            return
        rows = self.db.execute(
            "SELECT * FROM outbox WHERE state='pending' AND available<=? ORDER BY id LIMIT 50", (now,)
        ).fetchall()
        for row in rows:
            with self.db:
                self.db.execute("UPDATE outbox SET state='sending',attempts=attempts+1 WHERE id=?", (row["id"],))
            state = "sent"
            available = 0
            stop = False
            try:
                api.call("sendMessage", **json.loads(row["payload"]))
            except TelegramRejected as error:
                if error.code == 429 or (500 <= error.code < 600 and row["attempts"] < 4):
                    state = "pending"
                    available = now + (error.retry_after or min(5 * 2 ** row["attempts"], 60))
                    stop = True
                else:
                    state = "failed"
                    stop = error.code in (401, 409)
            except DeliveryUnknown:
                state = "unknown"
                stop = True
            with self.db:
                self.db.execute("UPDATE outbox SET state=?,available=? WHERE id=?", (state, available, row["id"]))
                if state == "pending":
                    self.db.execute("INSERT OR REPLACE INTO settings VALUES ('send_pause_until',?)", (str(available),))
                if row["request_id"] is not None:
                    self.db.execute(
                        "UPDATE requests SET notification_status=? WHERE id=?", (state, row["request_id"])
                    )
            if stop:
                break

    def counts(self):
        return {
            "requests": self.db.execute("SELECT COUNT(*) FROM requests").fetchone()[0],
            "notifications": dict(self.db.execute(
                "SELECT notification_status,COUNT(*) FROM requests GROUP BY notification_status"
            ).fetchall()),
            "outbox": dict(self.db.execute("SELECT state,COUNT(*) FROM outbox GROUP BY state").fetchall()),
        }


class Bot:
    def __init__(self, store: Store, owner_chat_id: int | None, content=ROOT / "content", clock=time.time, miniapp_url=None):
        self.store = store
        self.owner = owner_chat_id
        self.clock = clock
        self.site = json.loads((content / "site.json").read_text())
        self.services = json.loads((content / "services.json").read_text())
        self.by_id = {service["id"]: service for service in self.services}
        self.by_name = {service["name"]: service for service in self.services}
        self.website = self.site["base_url"].rstrip("/")
        self.miniapp_url = miniapp_url
        self.main = {"keyboard": list(MAIN["keyboard"]), "resize_keyboard": True}
        if miniapp_url:
            address = urlsplit(miniapp_url)
            if address.scheme != "https" or not address.hostname or address.username or address.password or address.query or address.fragment:
                raise ValueError("TELEGRAM_MINIAPP_URL должен быть публичным HTTPS-адресом без параметров и учётных данных.")
            self.main["keyboard"].insert(0, [{"text": "Открыть приложение", "web_app": {"url": miniapp_url}}])

    def reply(self, chat, text, keyboard=None):
        self.store.enqueue(chat, text, self.main if keyboard is None else keyboard)

    def start_request(self, chat, source, service_id=None):
        if not self.owner:
            self.store.clear_session(chat)
            self.reply(chat, "Приём заявок через бота ещё настраивается. Пока напишите Трофиму: " + self.site["telegram"])
            return
        data = {"source": source}
        if service_id in self.by_id:
            data["service_id"] = service_id
            self.store.save_session(chat, "details", data, int(self.clock()))
            self.reply(chat, "Услуга: " + self.by_id[service_id]["name"] + ".\nОпишите задачу и желаемый результат (10–1500 символов).", CANCEL)
        else:
            self.store.save_session(chat, "service", data, int(self.clock()))
            keyboard = {"keyboard": [[s["name"]] for s in self.services] + [["Другое", "Отмена"]], "resize_keyboard": True}
            self.reply(chat, "Какую задачу вы хотите обсудить? Выберите услугу.", keyboard)

    def process(self, update):
        identifier = update.get("update_id")
        if not isinstance(identifier, int):
            return
        now = int(self.clock())
        with self.store.transaction():
            if self.store.db.execute("SELECT 1 FROM updates WHERE update_id=?", (identifier,)).fetchone():
                return
            message = update.get("message")
            message = message if isinstance(message, dict) else {}
            chat = message.get("chat")
            chat = chat if isinstance(chat, dict) else {}
            user = message.get("from")
            user = user.copy() if isinstance(user, dict) else {}
            if not isinstance(user.get("username", ""), str):
                user.pop("username", None)
            chat_id = chat.get("id")
            # Public/group traffic must never create requests or reveal chat information.
            if chat.get("type") == "private" and isinstance(chat_id, int) and user.get("id") == chat_id and not user.get("is_bot"):
                self._message(identifier, chat_id, user, message, now)
            self.store.db.execute("INSERT INTO updates VALUES (?,?)", (identifier, now))
            self.store.db.execute(
                "INSERT OR REPLACE INTO settings VALUES ('offset',?)", (str(max(self.store.offset, identifier + 1)),)
            )
            self.store.db.execute("DELETE FROM sessions WHERE updated<?", (now - 86400,))
            self.store.db.execute("DELETE FROM updates WHERE processed<?", (now - 7 * 86400,))

    def _message(self, identifier, chat, user, message, now):
        if "web_app_data" in message:
            self._miniapp(identifier, chat, user, message["web_app_data"], now)
            return
        text = message.get("text", "")
        if not isinstance(text, str):
            text = ""
        text = text.strip()
        command = text.split(maxsplit=1)[0].split("@", 1)[0] if text else ""
        if command == "/id":
            self.reply(chat, f"Ваш chat ID: {chat}.\nВладелец указывает свой ID в TELEGRAM_OWNER_CHAT_ID.")
            return
        if command == "/help" or text == "Помощник":
            self.store.clear_session(chat)
            self.reply(chat, "Я помощник Трофима Мокрова по его услугам и сайту. Помогу посмотреть цены, выбрать направление и оформить заявку.\n\nНапишите, например: «Сколько стоит сайт?», «Нужна автоматизация», «Кто такой Трофим?» или выберите кнопку в меню.")
            return
        if command == "/about" or text == "Обо мне":
            self.store.clear_session(chat)
            self._about(chat)
            return
        if command in ("/site", "/portfolio") or text == "Перейти на сайт":
            self.store.clear_session(chat)
            portfolio = command == "/portfolio"
            self.reply(chat, "Проекты Трофима и описание работ." if portfolio else "Сайт Трофима Мокрова: услуги, проекты, статьи и контакты.",
                       {"inline_keyboard": [[{"text": "Открыть портфолио" if portfolio else "Перейти на сайт", "url": self.website + ("/portfolio.html" if portfolio else "/")}]]})
            return
        if command == "/status" and chat == self.owner:
            self.reply(chat, "Состояние приёма заявок: " + json.dumps(self.store.counts(), ensure_ascii=False))
            return
        if command == "/start":
            self.store.clear_session(chat)
            payload = text.split(maxsplit=1)[1] if len(text.split(maxsplit=1)) == 2 else ""
            if payload == "site":
                self.start_request(chat, "site")
                return
            if payload.startswith("service_") and payload[8:] in self.by_id:
                self.start_request(chat, payload, payload[8:])
                return
            if payload == "app" and self.miniapp_url:
                self.reply(chat, "Нажмите «Открыть приложение» на клавиатуре бота: там услуги, цены и удобная форма заявки. Если клавиатура скрыта, откройте её значком рядом с полем сообщения.")
                return
            self.reply(chat, "Здравствуйте! Я помощник Трофима Мокрова. Помогу выбрать услугу и оформить заявку. Спросите о сайте, ценах или автоматизации — либо выберите действие в меню.")
            return
        if command in ("/cancel", "/menu") or text == "Отмена":
            self.store.clear_session(chat)
            self.reply(chat, "Заявка не отправлена. Выберите действие в меню." if command != "/menu" else "Главное меню.")
            return
        if text in ("Услуги и цены", "Портфолио", "Контакты", "Сайт") or command == "/services":
            self.store.clear_session(chat)
            if text == "Услуги и цены" or command == "/services":
                self.reply(chat, "Услуги Трофима:\n\n" + "\n".join(s["name"] + " — " + s["price"] for s in self.services) + "\n\n" + self.website + "/services.html\nДля обсуждения нажмите «Оставить заявку».")
            elif text == "Портфолио":
                self.reply(chat, "Работы и описание моего вклада: " + self.website + "/portfolio.html")
            elif text == "Контакты":
                self.reply(chat, "Написать Трофиму: " + self.site["telegram"] + "\nПочта: " + self.site["email"])
            else:
                self.reply(chat, "Сайт Трофима Мокрова: " + self.website + "/")
            return
        if text == "Оставить заявку" or command == "/request":
            self.start_request(chat, "bot")
            return
        state, data = self.store.session(chat, now)
        if state == "service":
            service = self.by_name.get(text)
            if service:
                data["service_id"] = service["id"]
            elif text == "Другое":
                data["service_id"] = "other"
            else:
                self.reply(chat, "Выберите услугу кнопкой или нажмите «Отмена».", {"keyboard": [[s["name"]] for s in self.services] + [["Другое", "Отмена"]], "resize_keyboard": True})
                return
            self.store.save_session(chat, "details", data, now)
            self.reply(chat, "Опишите задачу и желаемый результат (10–1500 символов).", CANCEL)
        elif state == "details":
            if not 10 <= len(text) <= 1500:
                self.reply(chat, "Нужно текстовое описание от 10 до 1500 символов. Не указывайте пароли, ключи и платёжные данные.", CANCEL)
                return
            data["details"] = text
            self.store.save_session(chat, "contact", data, now)
            self.reply(chat, "Как с вами связаться? Напишите @имя в Telegram, email или телефон либо поделитесь своим контактом. Данные заявки получит Трофим для ответа по вашей задаче.", {"keyboard": [[{"text": "Поделиться своим контактом", "request_contact": True}], ["Отмена"]], "resize_keyboard": True})
        elif state == "contact":
            contact = message.get("contact")
            if isinstance(contact, dict):
                if contact.get("user_id") != user["id"]:
                    self.reply(chat, "Поделитесь только своим контактом или укажите способ связи текстом.", CANCEL)
                    return
                text = str(contact.get("phone_number", ""))
            if not 5 <= len(text) <= 160 or "\n" in text or not any(c.isalnum() for c in text):
                self.reply(chat, "Укажите контакт одной строкой (5–160 символов): @имя, email или телефон.", CANCEL)
                return
            data["contact"] = text
            self.store.save_session(chat, "confirm", data, now)
            service = self.by_id.get(data["service_id"], {"name": "Другое"})
            self.reply(chat, "Проверьте заявку:\n\nУслуга: " + service["name"] + "\nЗадача: " + data["details"] + "\nКонтакт: " + text + "\n\nНажимая «Отправить заявку», вы передаёте эти данные Трофиму для ответа по заявке.", CONFIRM)
        elif state == "confirm":
            if text == "Изменить заявку":
                self.store.save_session(chat, "details", {"service_id": data["service_id"], "source": data["source"]}, now)
                self.reply(chat, "Напишите новое описание задачи (10–1500 символов).", CANCEL)
                return
            if text != "Отправить заявку":
                self.reply(chat, "Проверьте данные и нажмите «Отправить заявку», «Изменить заявку» или «Отмена».", CONFIRM)
                return
            if not self.owner:
                self.store.clear_session(chat)
                self.reply(chat, "Приём заявок временно недоступен. Напишите Трофиму: " + self.site["telegram"])
                return
            count = self.store.db.execute("SELECT COUNT(*) FROM requests WHERE chat_id=? AND created>?", (chat, now - 86400)).fetchone()[0]
            if count >= 3:
                self.reply(chat, "За сутки уже оформлено три заявки. Для уточнений напишите Трофиму: " + self.site["telegram"])
                return
            cursor = self.store.db.execute(
                "INSERT INTO requests (update_id,created,chat_id,username,service_id,details,contact,source) VALUES (?,?,?,?,?,?,?,?)",
                (identifier, now, chat, str(user.get("username", ""))[:64], data["service_id"], data["details"], data["contact"], data["source"]),
            )
            request_id = cursor.lastrowid
            service = self.by_id.get(data["service_id"], {"name": "Другое"})
            self.store.enqueue(
                self.owner,
                f"Новая заявка №{request_id}\nУслуга: " + service["name"] + "\nЗадача: " + data["details"] + "\nКонтакт: " + data["contact"] + "\nTelegram: " + ("@" + user["username"] if user.get("username") else "публичное имя не указано") + "\nИсточник: " + data["source"],
                request_id=request_id,
            )
            self.reply(chat, f"Заявка №{request_id} сохранена и поставлена в очередь уведомлений Трофиму. Это не подтверждение прочтения. Если вопрос срочный: " + self.site["telegram"])
            self.store.clear_session(chat)
        else:
            self._assist(chat, text)

    def _about(self, chat):
        self.reply(chat, "Трофим Мокров помогает создавать сайты, применять AI-инструменты, работать с контентом и автоматизировать процессы. Сначала обсуждаются задача, объём и критерии результата.\n\nПодробности, подход и проекты — на сайте.",
                   {"inline_keyboard": [[{"text": "Узнать обо мне", "url": self.website + "/about.html"}, {"text": "Портфолио", "url": self.website + "/portfolio.html"}]]})

    def _assist(self, chat, text):
        """Answer from published site facts; never invent model-generated facts."""
        query = text.casefold().replace("ё", "е")
        if any(value in query for value in ("кто ты", "что умеешь", "чем поможешь")):
            self.reply(chat, "Я помощник Трофима по услугам, ценам и заявкам. Расскажу о сайте и работах, помогу подобрать направление. Например: «Нужен сайт для мастерской» или «Сколько стоит автоматизация?»")
            return
        if any(value in query for value in ("кто такой", "о трофиме", "обо мне", "чем занимается трофим")):
            self._about(chat)
            return
        if any(value in query for value in ("портфолио", "примеры работ", "посмотреть работы")):
            self.reply(chat, "Портфолио с задачами и описанием вклада Трофима: " + self.website + "/portfolio.html")
            return
        tags = {
            "ecosystem": ("инфраструктур", "экосистем"),
            "ai-agents": ("ai-агент", "ии-агент", "ai агент", "ии агент", "ассистент"),
            "automation": ("автоматизац", "crm", "бот"),
            "websites": ("сайт", "лендинг", "интернет-магазин"),
            "setup": ("компьютер", "ноутбук", "устройств"),
            "ai-content": ("изображен", "картинк", "фотограф"),
            "identity": ("логотип", "назван", "бренд", "стиль"),
            "social": ("соцсет", "посты", "контент"),
        }
        for service_id, words in tags.items():
            if service_id in self.by_id and any(word in query for word in words):
                service = self.by_id[service_id]
                summary = "\n".join("• " + item for item in service.get("includes", [])[:3])
                self.reply(chat, service["name"] + " — " + service["price"] + ("\n\n" + summary if summary else "") + "\n\nЭто ориентир для базового объёма. Точные условия согласуем после обсуждения задачи. Для продолжения нажмите «Оставить заявку» или «Открыть приложение».\n" + self.website + "/services.html#" + service_id)
                return
        if any(word in query for word in ("цен", "стоимост", "услуг")):
            self.reply(chat, "Направления и ориентиры:\n\n" + "\n".join(service["name"] + " — " + service["price"] for service in self.services) + "\n\nОпишите задачу — помогу выбрать направление.")
            return
        if any(word in query for word in ("контакт", "связаться", "написать трофиму")):
            self.reply(chat, "Написать Трофиму: " + self.site["telegram"] + "\nПочта: " + self.site["email"])
            return
        self.reply(chat, "Я помогу с услугами и заявками Трофима. Напишите, что нужно: сайт, автоматизация, AI-инструменты или контент. Для прямого общения: " + self.site["telegram"])

    def _miniapp(self, identifier, chat, user, envelope, now):
        """Keyboard Mini App data arrives via Telegram, bound to message.from.

        Fields themselves remain untrusted. No client-provided identity, chat ID,
        price or notification recipient is ever used.
        """
        raw = envelope.get("data") if isinstance(envelope, dict) else None
        try:
            if not isinstance(raw, str) or len(raw) > 4096 or len(raw.encode("utf-8")) > 4096:
                raise ValueError
            packet = json.loads(raw)
            if not isinstance(packet, dict) or type(packet.get("version")) is not int or packet["version"] != 1 or packet.get("type") != "request" or packet.get("consent") is not True:
                raise ValueError
            service_id, details, contact = (packet.get(name) for name in ("service_id", "details", "contact"))
            if not isinstance(service_id, str) or service_id not in {*self.by_id, "other"}:
                raise ValueError
            if not isinstance(details, str) or not 10 <= len(details.strip()) <= 1500:
                raise ValueError
            if not isinstance(contact, str) or not 5 <= len(contact.strip()) <= 160 or any(c in contact for c in "\r\n") or not any(c.isalnum() for c in contact):
                raise ValueError
        except (ValueError, TypeError, UnicodeError):
            self.reply(chat, "Не удалось принять заявку из приложения. Проверьте описание и контакт либо оформите заявку через меню бота.")
            return
        if not self.owner:
            self.reply(chat, "Приём заявок пока настраивается. Напишите Трофиму: " + self.site["telegram"])
            return
        data = {"service_id": service_id, "details": details.strip(), "contact": contact.strip(), "source": "miniapp"}
        self.store.save_session(chat, "confirm", data, now)
        # The Mini App's explicit submit button is the confirmation. Reuse the
        # same transactional intake, rate limit and notifications as chat forms.
        self._message(identifier, chat, user, {"text": "Отправить заявку"}, now)
