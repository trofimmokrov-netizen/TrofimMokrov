"""Explicitly update Telegram's public bot profile, then verify it."""
import os
import sys

from .bot import DeliveryUnknown, TelegramAPI, TelegramRejected


SHORT_DESCRIPTION = (
    "Помощник Трофима Мокрова: сайты, AI и автоматизация. Услуги, цены и заявки."
)
DESCRIPTION = (
    "Трофим AI — помощник Трофима Мокрова.\n\n"
    "Помогу выбрать услугу, узнать стоимость и оставить заявку: сайты, "
    "AI-инструменты, контент и автоматизация.\n\n"
    "В мини-приложении — каталог и удобная форма заявки. "
    "В меню — сайт, портфолио, информация о Трофиме и контакты.\n\n"
    "Нажмите «Запустить», чтобы начать."
)


def configure_profile(api):
    identity = api.call("getMe")
    if not isinstance(identity, dict) or not isinstance(identity.get("username"), str) or identity["username"].lower() != "trofimai_bot":
        raise ValueError("Ожидается токен @TrofimAI_bot.")
    for language in ("", "ru"):
        api.call("setMyDescription", description=DESCRIPTION, language_code=language)
        api.call("setMyShortDescription", short_description=SHORT_DESCRIPTION, language_code=language)
        description = api.call("getMyDescription", language_code=language)
        short = api.call("getMyShortDescription", language_code=language)
        if description.get("description") != DESCRIPTION or short.get("short_description") != SHORT_DESCRIPTION:
            raise ValueError("Telegram не подтвердил сохранение описания.")


def main():
    try:
        configure_profile(TelegramAPI(os.environ.get("TELEGRAM_BOT_TOKEN", "")))
        print("Описание и раздел «О боте» сохранены в Telegram и проверены (по умолчанию и русский).")
        return 0
    except (ValueError, TelegramRejected, DeliveryUnknown) as error:
        print(str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
