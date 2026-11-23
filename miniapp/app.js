/* Bitrix24 provides the application form and chat inside the Mini App. */
(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const state = {catalog: null, view: 'services', telegram: null};
  const note = $('context-note');
  const formLoader = 'https://cdn-ru.bitrix24.ru/b38606320/crm/form/loader_25.js';
  const widgetLoader = 'https://cdn-ru.bitrix24.ru/b38606320/crm/site_button/loader_3_gbqxj4.js';
  let requestStarted = false;

  function loadBitrixScript(url, refreshPeriod, onError) {
    const script = document.createElement('script');
    script.async = true;
    script.src = url + '?' + Math.floor(Date.now() / refreshPeriod);
    if (onError) script.addEventListener('error', onError, {once: true});
    document.head.append(script);
  }

  function mountRequestForm() {
    if (requestStarted) return;
    requestStarted = true;
    const mount = $('bitrix-form');
    const status = $('request-form-status');
    const fallback = $('request-contact-fallback');
    const marker = document.createElement('script');
    marker.setAttribute('data-b24-form', 'inline/25/h8a51a');
    marker.setAttribute('data-b24-form-telemetry-sign', 'v1:25:site.bd5cb31496b0978c850786c0526098386316cc31190a6437e3d5b2a90988bd56');
    marker.setAttribute('data-skip-moving', 'true');
    mount.append(marker);

    const showFailure = () => {
      status.textContent = 'Не удалось загрузить форму. Можно связаться со мной другим способом.';
      fallback.hidden = false;
    };
    const fallbackTimer = window.setTimeout(showFailure, 15000);
    const observer = new MutationObserver(() => {
      if (!mount.querySelector('form, iframe')) return;
      window.clearTimeout(fallbackTimer);
      observer.disconnect();
      status.hidden = true;
      fallback.hidden = true;
    });
    observer.observe(mount, {childList: true, subtree: true});
    loadBitrixScript(formLoader, 180000, () => {
      window.clearTimeout(fallbackTimer);
      observer.disconnect();
      showFailure();
    });
  }

  function syncBackButton() {
    const back = state.telegram?.BackButton;
    if (state.view === 'services') back?.hide?.();
    else back?.show?.();
  }

  function showView(view) {
    state.view = view;
    for (const name of ['services', 'request', 'contact']) {
      $(name + '-view').hidden = name !== view;
    }
    note.hidden = Boolean(state.catalog) || view !== 'services';
    document.querySelectorAll('[data-view]').forEach(button => {
      if (button.dataset.view === view) button.setAttribute('aria-current', 'page');
      else button.removeAttribute('aria-current');
    });
    syncBackButton();
    window.scrollTo(0, 0);
    $(view === 'services' ? 'catalog-title' : view + '-title').focus({preventScroll: true});
    if (view === 'request') mountRequestForm();
  }

  function choose(topic = '') {
    const heading = $('request-topic');
    heading.textContent = topic;
    heading.hidden = !topic;
    showView('request');
  }

  function link(element, url) {
    if (/^https:\/\//.test(url) || /^mailto:/.test(url)) element.href = url;
  }

  function setProfileLink(id, url) {
    const profile = $(id);
    link(profile, url);
    const handle = new URL(profile.href).pathname.replace(/^\/+|\/+$/g, '');
    profile.querySelector('small').textContent = '@' + handle;
  }

  function render(catalog) {
    if (!catalog || !Array.isArray(catalog.services) || !catalog.site) throw new Error('catalog');
    if (catalog.pilot) {
      const pilot = catalog.pilot;
      $('pilot-title').textContent = pilot.headline; $('pilot-intro').textContent = pilot.intro;
      $('pilot-terms').textContent = pilot.terms; $('pilot-continuation').textContent = pilot.continuation; $('pilot-portfolio').textContent = pilot.portfolio;
      for (const example of pilot.examples) {const li = document.createElement('li'); li.textContent = example; $('pilot-examples').append(li);}
      $('pilot-offer').hidden = false;
      $('choose-pilot').disabled = false;
    }
    for (const service of catalog.services) {
      const card = document.createElement('article'); card.className = 'service-card';
      const title = document.createElement('h3'); title.textContent = service.name;
      const audience = document.createElement('p'); audience.className = 'audience'; audience.textContent = service.audience;
      const price = document.createElement('p'); price.className = 'price'; price.textContent = service.price;
      const unit = document.createElement('small'); unit.textContent = service.unit || ''; price.append(unit);
      const details = document.createElement('details'), summary = document.createElement('summary'); summary.textContent = 'Что входит'; details.append(summary);
      const list = document.createElement('ul');
      for (const item of service.includes || []) {const li = document.createElement('li'); li.textContent = item; list.append(li);} details.append(list);
      for (const text of [service.result, service.extra, service.separate]) {if (text) {const p = document.createElement('p'); p.textContent = text; details.append(p);}}
      const button = document.createElement('button');
      button.className = 'button full';
      button.type = 'button';
      button.textContent = 'Обсудить задачу →';
      button.addEventListener('click', () => choose(service.name));
      card.append(title, audience, price, details, button);
      $('catalog').append(card);
    }
    $('service-count').textContent = catalog.services.length + ' направлений';
    setProfileLink('personal-link', catalog.site.telegram);
    setProfileLink('instagram-link', catalog.site.instagram);
    setProfileLink('vk-link', catalog.site.vk);
    if (catalog.site.email) {
      const email = $('email-link');
      link(email, 'mailto:' + catalog.site.email);
      email.querySelector('small').textContent = catalog.site.email;
    }
    if (catalog.site.base_url) {
      link($('hero-projects'), catalog.site.base_url.replace(/\/+$/, '') + '/portfolio.html#telegram-projects');
    }
    state.catalog = catalog;
    note.hidden = true;
  }

  function connectTelegram() {
    const tg = window.Telegram?.WebApp;
    if (!tg?.platform || tg.platform === 'unknown' || state.telegram === tg) return;
    state.telegram = tg;
    try {
      tg.ready?.();
      tg.expand?.();
      const theme = () => {
        document.documentElement.classList.toggle('dark', tg.colorScheme === 'dark');
        document.documentElement.classList.toggle('light', tg.colorScheme === 'light');
      };
      theme();
      tg.onEvent?.('themeChanged', theme);
      tg.BackButton?.onClick?.(() => showView('services'));
      syncBackButton();
    } catch (_) {
      /* The in-page form and navigation work without the Telegram bridge. */
    }
  }

  document.querySelectorAll('[data-view]').forEach(button => button.addEventListener('click', () => showView(button.dataset.view)));
  document.querySelector('.brand').addEventListener('click', event => {
    event.preventDefault();
    showView('services');
  });
  $('hero-request').addEventListener('click', () => choose());
  $('hero-services').addEventListener('click', event => {
    const heading = $('service-list-title');
    event.preventDefault();
    heading.focus({preventScroll: true});
    heading.scrollIntoView({block: 'start'});
  });
  $('hero-contact').addEventListener('click', () => showView('contact'));
  $('choose-other').addEventListener('click', () => choose());
  $('choose-pilot').addEventListener('click', () => choose('Пробная задача'));
  $('request-contact-fallback').addEventListener('click', () => showView('contact'));
  function openProfile(event) {
    const url = event.currentTarget.href;
    const tg = state.telegram;
    if (!url.startsWith('https://') || event.button !== 0 ||
        event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) return;
    const open = url.startsWith('https://t.me/') ? tg?.openTelegramLink : tg?.openLink;
    if (typeof open !== 'function') return;
    try {
      open.call(tg, url);
      event.preventDefault();
    } catch (_) {
      /* The anchor stays available on clients without native link support. */
    }
  }
  for (const id of ['personal-link', 'instagram-link', 'vk-link']) {
    $(id).addEventListener('click', openProfile);
  }

  $('telegram-sdk').addEventListener('load', connectTelegram);
  connectTelegram();
  loadBitrixScript(widgetLoader, 60000);
  fetch('catalog.json', {cache: 'no-cache'})
    .then(response => {
      if (!response.ok) throw new Error('catalog');
      return response.json();
    })
    .then(render)
    .catch(() => {
      note.textContent = 'Не удалось загрузить услуги. Форму можно открыть во вкладке «Заявка».';
    });
})();
