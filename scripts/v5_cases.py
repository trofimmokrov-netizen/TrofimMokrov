"""Render the ecosystem guide and evidence-backed project case pages."""

from html import escape as e
import re
from urllib.parse import quote


# The initial state comes from the repository. Optional nodes describe possible project choices.
ECOSYSTEM_GROUPS = (
    ("Что видит посетитель", (
        ("sites", "Сайты", True, "Страницы услуг, портфолио и библиотека помогают разобраться в предложении. На странице контактов размещена форма Битрикс24.", "Услуги и цены", "services.html"),
        ("telegram", "Telegram", True, "Сайт содержит ссылки на личный Telegram, бота TrofimAI и мини-приложения из портфолио. Бот и приложения открываются в клиенте Telegram.", "Telegram-проекты", "portfolio.html#telegram-projects"),
        ("mini-apps", "Mini Apps", True, "В TrofimAI внутри Telegram доступны каталог услуг и контакты. Форма заявки и виджет чата загружаются из Битрикс24.", "Открыть TrofimAI", "https://t.me/TrofimAI_bot?start=app"),
    )),
    ("Как обрабатываются заявки", (
        ("bitrix24", "Битрикс24", True, "Контактная страница и Mini App используют встроенные форму и виджет Битрикс24. Поля, получатели и доступные каналы настраиваются в Битрикс24.", "Форма на сайте", "contact.html#request-form"),
        ("crm", "CRM", False, "В клиентском проекте CRM может хранить обращения, назначать ответственных и показывать этапы работы. Настройку ведут от полей заявки и правил обработки.", "Статьи о заявках", "articles.html#topic-crm"),
        ("automation", "Автоматизация", False, "Сценарий может передавать данные между сервисами, отправлять уведомление или запускать обработку по расписанию. Условия повторов и ручного восстановления согласуют заранее.", "Автоматизация процессов", "services.html#automation"),
        ("ai-agents", "AI-агенты", False, "Агент может подготовить черновик ответа или материалы для публикации. Объём доступа и действия для проверки человеком определяются задачей.", "AI-агенты для контента", "services.html#ai-agents"),
    )),
    ("Где работает проект", (
        ("github", "GitHub", True, "В GitHub хранятся исходники и история изменений. Статические файлы этого сайта публикуются через GitHub Pages.", "Кейс этого сайта", "cases/personal-site.html"),
        ("supabase", "Supabase", False, "Supabase можно использовать, когда приложению нужна база данных, учётные записи или правила доступа к записям. Необходимость этих функций определяет выбор платформы.", "Как спроектировать данные", "articles/supabase-table-model-and-migrations.html"),
        ("vercel", "Vercel", False, "Vercel можно рассмотреть для публикации сайта или размещения веб-приложения с серверными функциями. Требования к сборке, конфигурации и размещению уточняют по проекту.", "Как проверить публикацию", "articles/vercel-preview-production-checks.html"),
    )),
)


def ecosystem_page():
    rows = []
    panels = []
    for group_title, nodes in ECOSYSTEM_GROUPS:
        buttons = []
        for slug, title, current, description, label, destination in nodes:
            state = "current" if current else "option"
            status = "На этом сайте" if current else "Подключение по задаче"
            buttons.append(f'''<button type="button" class="eco-node" data-eco-node="{slug}" data-eco-state="{state}"
 aria-controls="eco-{slug}" aria-pressed="false">{e(title)}</button>''')
            panels.append(f'''<article class="eco-panel" id="eco-{slug}" data-eco-panel="{slug}">
 <p class="eco-panel-status eco-panel-status--{state}">{status}</p>
 <h2>{e(title)}</h2><p>{e(description)}</p>
 <a class="text-link action-link" href="{e(destination, quote=True)}">{e(label)} ↗</a>
</article>''')
        rows.append(f'''<div class="eco-stage">
 <h3>{e(group_title)}</h3>
 <div class="eco-buttons" role="group" aria-label="{e(group_title, quote=True)}">{''.join(buttons)}</div>
</div>''')
    return f'''<section class="page-heading eco-heading">
 <h1>Цифровая экосистема</h1>
 <p class="lead">Путь от первого знакомства с услугой до заявки. Посмотрите, какие инструменты уже использует этот сайт и что можно подключить под задачу.</p>
</section>
<div class="eco-layout" data-eco>
 <section class="eco-map" data-eco-controls aria-labelledby="eco-map-title" hidden>
  <h2 id="eco-map-title">Карта инструментов</h2>
  <ul class="eco-legend">
   <li><span class="eco-key eco-key--current" aria-hidden="true"></span>В текущем сайте</li>
   <li><span class="eco-key" aria-hidden="true"></span>По задаче проекта</li>
  </ul>
  <div class="eco-stages">{''.join(rows)}</div>
  <p class="sr-only" data-eco-status role="status"></p>
 </section>
 <div class="eco-panels" aria-label="Описание инструментов">{''.join(panels)}</div>
</div>
<section class="section eco-examples" aria-labelledby="eco-examples-title">
 <h2 id="eco-examples-title">Как это может работать</h2>
 <div class="eco-examples-grid">
  <article>
   <h3>Посетитель оставляет заявку</h3>
   <p>Читает условия на сайте и открывает форму Битрикс24. Поля и направление обращения выбирают при настройке формы.</p>
   <a class="text-link action-link" href="contact.html#request-form">Открыть форму ↗</a>
  </article>
  <article>
   <h3>Клиент выбирает в Telegram</h3>
   <p>Знакомится с каталогом внутри мини-приложения, затем открывает предусмотренную форму или пишет мастеру.</p>
   <a class="text-link action-link" href="portfolio.html#telegram-projects">Посмотреть проекты ↗</a>
  </article>
  <article>
   <h3>Команда обрабатывает обращения</h3>
   <p>Согласует этапы в CRM и правила уведомлений. При необходимости подключает автоматизацию отдельных действий.</p>
   <a class="text-link action-link" href="services.html#business-system">Об услуге ↗</a>
  </article>
 </div>
</section>'''


TELEGRAM_CASE_SLUGS = {
    "deviceworkshop_bot": "device-workshop",
    "drevesny3d_bot": "drevesny-3d",
    "aikbaseorder_bot": "aik-base",
}


def project_case_slug(project):
    return project["slug"]


def telegram_case_slug(project):
    username = project["handle"].lower()
    return TELEGRAM_CASE_SLUGS.get(username) or re.sub("[^a-z0-9-]+", "-", username).strip("-")


CASE_ROUTES = {
    "ksusha-epoxy": (
        "Открыть коллекцию столов и посмотреть, как дерево сочетается с эпоксидной смолой.",
        "Перейти в галерею, чтобы рассмотреть отдельные работы.",
        "Узнать, как связаться с мастерской для обсуждения проекта.",
    ),
    "drevesniy-zamysel": (
        "Подготовить информацию о мастерской для цифровых площадок.",
        "Поддерживать выпуск постов во ВКонтакте и MAX.",
        "Уточнять представление мастерской на картах и помогать с настройкой рабочих инструментов.",
    ),
    "personal-site": (
        "На главной выбрать направление работы и посмотреть стартовые условия.",
        "Сравнить услуги, открыть проекты или найти ответ в библиотеке.",
        "Перейти к форме Битрикс24, написать в Telegram или открыть Mini App.",
    ),
}

TELEGRAM_DETAILS = {
    "device-workshop": (
        "Каталог ремонта в Telegram",
        "Собрать информацию о ремонте техники в одном интерфейсе. Посетитель может посмотреть услуги и цены перед обращением к мастеру.",
        "В мини-приложении есть каталог, цены, личный кабинет и возможность связаться с мастером. Отдельно доступен сайт мастерской Тиграна.",
        "Карточки услуг помогают сформулировать вопрос по конкретной работе. В приложении можно перейти от просмотра каталога к контакту с мастером.",
        (
            "Открыть каталог из бота Device Workshop.",
            "Выбрать направление ремонта и посмотреть цену в каталоге.",
            "Перейти к контакту с мастером для уточнения задачи.",
        ),
    ),
    "drevesny-3d": (
        "Коллекция и 3D-конструктор в Telegram",
        "Помочь посетителю познакомиться с коллекцией мастерской и рассмотреть изделие в контексте комнаты до общения с Ксенией.",
        "В мини-приложении представлены коллекция, 3D-конструктор и примерка предметов в комнате. Контакт с Ксенией доступен в приложении.",
        "Посетитель может показать выбранное изделие и обсудить его с Ксенией. Из карточки проекта также можно перейти на сайт мастерской.",
        (
            "Открыть коллекцию мастерской.",
            "Рассмотреть предмет в конструкторе и попробовать его в комнате.",
            "Связаться с Ксенией и обсудить выбранное изделие.",
        ),
    ),
    "aik-base": (
        "Работы по металлу и подготовка заявки",
        "Помочь заказчику посмотреть примеры работ по сварке и металлу и подготовить обращение к мастеру.",
        "В мини-приложении есть подборка работ, 3D-конструктор, примерка через камеру и подготовка заявки для отправки мастеру.",
        "Между просмотром работ и обращением есть возможность рассмотреть вариант через конструктор и камеру. Детали выполнения работ можно обсудить с мастером.",
        (
            "Посмотреть примеры сварочных и металлических работ.",
            "Открыть 3D-конструктор или примерку через камеру.",
            "Подготовить описание задачи для обращения к мастеру.",
        ),
    ),
}


def case_body(title, description, kind, portfolio_anchor, actions, sections, route=(), illustration=""):
    actions_html = "".join(
        f'<a class="button{"" if index == 0 else " secondary"}" href="{e(url, quote=True)}">{e(label)} ↗</a>'
        for index, (label, url) in enumerate(actions)
    )
    contents = "".join(
        f'<li><a href="#case-{slug}">{e(heading)}</a></li>' for slug, heading, _ in sections
    )
    blocks = []
    for slug, heading, text in sections:
        route_html = ""
        if slug == "work" and route:
            steps = "".join(f'<li>{e(step)}</li>' for step in route)
            route_html = f'<ol class="case-route">{steps}</ol>'
        blocks.append(f'''<section id="case-{slug}" class="case-section" aria-labelledby="case-{slug}-title">
 <h2 id="case-{slug}-title">{e(heading)}</h2>
 <p>{e(text)}</p>{route_html}
</section>''')
    return f'''<nav class="breadcrumbs" aria-label="Путь к проекту">
 <a href="../portfolio.html#{e(portfolio_anchor, quote=True)}">Портфолио</a><span aria-current="page"> / {e(title)}</span>
</nav>
<section class="page-heading case-heading">
 <span class="case-kind">{e(kind)}</span>
 <h1>{e(title)}</h1><p class="lead">{e(description)}</p>
 <div class="case-actions">{actions_html}</div>
</section>
{illustration}
<div class="case-layout">
 <nav class="case-index" aria-label="Содержание кейса">
  <h2>В этом кейсе</h2><ol>{contents}</ol>
 </nav>
 <div class="case-sections">{''.join(blocks)}</div>
</div>
<section class="case-footer" aria-label="Дальнейшие действия">
 <a class="text-link action-link" href="../portfolio.html">Все проекты ↗</a>
 <a class="text-link action-link" href="../ecosystem.html">Как связаны инструменты ↗</a>
</section>'''


def case_pages(projects, telegram_projects):
    for project in projects:
        slug = project_case_slug(project)
        title = project["title"]
        description = project["description"]
        service_slug = "ecosystem" if slug == "drevesniy-zamysel" else "websites"
        actions = []
        if project.get("url"):
            actions.append((project.get("url_label", "Открыть проект"), project["url"]))
        if slug == "personal-site":
            actions.append(("Открыть главную", "../index.html"))
        actions.append(("Посмотреть услугу", f"../services.html#{service_slug}"))
        illustration = ""
        if project.get("image"):
            image_url = e("../" + project["image"], quote=True)
            alt = e(project["alt"], quote=True)
            illustration = f'''<figure class="case-media">
 <img src="{image_url}" width="1440" height="1050" loading="lazy" decoding="async" alt="{alt}">
</figure>'''
        sections = (
            ("task", "Задача", project["task"]),
            ("work", "Что сделано", project["work"]),
            ("tools", "Инструменты", project["tools"]),
            ("result", "Результат", project["result"]),
        )
        body = case_body(title, description, project["kind"], project["slug"], actions, sections,
                         CASE_ROUTES.get(slug, ()), illustration)
        yield slug, title, description, body

    for project in telegram_projects:
        slug = telegram_case_slug(project)
        title = project["name"]
        description = project["description"]
        extras = TELEGRAM_DETAILS.get(slug)
        if extras:
            subject, task, work, result, route = extras
            sections = (
                ("task", "Задача", task),
                ("work", "Возможности приложения", work),
                ("result", "Как им пользоваться", result),
            )
        else:
            subject = "Мини-приложение"
            sections = (("work", "Возможности приложения", description),)
            route = ()
        profile = "https://t.me/" + quote(project["handle"], safe="")
        actions = [("Открыть в Telegram", profile)]
        if project.get("website"):
            actions.append((project["website_label"], project["website"]))
        actions.append(("О создании Mini Apps", "../services.html#telegram-bots"))
        body = case_body(title, description, "Telegram Mini App", "bot-" + project["handle"].lower(),
                         actions, sections, route)
        yield slug, title + " — " + subject, description, body
