"""Run a single long-polling worker; no public HTTP endpoint is opened."""
from __future__ import annotations

import argparse
import fcntl
import json
import os
import sys
import time
from pathlib import Path

from .bot import Bot, DeliveryUnknown, Store, TelegramAPI, TelegramRejected


COMMANDS = [
    {"command": "start", "description": "Знакомство и главное меню"},
    {"command": "services", "description": "Услуги и цены"},
    {"command": "about", "description": "О Трофиме"},
    {"command": "site", "description": "Перейти на сайт"},
    {"command": "portfolio", "description": "Портфолио"},
    {"command": "help", "description": "Помощник по услугам"},
    {"command": "request", "description": "Оставить заявку"},
    {"command": "pilot", "description": "Обсудить пробную задачу"},
    {"command": "menu", "description": "Главное меню"},
    {"command": "cancel", "description": "Отменить оформление заявки"},
    {"command": "id", "description": "Узнать свой chat ID"},
]


def main():
    parser = argparse.ArgumentParser(description="TrofimAI: меню, заявки и уведомления в Telegram")
    parser.add_argument("--db", default=os.environ.get("TROFIM_BOT_DB", str(Path.home() / ".local/share/trofimai/requests.sqlite3")))
    parser.add_argument("--check", action="store_true", help="Проверить доступ к боту, не получать обновления и не отправлять сообщения")
    parser.add_argument("--status", action="store_true", help="Показать только локальные счётчики, без сети и персональных данных")
    args = parser.parse_args()
    db = Path(args.db).expanduser().resolve()
    root = Path(__file__).resolve().parents[1]
    if db.is_relative_to(root):
        parser.error("Храните базу заявок вне каталога публичного сайта.")
    db.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    lock = db.with_suffix(db.suffix + ".lock").open("a")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        parser.exit(1, "Для этой базы уже работает процесс бота.\n")
    store = Store(db)
    try:
        if args.status:
            print(json.dumps(store.counts(), ensure_ascii=False))
            return 0
        token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
        owner_value = os.environ.get("TELEGRAM_OWNER_CHAT_ID", "").strip()
        if owner_value and (not owner_value.lstrip("-").isdigit() or int(owner_value) == 0):
            raise ValueError("TELEGRAM_OWNER_CHAT_ID должен быть ненулевым числовым chat ID.")
        owner = int(owner_value) if owner_value else None
        api = TelegramAPI(token)
        me = api.call("getMe")
        if not isinstance(me, dict) or not isinstance(me.get("username"), str) or me["username"].lower() != "trofimai_bot":
            raise ValueError("Токен принадлежит другому боту. Ожидается @TrofimAI_bot.")
        webhook = api.call("getWebhookInfo")
        if not isinstance(webhook, dict):
            raise ValueError("Не удалось проверить режим получения обновлений.")
        if webhook.get("url"):
            raise ValueError("У бота уже установлен webhook. Он не изменён; сначала определите, где работает существующая интеграция.")
        print("Подключение к @TrofimAI_bot подтверждено; webhook отсутствует.", flush=True)
        if not owner:
            print("Получатель заявок не настроен. Доступны меню и /id; оформление заявок отключено.", flush=True)
        if args.check:
            return 0 if owner else 2
        api.call("setMyCommands", commands=COMMANDS)
        store.recover()
        bot = Bot(store, owner, miniapp_url=os.environ.get("TELEGRAM_MINIAPP_URL"))
        print("Меню зарегистрировано. Запущен один процесс long polling.", flush=True)
        while True:
            store.flush(api)
            try:
                updates = api.call("getUpdates", offset=store.offset, timeout=25, limit=50, allowed_updates=["message"])
                if not isinstance(updates, list):
                    raise DeliveryUnknown("Некорректный список обновлений.")
                for update in updates:
                    if isinstance(update, dict):
                        bot.process(update)
                store.flush(api)
            except DeliveryUnknown:
                print("Нет подтверждённого ответа Telegram; чтение обновлений будет повторено. Неопределённые отправки не повторяются.", file=sys.stderr, flush=True)
                time.sleep(5)
            except TelegramRejected as error:
                if error.code == 429:
                    time.sleep(min(error.retry_after or 30, 60))
                elif 500 <= error.code < 600:
                    print("Временная ошибка Telegram при чтении обновлений; повтор через 5 секунд.", file=sys.stderr, flush=True)
                    time.sleep(5)
                else:
                    raise
    except KeyboardInterrupt:
        return 0
    except (ValueError, DeliveryUnknown, TelegramRejected) as error:
        print(str(error), file=sys.stderr)
        return 1
    finally:
        store.close()
        lock.close()


if __name__ == "__main__":
    raise SystemExit(main())
