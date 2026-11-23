/* Telegram opens the site's form. The Mini App does not collect application data. */
(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const note = $('context-note');
  let currentView = 'services';
  let telegram;

  function syncBackButton() {
    const back = telegram?.BackButton;
    if (currentView === 'services') back?.hide?.();
    else back?.show?.();
  }

  function showView(view) {
    currentView = view;
    for (const name of ['services', 'contact']) $(name + '-view').hidden = name !== view;
    document.querySelectorAll('[data-view]').forEach(button => {
      if (button.dataset.view === view) button.setAttribute('aria-current', 'page');
      else button.removeAttribute('aria-current');
    });
    syncBackButton();
    window.scrollTo(0, 0);
    $(view === 'services' ? 'catalog-title' : 'contact-title').focus({preventScroll: true});
  }

  function configureLinks(site) {
    if (typeof site.base_url === 'string' && site.base_url.startsWith('https://')) {
      const base = site.base_url.replace(/\/+$/, '') + '/';
      const requestURL = new URL('contact.html#request-form', base);
      for (const link of document.querySelectorAll('[data-request-link]')) link.href = requestURL;
      $('portfolio-link').href = new URL('portfolio.html', base);
    }
    if (typeof site.telegram === 'string' && site.telegram.startsWith('https://t.me/')) {
      $('personal-link').href = site.telegram;
    }
    if (typeof site.email === 'string' && site.email) $('email-link').href = 'mailto:' + site.email;
  }

  function render(catalog) {
    if (!catalog || !Array.isArray(catalog.services) || !catalog.site) throw new Error('catalog');
    configureLinks(catalog.site);
    if (catalog.pilot) {
      const pilot = catalog.pilot;
      $('pilot-title').textContent = pilot.headline; $('pilot-intro').textContent = pilot.intro;
      $('pilot-terms').textContent = pilot.terms; $('pilot-continuation').textContent = pilot.continuation; $('pilot-portfolio').textContent = pilot.portfolio;
      for (const example of pilot.examples) {const li = document.createElement('li'); li.textContent = example; $('pilot-examples').append(li);}
      $('pilot-offer').hidden = false;
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
      const link = document.createElement('a');
      link.className = 'button full';
      link.textContent = 'Оставить заявку ↗';
      link.href = $('tab-request').href;
      link.target = '_blank';
      link.rel = 'noopener noreferrer';
      link.dataset.requestLink = '';
      card.append(title, audience, price, details, link);
      $('catalog').append(card);
    }
    $('service-count').textContent = catalog.services.length + ' направлений';
    note.hidden = true;
  }

  function connectTelegram() {
    const client = window.Telegram?.WebApp;
    if (!client?.platform || client.platform === 'unknown' || telegram === client) return;
    telegram = client;
    const theme = () => {
      document.documentElement.classList.toggle('dark', client.colorScheme === 'dark');
      document.documentElement.classList.toggle('light', client.colorScheme === 'light');
    };
    try {
      client.ready?.();
      client.expand?.();
      theme();
      client.onEvent?.('themeChanged', theme);
      client.BackButton?.onClick?.(() => showView('services'));
      syncBackButton();
    } catch (_) {
      /* Standard links and in-page navigation remain usable. */
    }
  }

  document.querySelectorAll('[data-view]').forEach(button => button.addEventListener('click', () => showView(button.dataset.view)));
  document.querySelector('.brand').addEventListener('click', event => {event.preventDefault(); showView('services');});
  document.addEventListener('click', event => {
    if (!telegram || event.defaultPrevented || event.button !== 0 || event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) return;
    const link = event.target.closest?.('a[data-request-link], a[data-telegram-link], a[data-site-link]');
    if (!link || !link.href.startsWith('https://')) return;
    const opener = link.hasAttribute('data-telegram-link') ? telegram.openTelegramLink : telegram.openLink;
    if (typeof opener !== 'function') return;
    try {
      opener.call(telegram, link.href);
      event.preventDefault();
    } catch (_) {
      /* The anchor stays available on clients without native link support. */
    }
  });

  $('telegram-sdk').addEventListener('load', connectTelegram);
  connectTelegram();
  fetch('catalog.json', {cache: 'no-cache'})
    .then(response => {
      if (!response.ok) throw new Error('catalog');
      return response.json();
    })
    .then(render)
    .catch(() => {
      note.textContent = 'Не удалось загрузить услуги. Откройте форму заявки на сайте или раздел «Контакты».';
    });
})();
