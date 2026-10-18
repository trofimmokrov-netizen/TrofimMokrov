/* No bot token, public submission endpoint or browser storage is used here. */
(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const state = {catalog: null, view: 'services', review: null, sending: false, telegram: null};
  const note = $('context-note'), status = $('form-status'), form = $('request-form');
  const fields = {service: $('service'), details: $('details'), contact: $('contact')};
  function setStatus(text, error = false) {status.textContent = text; status.classList.toggle('error', error);}
  function canSend() {return state.telegram && state.telegram.platform && state.telegram.platform !== 'unknown';}
  function updateContext() {
    if (!state.catalog) return;
    note.textContent = canSend() ? 'Выберите услугу и оставьте заявку. Ответ придёт по вашему контакту.' : 'Это просмотр приложения. Для отправки откройте @TrofimAI_bot и нажмите «Открыть приложение» в меню бота.';
    $('send-button').disabled = !canSend() || state.sending;
  }
  function syncBackButton() {
    const back = state.telegram && state.telegram.BackButton;
    if (back) {if (state.view !== 'services') back.show(); else back.hide();}
  }
  function showView(view, focus = true) {
    if (!['services', 'request', 'contact'].includes(view)) return;
    state.view = view;
    for (const name of ['services', 'request', 'contact']) $(name + '-view').hidden = name !== view;
    document.querySelectorAll('[data-view]').forEach(button => {
      if (button.dataset.view === view) button.setAttribute('aria-current', 'page'); else button.removeAttribute('aria-current');
    });
    syncBackButton(); window.scrollTo(0, 0);
    if (focus) $(view === 'services' ? 'catalog-title' : view + '-title').focus({preventScroll: true});
  }
  function edit() {state.review = null; $('review').hidden = true; form.hidden = false; setStatus(''); fields.details.focus();}
  function choose(id = 'other') {if (!state.catalog) return; fields.service.value = id; edit(); showView('request');}
  function link(element, url) {if (/^https:\/\//.test(url) || /^mailto:/.test(url)) element.href = url;}
  function render(catalog) {
    if (!catalog || !Array.isArray(catalog.services) || !catalog.site) throw new Error('catalog');
    state.catalog = catalog;
    for (const [index, service] of catalog.services.entries()) {
      const card = document.createElement('article'); card.className = 'service-card';
      const number = document.createElement('span'); number.className = 'card-number'; number.textContent = String(index + 1).padStart(2, '0') + ' / НАПРАВЛЕНИЕ';
      const title = document.createElement('h3'); title.textContent = service.name;
      const audience = document.createElement('p'); audience.className = 'audience'; audience.textContent = service.audience;
      const price = document.createElement('p'); price.className = 'price'; price.textContent = service.price;
      const unit = document.createElement('small'); unit.textContent = service.unit || ''; price.append(unit);
      const details = document.createElement('details'), summary = document.createElement('summary'); summary.textContent = 'Что входит'; details.append(summary);
      const list = document.createElement('ul');
      for (const item of service.includes || []) {const li = document.createElement('li'); li.textContent = item; list.append(li);} details.append(list);
      const button = document.createElement('button'); button.className = 'button full'; button.type = 'button'; button.textContent = 'Обсудить задачу →'; button.addEventListener('click', () => choose(service.id));
      card.append(number, title, audience, price, details, button); $('catalog').append(card);
      const option = document.createElement('option'); option.value = service.id; option.textContent = service.name; fields.service.append(option);
    }
    const other = document.createElement('option'); other.value = 'other'; other.textContent = 'Другая задача'; fields.service.append(other);
    $('service-count').textContent = catalog.services.length + ' направлений';
    fields.service.disabled = false; $('choose-other').disabled = false; $('review-button').disabled = false; $('contact-request').disabled = false;
    link($('personal-link'), catalog.site.telegram); link($('email-link'), 'mailto:' + catalog.site.email);
    link($('portfolio-link'), catalog.site.base_url + '/portfolio.html'); link($('open-bot'), catalog.site.bot_url + '?start=app'); updateContext();
  }
  function connectTelegram() {
    const tg = window.Telegram && window.Telegram.WebApp;
    if (!tg || state.telegram === tg) return;
    state.telegram = tg;
    try {
      tg.ready(); tg.expand();
      const theme = () => {document.documentElement.classList.toggle('dark', tg.colorScheme === 'dark'); document.documentElement.classList.toggle('light', tg.colorScheme === 'light');};
      theme(); tg.onEvent('themeChanged', theme);
      if (tg.BackButton) tg.BackButton.onClick(() => state.review ? edit() : showView('services')); syncBackButton();
    } catch (_) { /* Older clients retain standard form controls. */ }
    updateContext();
  }
  document.querySelectorAll('[data-view]').forEach(button => button.addEventListener('click', () => showView(button.dataset.view)));
  document.querySelector('.brand').addEventListener('click', event => {event.preventDefault(); showView('services');}); $('catalog-title').tabIndex = -1;
  $('choose-other').addEventListener('click', () => choose()); $('contact-request').addEventListener('click', () => choose()); $('edit-button').addEventListener('click', edit);
  fields.details.addEventListener('input', () => {$('details-count').textContent = fields.details.value.length + ' / 1500';});
  form.addEventListener('submit', event => {
    event.preventDefault(); if (!state.catalog || !form.reportValidity()) return;
    const details = fields.details.value.trim(), contact = fields.contact.value.trim();
    if (details.length < 10 || contact.length < 5 || /[\r\n]/.test(contact) || !/[\p{L}\p{N}]/u.test(contact)) {setStatus('Укажите описание от 10 символов и контакт одной строкой.', true); return;}
    const data = {version: 1, type: 'request', consent: true, service_id: fields.service.value, details, contact};
    if (new TextEncoder().encode(JSON.stringify(data)).length > 4096) {setStatus('Описание слишком объёмное для Telegram. Сократите его и попробуйте снова.', true); return;}
    state.review = data; $('review-service').textContent = fields.service.options[fields.service.selectedIndex].text;
    $('review-details').textContent = details; $('review-contact').textContent = contact;
    form.hidden = true; $('review').hidden = false; setStatus(canSend() ? '' : 'Отправка доступна при открытии приложения кнопкой в боте.'); updateContext(); $('review').scrollIntoView({block: 'start'});
  });
  $('send-button').addEventListener('click', () => {
    if (!state.review || state.sending || !canSend()) return;
    state.sending = true; updateContext();
    try {state.telegram.sendData(JSON.stringify(state.review)); setStatus('Данные переданы Telegram. Подтверждение сохранения заявки придёт от бота в чат.');}
    catch (_) {state.sending = false; updateContext(); setStatus('Telegram не принял данные. Попробуйте ещё раз или напишите Трофиму лично.', true);}
  });
  $('telegram-sdk').addEventListener('load', connectTelegram); connectTelegram();
  fetch('catalog.json', {cache: 'no-cache'}).then(response => {if (!response.ok) throw new Error('catalog'); return response.json();}).then(render).catch(() => {
    note.textContent = 'Не удалось загрузить услуги. Обновите приложение или напишите @TrofimMokrov.'; setStatus('Каталог недоступен. Можно связаться с Трофимом через раздел «Контакты».', true);
  });
})();
