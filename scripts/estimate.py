"""Generate the service calculator and its request handoff."""

import json
import re
from html import escape


MINIMUM_ORDER = 5000
PRIMARY_SERVICES = (
    "websites",
    "telegram-bots",
    "business-system",
    "automation",
    "ai-agents",
    "social",
)


def _price_data(service):
    rate = re.fullmatch(r"(от )?([0-9][0-9 \u00a0\u202f]*) ₽", service["price"])
    amount = int(re.sub(r"\s", "", rate[2])) if rate else None
    monthly = "в месяц" in service["unit"].casefold()
    return {
        "id": service["id"],
        "name": service["name"],
        "price": service["price"],
        "unit": service["unit"],
        "amount": amount,
        "monthly": monthly,
        "startingAt": bool(rate and rate[1]),
    }


def _catalog_markup(services):
    catalog = {"minimum": MINIMUM_ORDER, "services": [_price_data(service) for service in services]}
    payload = json.dumps(catalog, ensure_ascii=False).replace("<", "\\u003c")
    return f'<script id="estimate-catalog" type="application/json">{payload}</script>'


def _choice(service):
    return f'''<li><label class="estimate-choice">
 <input type="checkbox" name="estimate-service" value="{escape(service['id'])}">
 <span><strong>{escape(service['name'])}</strong><small>{escape(service['price'])} · {escape(service['unit'])}</small></span>
</label></li>'''


def estimate_section(services, advance_terms, script_url):
    by_id = {service["id"]: service for service in services}
    primary = "".join(_choice(by_id[key]) for key in PRIMARY_SERVICES if key in by_id)
    other = "".join(_choice(service) for service in services if service["id"] not in PRIMARY_SERVICES)
    more = f'''<details id="estimate-more" class="estimate-more"><summary>Другие услуги<span id="estimate-more-count"></span></summary>
 <ul class="estimate-choices">{other}</ul>
</details>''' if other else ""
    minimum = f"{MINIMUM_ORDER:,}".replace(",", " ")
    return f'''<section class="section estimate" id="estimate" aria-labelledby="estimate-title" data-estimate-script="{escape(script_url)}">
 <div class="section-head"><h2 id="estimate-title">Предварительная стоимость</h2><p>Выберите услуги, чтобы увидеть разовые и ежемесячные расходы отдельно.</p></div>
 <p id="estimate-fallback">Посмотрите <a class="text-link" href="services.html">услуги и цены</a> или <a class="text-link" href="contact.html#request-form">оставьте заявку</a>, чтобы обсудить свою задачу.</p>
 <div id="estimate-calculator" class="estimate-layout" hidden>
  <fieldset class="estimate-picker">
   <legend>Услуги для вашего проекта</legend>
   <ul class="estimate-choices">{primary}</ul>
   {more}
  </fieldset>
  <div class="estimate-summary">
   <h3>Ваш расчёт</h3>
   <p id="estimate-empty">Выберите хотя бы одну услугу.</p>
   <dl id="estimate-totals" class="estimate-totals" hidden></dl>
   <p id="estimate-minimum" class="estimate-minimum" hidden></p>
   <p id="estimate-announcement" class="sr-only" role="status"></p>
   <p class="estimate-terms">{escape(advance_terms)} Минимальный заказ — {minimum} ₽.</p>
   <p class="estimate-note">Расчёт основан на базовых объёмах из каталога. Итоговую стоимость согласуем после обсуждения. Подписки и сторонние сервисы при необходимости оплачиваются отдельно.</p>
   <div class="estimate-actions">
    <a id="estimate-request" class="button" href="contact.html#request-form">К заявке</a>
    <button id="estimate-reset" class="button secondary" type="button" disabled>Сбросить выбор</button>
   </div>
  </div>
 </div>
 {_catalog_markup(services)}
</section>'''


def request_estimate(services):
    return f'''<section id="request-estimate" class="request-estimate" aria-labelledby="request-estimate-title" hidden>
 <h3 id="request-estimate-title">Услуги из вашего расчёта</h3>
 <ul id="request-estimate-services" class="request-estimate-services"></ul>
 <dl id="request-estimate-totals" class="estimate-totals"></dl>
 <p class="estimate-note">Скопируйте расчёт, чтобы добавить его к описанию задачи. Готовый список можно отправить в Telegram или по почте.</p>
 <div class="estimate-actions">
  <button id="request-estimate-copy" class="button secondary" type="button">Скопировать расчёт</button>
  <a id="request-estimate-edit" class="text-link" href="index.html#estimate">Изменить выбор</a>
 </div>
 <div id="request-estimate-manual" hidden>
  <label for="request-estimate-text">Текст расчёта</label>
  <textarea id="request-estimate-text" rows="5" readonly></textarea>
 </div>
 <p id="request-estimate-status" class="estimate-copy-status" role="status"></p>
</section>
{_catalog_markup(services)}'''
