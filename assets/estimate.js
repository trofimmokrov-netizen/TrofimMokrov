(() => {
  "use strict";

  const dataElement = document.getElementById("estimate-catalog");
  if (!dataElement) return;

  const data = JSON.parse(dataElement.textContent);
  const catalog = new Map(data.services.map(service => [service.id, service]));
  const params = new URLSearchParams(window.location.search);
  const paramName = "estimate";
  const storageKey = "trofim-estimate";
  const money = new Intl.NumberFormat("ru-RU");

  function sanitize(value) {
    return [...new Set((value || "").split(",").filter(id => catalog.has(id)))];
  }

  function destination(path, hash, ids) {
    const url = new URL(path, window.location.href);
    if (ids.length) url.searchParams.set(paramName, ids.join(","));
    url.hash = hash;
    return url.href;
  }

  function formatAmount(amount) {
    return money.format(amount) + " ₽";
  }

  function totals(services) {
    const lines = [];
    const quoted = [];
    let belowMinimum = false;
    const groups = [
      {monthly: false, label: "Разово"},
      {monthly: true, label: "Ежемесячно"},
    ];
    const pricedServices = services.filter(service => service.amount !== null);
    for (const group of groups) {
      const priced = pricedServices.filter(service => service.monthly === group.monthly);
      if (!priced.length) continue;
      const total = priced.reduce((sum, service) => sum + service.amount, 0);
      const prefix = priced.some(service => service.startingAt) ? "от " : "";
      lines.push({label: group.label, value: prefix + formatAmount(total)});
      if (!group.monthly && total < data.minimum) belowMinimum = true;
    }
    for (const service of services) {
      if (service.amount === null) quoted.push(service.name);
    }
    if (quoted.length) lines.push({label: "Оценим отдельно", value: quoted.join(", ")});
    return {lines, belowMinimum};
  }

  function renderTotals(list, lines) {
    list.replaceChildren(...lines.map(({label, value}) => {
      const row = document.createElement("div");
      const term = document.createElement("dt");
      const amount = document.createElement("dd");
      term.textContent = label;
      amount.textContent = value;
      row.append(term, amount);
      return row;
    }));
  }

  function readStoredSelection() {
    try {
      return sanitize(sessionStorage.getItem(storageKey));
    } catch {
      return [];
    }
  }

  function saveSelection(ids) {
    try {
      sessionStorage.setItem(storageKey, ids.join(","));
    } catch {
      // The request link still transfers the selected catalog IDs.
    }
  }

  function initializeCalculator(calculator) {
    const options = [...calculator.querySelectorAll('input[name="estimate-service"]')];
    const request = document.getElementById("estimate-request");
    const reset = document.getElementById("estimate-reset");
    const empty = document.getElementById("estimate-empty");
    const summary = document.getElementById("estimate-totals");
    const minimum = document.getElementById("estimate-minimum");
    const announcement = document.getElementById("estimate-announcement");
    const more = document.getElementById("estimate-more");
    const moreCount = document.getElementById("estimate-more-count");
    const initial = params.has(paramName) ? sanitize(params.get(paramName)) : readStoredSelection();

    function update(announce) {
      const selected = options.filter(option => option.checked);
      const ids = selected.map(option => option.value);
      const {lines, belowMinimum} = totals(ids.map(id => catalog.get(id)));
      renderTotals(summary, lines);
      summary.hidden = !ids.length;
      empty.hidden = !!ids.length;
      minimum.hidden = !belowMinimum;
      minimum.textContent = belowMinimum
        ? "Если берёте только эти разовые работы, их можно дополнить до минимальной суммы заказа."
        : "";
      reset.disabled = !ids.length;
      request.href = destination("contact.html", "request-form", ids);
      if (moreCount) {
        const count = selected.filter(option => more.contains(option)).length;
        moreCount.textContent = count ? "Выбрано " + count : "";
      }
      if (announce) {
        announcement.textContent = lines.length
          ? lines.map(({label, value}) => label + " — " + value).join(". ")
          : "Выбор сброшен.";
        if (params.has(paramName)) {
          const current = new URL(window.location.href);
          if (ids.length) current.searchParams.set(paramName, ids.join(","));
          else current.searchParams.delete(paramName);
          history.replaceState(history.state, "", current);
        }
      }
      saveSelection(ids);
    }

    options.forEach(option => {
      option.checked = initial.includes(option.value);
    });
    if (more && options.some(option => option.checked && more.contains(option))) more.open = true;
    calculator.addEventListener("change", () => update(true));
    reset.addEventListener("click", () => {
      options.forEach(option => { option.checked = false; });
      options[0]?.focus();
      update(true);
    });
    update(false);
    document.getElementById("estimate-fallback").hidden = true;
    calculator.hidden = false;
  }

  function initializeRequest(section) {
    const ids = sanitize(params.get(paramName));
    if (!ids.length) return;

    const services = ids.map(id => catalog.get(id));
    const {lines} = totals(services);
    const list = document.getElementById("request-estimate-services");
    const summary = document.getElementById("request-estimate-totals");
    const edit = document.getElementById("request-estimate-edit");
    const copy = document.getElementById("request-estimate-copy");
    const manual = document.getElementById("request-estimate-manual");
    const text = document.getElementById("request-estimate-text");
    const status = document.getElementById("request-estimate-status");

    list.replaceChildren(...services.map(service => {
      const item = document.createElement("li");
      item.textContent = service.name + " — " + service.price + " · " + service.unit;
      return item;
    }));
    renderTotals(summary, lines);
    edit.href = destination("index.html", "estimate", ids);
    text.value = [
      "Услуги из предварительного расчёта",
      ...[...list.children].map(item => "• " + item.textContent),
      "",
      ...lines.map(({label, value}) => label + " — " + value),
    ].join("\n");
    copy.addEventListener("click", async () => {
      try {
        await navigator.clipboard.writeText(text.value);
        manual.hidden = true;
        status.textContent = "Расчёт скопирован.";
      } catch {
        manual.hidden = false;
        text.focus();
        text.select();
        status.textContent = "Выделенный текст можно скопировать вручную.";
      }
    });

    section.hidden = false;
  }

  const calculator = document.getElementById("estimate-calculator");
  if (calculator) initializeCalculator(calculator);
  const request = document.getElementById("request-estimate");
  if (request) initializeRequest(request);
})();
