"""Render local, exportable utilities for the public tools page."""

import json
from html import escape

from estimate import MINIMUM_ORDER, _price_data


def _field(name, label, *, kind="text", hint="", **attrs):
    attributes = "".join(
        f" {key.replace('_', '-')}" + ("" if value is True else f'="{escape(str(value))}"')
        for key, value in attrs.items() if value is not False
    )
    control = (
        f'<textarea name="{name}" rows="3"{attributes}></textarea>'
        if kind == "textarea" else f'<input name="{name}" type="{kind}"{attributes}>'
    )
    note = f'<small>{escape(hint)}</small>' if hint else ""
    return f'<label class="tool-field"><span>{escape(label)}</span>{control}{note}</label>'


def _select(name, label, options):
    choices = "".join(
        f'<option value="{escape(str(value))}">{escape(text)}</option>' for value, text in options
    )
    return f'<label class="tool-field"><span>{escape(label)}</span><select name="{name}">{choices}</select></label>'


def _checklist(legend, name, choices):
    return f'<fieldset class="tool-choices"><legend>{escape(legend)}</legend>' + "".join(
        f'<label class="tool-choice"><input type="checkbox" name="{name}" value="{escape(value)}"><span>{text}</span></label>'
        for value, text in choices
    ) + "</fieldset>"


def _tool(slug, title, description, fields, action):
    return f'''<details class="digital-tool" id="tool-{slug}" data-tool="{slug}" name="digital-tools">
 <summary><span class="tool-summary"><span class="tool-name">{escape(title)}</span><span class="tool-description">{escape(description)}</span></span></summary>
 <p class="tool-unavailable" data-tool-unavailable>Чтобы использовать инструмент, включите JavaScript в браузере.</p>
 <form class="tool-form" autocomplete="off" hidden>
  <fieldset class="tool-inputs" disabled><legend class="sr-only">{escape(title)}</legend>
   {fields}
   <button class="button" type="submit">{escape(action)}</button>
  </fieldset>
  <div class="tool-result" data-tool-result hidden>
   <label class="tool-field"><span>Результат</span><textarea data-tool-output rows="9" readonly></textarea></label>
   <div class="tool-actions">
    <button class="button secondary" type="button" data-tool-copy>Скопировать</button>
    <button class="button secondary" type="button" data-tool-download>Скачать .txt</button>
   </div>
  </div>
  <p class="tool-status" role="status"></p>
 </form>
</details>'''


def digital_tools(services, advance_terms):
    """Return the tool list and the calculator's current catalog data."""
    tools = [
        _tool(
            "website-brief", "Бриф на сайт", "Соберите задачу, аудиторию, страницы и материалы для проекта.",
            _field("project", "Проект или компания", maxlength=120, required=True)
            + _field("audience", "Для кого сайт", maxlength=220, required=True)
            + _field("goal", "Что посетитель должен сделать", maxlength=220, required=True)
            + _field("pages", "Страницы или разделы", kind="textarea", maxlength=600)
            + _field("materials", "Готовые материалы", kind="textarea", maxlength=600)
            + _field("reference", "Ссылка на пример", kind="url", maxlength=1200, placeholder="https://example.com"),
            "Собрать бриф",
        ),
        _tool(
            "telegram-brief", "Бриф на Telegram-бота", "Опишите вход, основной сценарий и передачу обращения.",
            _field("project", "Проект или название бота", maxlength=120, required=True)
            + _field("audience", "Кто будет пользоваться ботом", maxlength=220, required=True)
            + _field("journey", "Главный сценарий", kind="textarea", maxlength=600, required=True, hint="Например, выбрать услугу, указать дату и получить подтверждение.")
            + _field("handoff", "Куда передаётся запрос", maxlength=220)
            + _field("integrations", "Сервисы и интеграции", maxlength=300)
            + _select("miniapp", "Мини-приложение", [("Обсудить на старте", "Обсудить на старте"), ("Нужно", "Нужно"), ("Для запуска хватит бота", "Для запуска хватит бота")]),
            "Собрать бриф",
        ),
        _tool(
            "content-plan", "План публикаций", "Получите темы, форматы и вопросы для редакционного плана.",
            _field("topic", "Тема или продукт", maxlength=150, required=True)
            + _field("audience", "Для кого публикуете", maxlength=150, required=True)
            + _select("goal", "Задача публикаций", [("introduce", "Познакомить с темой"), ("explain", "Объяснить выбор и процесс"), ("requests", "Получить обращения")])
            + _select("channel", "Площадка", [("telegram", "Telegram"), ("vk", "ВКонтакте"), ("instagram", "Instagram"), ("website", "Сайт")])
            + _select("weeks", "Период", [(1, "1 неделя"), (2, "2 недели"), (4, "4 недели")])
            + _select("frequency", "Публикаций в неделю", [(1, "1 публикация"), (2, "2 публикации"), (3, "3 публикации")]),
            "Собрать план",
        ),
        _tool(
            "budget", "Калькулятор бюджета", "Посчитайте работы по каталогу и сравните разовые и ежемесячные расходы.",
            _checklist("Выберите услуги", "service", [
                (service["id"], f"<strong>{escape(service['name'])}</strong><small>{escape(service['price'])} · {escape(service['unit'])}</small>")
                for service in services
            ])
            + _field("images", "Количество AI-изображений", kind="number", min=1, max=1000, step=1, value=1, required=True, hint="Учитывается, если выбрана услуга «AI-изображения».")
            + _field("months", "Месяцев сопровождения", kind="number", min=1, max=60, step=1, value=1, required=True, hint="Учитывается для услуг с ценой за месяц."),
            "Рассчитать бюджет",
        ),
        _tool(
            "launch-checklist", "Чек-лист запуска сайта", "Отметьте готовые пункты и сохраните список перед публикацией.",
            _field("project", "Название сайта", maxlength=120)
            + _checklist("Что уже проверено", "done", [
                ("mobile", "Основной путь на телефоне и компьютере"),
                ("content", "Тексты, цены, контакты и права на изображения"),
                ("forms", "Формы, внешние ссылки и подтверждение заявки"),
                ("search", "Title, description, канонические URL и карта сайта"),
                ("domain", "Домен, HTTPS и перенаправления старых адресов"),
                ("tracking", "Аналитика и настройки согласия, если они используются"),
                ("backup", "Резервная версия и порядок отката"),
                ("owner", "Доступ владельца и ответственный за обновления"),
            ]),
            "Собрать чек-лист",
        ),
        _tool(
            "crm-checklist", "Чек-лист настройки CRM", "Проверьте входящие заявки, назначение, уведомления и отчёты.",
            _field("project", "Название воронки или проекта", maxlength=120)
            + _checklist("Что уже проверено", "done", [
                ("intake", "Источники заявок и обязательные поля"),
                ("mapping", "Передача полей в нужную карточку"),
                ("stages", "Стадии и ответственность за переходы"),
                ("routing", "Назначение заявки и резервная очередь"),
                ("dupes", "Повторные обращения, дубли и повторная отправка"),
                ("alerts", "Уведомления в рабочее время и замещение"),
                ("access", "Роли, доступ к данным и порядок хранения"),
                ("reports", "Отчёт по заявкам и контрольный сценарий"),
            ]),
            "Собрать чек-лист",
        ),
        _tool(
            "seo", "Шаблоны title и description", "Подготовьте варианты метатегов для услуги, статьи или проекта.",
            _select("pageType", "Тип страницы", [("service", "Услуга"), ("article", "Статья"), ("case", "Проект")])
            + _field("topic", "Тема страницы", maxlength=110, required=True)
            + _field("benefit", "Что читатель узнает или сможет сделать", maxlength=175, required=True, hint="Напишите коротким предложением. Например, сравните два способа подключения.")
            + _field("brand", "Название бренда", maxlength=60)
            + _field("region", "Город или регион", maxlength=60, hint="Заполняйте для услуги, доступной в этом регионе."),
            "Подготовить метатеги",
        ),
        _tool(
            "utm", "Генератор UTM-ссылок", "Добавьте метки кампании. Другие параметры и якорь сохраняются.",
            _field("url", "Адрес страницы", kind="url", maxlength=1500, required=True, placeholder="https://example.com/")
            + _field("utm_source", "Источник · utm_source", maxlength=120, required=True, placeholder="telegram")
            + _field("utm_medium", "Канал продвижения · utm_medium", maxlength=120, required=True, placeholder="social")
            + _field("utm_campaign", "Кампания · utm_campaign", maxlength=120, required=True, placeholder="spring_launch")
            + _field("utm_content", "Вариант объявления · utm_content", maxlength=120)
            + _field("utm_term", "Поисковая фраза · utm_term", maxlength=120),
            "Собрать UTM-ссылку",
        ),
        _tool(
            "telegram-link", "Генератор ссылок Telegram", "Соберите ссылку на профиль, старт бота или его мини-приложение.",
            _field("username", "Имя в Telegram", maxlength=33, required=True, placeholder="@example_bot")
            + _select("mode", "Что открыть", [("start", "Бот"), ("profile", "Профиль или канал"), ("app", "Мини-приложение")])
            + _field("payload", "Параметр запуска", maxlength=512, hint="Латиница, цифры, подчёркивание и дефис. До 64 символов для бота и до 512 для мини-приложения.")
            + _field("appName", "Короткое имя мини-приложения", maxlength=32, hint="Оставьте поле пустым для основного Mini App."),
            "Собрать ссылку",
        ),
        _tool(
            "automation-time", "Экономия времени на автоматизации", "Оцените еженедельный эффект и срок возврата времени на настройку.",
            _field("before", "Минут на один повтор сейчас", kind="number", min=0, max=10080, step="0.1", required=True)
            + _field("after", "Минут на повтор после внедрения", kind="number", min=0, max=10080, step="0.1", required=True, hint="Учтите ручную проверку результата.")
            + _field("frequency", "Повторов в неделю", kind="number", min=1, max=10000, step=1, required=True)
            + _field("maintenance", "Минут на обслуживание в неделю", kind="number", min=0, max=10080, step="0.1", value=0, required=True)
            + _field("setup", "Часов на настройку и тестирование", kind="number", min=0, max=10000, step="0.1", value=0, required=True),
            "Рассчитать время",
        ),
    ]

    catalog = {
        "minimum": MINIMUM_ORDER,
        "advanceTerms": advance_terms,
        "services": [_price_data(service) for service in services],
    }
    catalog_json = json.dumps(catalog, ensure_ascii=False).replace("<", "\\u003c")
    return f'''<section class="digital-tools" aria-labelledby="digital-tools-title">
 <div class="tools-intro"><h2 id="digital-tools-title">Инструменты для проекта</h2><p>Введённые данные остаются в этой вкладке. Для черновиков используйте рабочие примеры без персональных данных.</p></div>
 <div class="tools-list">{"".join(tools)}</div>
 <script id="digital-tools-catalog" type="application/json">{catalog_json}</script>
</section>'''
