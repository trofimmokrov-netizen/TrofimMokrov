(() => {
  const consentKey = 'trofim.activity.opt-in.v1';
  const totalsKey = 'trofim.activity.counts.v1';
  const panel = document.querySelector('[data-activity-panel]');
  const optIn = document.querySelector('#activity-opt-in');
  const counters = document.querySelector('#activity-counters');
  const clearButton = document.querySelector('#activity-clear');
  const status = document.querySelector('#activity-status');
  const labels = {
    cta_click: 'Нажатия на кнопки и ссылки действий',
    telegram_open: 'Переходы в Telegram',
    estimate_use: 'Выборы в калькуляторе',
    project_start: 'Начатые брифы',
    project_review: 'Просмотры расчёта в конструкторе',
    request_open: 'Переходы к форме заявки',
    article_view: 'Просмотры статей',
    tools_use: 'Готовые результаты инструментов',
  };
  const serviceIds = new Set((document.body.dataset.activityServices || '').split(',').filter(Boolean));
  const serviceLabels = [...document.querySelectorAll('[data-activity-service-label]')];
  const fixedEvents = new Set(['project_start', 'project_review', 'tools_use']);
  let storage;
  try {
    storage = localStorage;
    storage.getItem(consentKey);
  } catch {
    storage = null;
  }

  function consent() {
    try {
      return storage?.getItem(consentKey) === 'yes';
    } catch {
      return false;
    }
  }

  function readCounts() {
    try {
      const parsed = JSON.parse(storage.getItem(totalsKey) || '{}');
      return parsed && typeof parsed === 'object' ? parsed : {};
    } catch {
      return {};
    }
  }

  function counter(counts, key) {
    return Number.isSafeInteger(counts[key]) && counts[key] >= 0 ? counts[key] : 0;
  }

  function display() {
    if (!panel) return;
    optIn.checked = consent();
    const counts = readCounts();
    const rows = [...Object.entries(labels)];
    for (const label of serviceLabels) {
      const id = label.dataset.activityServiceLabel;
      if (counter(counts, 'service:' + id)) rows.push(['service:' + id, label.textContent]);
    }
    counters.replaceChildren(...rows.map(([key, label]) => {
      const row = document.createElement('li');
      row.textContent = label + ' — ' + counter(counts, key).toLocaleString('ru-RU');
      return row;
    }));
    clearButton.disabled = !rows.some(([key]) => counter(counts, key));
  }

  function record(key) {
    if (!consent()) return;
    try {
      const counts = readCounts();
      const next = Object.fromEntries([
        ...Object.keys(labels),
        ...[...serviceIds].map(id => 'service:' + id),
      ].filter(name => counter(counts, name)).map(name => [name, counter(counts, name)]));
      next[key] = Math.min((next[key] || 0) + 1, 1_000_000_000);
      storage.setItem(totalsKey, JSON.stringify(next));
      display();
    } catch {
      // Disabled or full browser storage must not prevent the selected action.
    }
  }

  if (panel) {
    panel.hidden = false;
    optIn.disabled = !storage;
    if (!storage) status.textContent = 'Хранилище браузера недоступно.';
    optIn.addEventListener('change', () => {
      try {
        storage.setItem(consentKey, optIn.checked ? 'yes' : 'no');
        if (!optIn.checked) storage.removeItem(totalsKey);
        status.textContent = optIn.checked ? 'Счётчики включены.' : 'Счётчики выключены и очищены.';
      } catch {
        status.textContent = 'Настройку не удалось сохранить в браузере.';
      }
      display();
    });
    clearButton.addEventListener('click', () => {
      try {
        storage.removeItem(totalsKey);
        status.textContent = 'Счётчики очищены.';
        display();
      } catch {
        status.textContent = 'Браузер не разрешил очистить счётчики.';
      }
    });
    window.addEventListener('storage', event => {
      if (event.key === consentKey || event.key === totalsKey || event.key === null) display();
    });
    display();
  }

  if (!storage) return;
  document.addEventListener('click', event => {
    if (!event.isTrusted || !(event.target instanceof Element)) return;
    const target = event.target.closest('a[href],button');
    if (!target || panel?.contains(target)) return;
    if (target.matches('.button,.action-link,.home-service,.header-telegram')) record('cta_click');
    if (target instanceof HTMLAnchorElement && target.protocol === 'https:' && target.hostname === 't.me') {
      record('telegram_open');
    }
    const id = target.dataset.activityService;
    if (serviceIds.has(id)) record('service:' + id);
  }, {passive: true});
  document.addEventListener('change', event => {
    const input = event.target;
    if (!event.isTrusted || !(input instanceof HTMLInputElement) || !input.checked) return;
    if (input.name === 'estimate-service' && serviceIds.has(input.value)) {
      record('estimate_use');
      record('service:' + input.value);
    }
  });
  document.addEventListener('trofim:activity', event => {
    if (fixedEvents.has(event.detail)) record(event.detail);
  });
  if (document.body.dataset.activityPage === 'article') record('article_view');
  if (document.body.dataset.activityPage === 'request') {
    let counted = false;
    const countRequest = () => {
      if (!counted && location.hash === '#request-form') {
        counted = true;
        record('request_open');
      }
    };
    countRequest();
    window.addEventListener('hashchange', countRequest);
  }
})();
