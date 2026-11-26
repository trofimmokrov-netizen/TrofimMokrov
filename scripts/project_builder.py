"""Render the project brief builder from the public service catalog."""

import json
from html import escape

from estimate import MINIMUM_ORDER, PRIMARY_SERVICES, _price_data


FEATURES = (
    ("catalog", "Каталог услуг или товаров"),
    ("request-form", "Форма заявки"),
    ("crm", "Передача заявок в CRM"),
    ("notifications", "Уведомления в Telegram"),
    ("account", "Личный кабинет"),
    ("reports", "Отчёты о работе системы"),
)
ADDITIONS = (
    ("content", "Подготовка текстов и визуалов"),
    ("integrations", "Подключение действующих сервисов"),
    ("launch", "Публикация и передача доступов"),
    ("support", "Обучение или сопровождение"),
)


def _service_choice(service):
    return f'''<label class="project-builder-choice">
 <input type="checkbox" name="project-service" value="{escape(service['id'])}">
 <span><strong>{escape(service['name'])}</strong><small>{escape(service['price'])} · {escape(service['unit'])}</small></span>
</label>'''


def _extra_choices(name, choices):
    return "".join(
        f'<label class="project-builder-choice"><input type="checkbox" name="{name}" value="{key}"><span>{label}</span></label>'
        for key, label in choices
    )


def _optional_group(name, label, choices):
    options = _extra_choices(f"project-{name}", choices)
    return f'''<details class="project-builder-more" id="project-more-{name}">
 <summary>{label}<span id="project-count-{name}"></span></summary>
 <fieldset>
  <legend class="sr-only">{label}</legend>
  <div class="project-builder-choices">{options}</div>
 </fieldset>
</details>'''


def project_builder(services, advance_terms):
    primary_services = {service["id"]: service for service in services if service["id"] in PRIMARY_SERVICES}
    primary = "".join(_service_choice(primary_services[key]) for key in PRIMARY_SERVICES if key in primary_services)
    other = "".join(_service_choice(service) for service in services if service["id"] not in primary_services)
    other_choices = f'''<details class="project-builder-more" id="project-more-service">
 <summary>Другие услуги<span id="project-count-service"></span></summary>
 <div class="project-builder-choices">{other}</div>
</details>''' if other else ""
    catalog = {"minimum": MINIMUM_ORDER, "services": [_price_data(service) for service in services]}
    payload = json.dumps(catalog, ensure_ascii=False).replace("<", "\\u003c")
    minimum = f"{MINIMUM_ORDER:,}".replace(",", " ")
    return f'''<div class="project-builder">
 <section class="page-heading project-builder-heading">
  <h1>Соберите бриф проекта</h1>
  <p class="lead">Выберите услуги и расскажите о задаче. Вы получите краткий бриф и предварительный расчёт для заявки.</p>
 </section>
 <p id="project-fallback">Посмотрите <a class="text-link" href="services.html">услуги и цены</a> или <a class="text-link" href="contact.html#request-form">оставьте заявку</a> с описанием задачи.</p>
 <div class="project-builder-workspace" id="project-workspace" hidden>
  <ol class="project-builder-progress" aria-label="Этапы брифа">
   <li aria-current="step">Услуги</li>
   <li>Задача</li>
   <li>Бриф и расчёт</li>
  </ol>
  <section class="project-builder-panel" data-project-step aria-labelledby="project-services-title">
   <h2 id="project-services-title" tabindex="-1">Услуги и функции</h2>
   <p>Отметьте подходящие услуги. Если вы ещё выбираете, переходите к описанию задачи.</p>
   <fieldset>
    <legend>Услуги из каталога</legend>
    <div class="project-builder-choices">{primary}</div>
    {other_choices}
   </fieldset>
   {_optional_group('feature', 'Желаемые функции', FEATURES)}
   {_optional_group('addition', 'Что ещё понадобится', ADDITIONS)}
  </section>
  <section class="project-builder-panel" data-project-step aria-labelledby="project-task-title" hidden>
   <h2 id="project-task-title" tabindex="-1">Расскажите о задаче</h2>
   <p>Заполните то, что уже известно. Детали можно уточнить после заявки.</p>
   <div class="project-builder-fields">
    <div>
     <label for="project-budget">Ориентир по бюджету</label>
     <input type="text" id="project-budget" maxlength="100" placeholder="Сумма или диапазон" autocomplete="off">
    </div>
    <div>
     <label for="project-timing">Желаемый срок</label>
     <input type="text" id="project-timing" maxlength="100" placeholder="Дата или удобный период" autocomplete="off">
    </div>
    <div class="project-builder-description">
     <label for="project-description">Коротко опишите задачу</label>
     <p id="project-description-hint">Что уже есть и каким должен быть результат? Оставьте личные данные, пароли и ключи доступа за пределами черновика. Контакты можно указать в форме заявки.</p>
     <textarea id="project-description" rows="6" maxlength="2000" aria-describedby="project-description-hint"></textarea>
    </div>
   </div>
  </section>
  <section class="project-builder-panel" data-project-step aria-labelledby="project-review-title" hidden>
   <h2 id="project-review-title" tabindex="-1">Бриф и расчёт</h2>
   <p id="project-review-empty" hidden>Добавьте услуги или описание задачи, чтобы подготовить бриф.</p>
   <div class="project-builder-review">
    <div id="project-brief" hidden>
     <h3>Ваша задача</h3>
     <dl class="project-builder-summary" id="project-brief-details"></dl>
    </div>
    <div class="project-builder-estimate">
     <h3>Ориентир по стоимости</h3>
     <dl class="project-builder-summary" id="project-price-breakdown" hidden></dl>
     <p id="project-price-empty">Выберите услуги, чтобы увидеть базовые цены.</p>
     <p class="project-builder-note" id="project-price-minimum" hidden>Если нужны только эти разовые работы, их можно дополнить до минимальной суммы заказа.</p>
     <p class="project-builder-note" id="project-price-terms">{escape(advance_terms)} Минимальный заказ — {minimum} ₽.</p>
     <p class="project-builder-note">Суммы рассчитаны по базовым объёмам каталога. Функции, дополнительные работы и сторонние подписки уточним при обсуждении.</p>
    </div>
   </div>
   <div class="project-builder-handoff">
    <p id="project-handoff-hint" hidden>Скопируйте бриф, откройте форму заявки и вставьте текст в описание задачи.</p>
    <div class="project-builder-actions">
     <button class="button secondary" id="project-copy" type="button" hidden>Скопировать бриф</button>
     <a class="button" id="project-request" href="contact.html#request-form">Открыть форму заявки</a>
    </div>
    <div id="project-manual-copy" hidden>
     <label for="project-brief-text">Текст брифа</label>
     <textarea id="project-brief-text" rows="6" readonly></textarea>
    </div>
    <p class="project-builder-note" id="project-copy-status" role="status"></p>
   </div>
  </section>
  <div class="project-builder-controls">
   <div class="project-builder-actions">
    <button class="button secondary" id="project-prev" type="button" hidden>Назад</button>
    <button class="button" id="project-next" type="button">Продолжить</button>
   </div>
   <button class="text-link project-builder-reset" id="project-reset" type="button" hidden>Очистить черновик</button>
  </div>
  <div class="project-builder-draft">
   <label><input id="project-keep-draft" type="checkbox"> Сохранить черновик для следующего визита</label>
   <p class="project-builder-note" id="project-draft-status" role="status">Пока отметка снята, черновик сохраняется в этой вкладке.</p>
  </div>
 </div>
 <script id="project-catalog" type="application/json">{payload}</script>
</div>'''
