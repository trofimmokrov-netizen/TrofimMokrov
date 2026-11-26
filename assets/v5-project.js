(() => {
  "use strict";

  const workspace = document.getElementById("project-workspace");
  if (!workspace) return;
  const element = id => document.getElementById(id);
  const panels = [...workspace.querySelectorAll("[data-project-step]")];
  const progress = [...workspace.querySelectorAll(".project-builder-progress li")];
  const steps = {services: 0, task: 1, review: 2};
  const groups = {
    services: [...workspace.querySelectorAll('input[name="project-service"]')],
    features: [...workspace.querySelectorAll('input[name="project-feature"]')],
    additions: [...workspace.querySelectorAll('input[name="project-addition"]')],
  };
  const fields = {
    budget: element("project-budget"),
    timing: element("project-timing"),
    description: element("project-description"),
  };
  const catalogData = JSON.parse(element("project-catalog").textContent);
  const catalog = new Map(catalogData.services.map(service => [service.id, service]));
  const keepDraft = element("project-keep-draft");
  const disclosures = ["service", "feature", "addition"].map(name => ({
    panel: element("project-more-" + name),
    count: element("project-count-" + name),
    choices: [...workspace.querySelectorAll('input[name="project-' + name + '"]')],
  })).filter(disclosure => disclosure.panel);
  const prev = element("project-prev");
  const next = element("project-next");
  const reset = element("project-reset");
  const draftStatus = element("project-draft-status");
  const copy = element("project-copy");
  const copyStatus = element("project-copy-status");
  const manualCopy = element("project-manual-copy");
  const briefText = element("project-brief-text");
  const request = element("project-request");
  const currency = new Intl.NumberFormat("ru-RU");
  const draftKey = "trofim-project-draft-v1";
  let step = steps.services;
  let started = false;

  function read(storage) {
    try {
      const saved = JSON.parse(window[storage].getItem(draftKey));
      return saved && typeof saved === "object" && !Array.isArray(saved) ? saved : null;
    } catch {
      return null;
    }
  }

  function store(storage, draft) {
    try {
      if (draft) window[storage].setItem(draftKey, JSON.stringify(draft));
      else window[storage].removeItem(draftKey);
      return true;
    } catch {
      return false;
    }
  }

  function collect() {
    const draft = {step, started, keep: keepDraft.checked};
    for (const [key, choices] of Object.entries(groups)) {
      draft[key] = choices.filter(choice => choice.checked).map(choice => choice.value);
    }
    for (const [key, field] of Object.entries(fields)) draft[key] = field.value.slice(0, field.maxLength);
    return draft;
  }

  function apply(draft) {
    step = Number.isInteger(draft.step) && panels[draft.step] ? draft.step : steps.services;
    started = draft.started === true;
    keepDraft.checked = draft.keep === true;
    for (const [key, choices] of Object.entries(groups)) {
      const ids = Array.isArray(draft[key]) ? new Set(draft[key]) : new Set();
      choices.forEach(choice => { choice.checked = ids.has(choice.value); });
    }
    for (const [key, field] of Object.entries(fields)) {
      field.value = typeof draft[key] === "string" ? draft[key].slice(0, field.maxLength) : "";
    }
    for (const {panel, choices} of disclosures) {
      panel.open = choices.some(choice => choice.checked && panel.contains(choice));
    }
  }

  function tell(message) {
    if (draftStatus.textContent !== message) draftStatus.textContent = message;
  }

  function haveDetails(draft) {
    return Object.keys(groups).some(key => draft[key].length)
      || Object.keys(fields).some(key => draft[key].trim());
  }

  function save(preferenceChanged = false) {
    const draft = collect();
    const tabSaved = store("sessionStorage", draft);
    const savedWithinBrowser = draft.keep && store("localStorage", draft);
    if (preferenceChanged && !draft.keep) store("localStorage", null);
    if (draft.keep && savedWithinBrowser) {
      tell("Черновик сохранён в этом браузере. Его можно очистить здесь.");
    } else if (draft.keep && !savedWithinBrowser) {
      tell(tabSaved
        ? "Сохранение между визитами недоступно. Черновик сохранён в этой вкладке."
        : "Сохранение недоступно. Скопируйте бриф перед закрытием страницы.");
    } else {
      tell(tabSaved ? "Черновик сохраняется в этой вкладке."
        : "Сохранение недоступно. Скопируйте бриф перед закрытием страницы.");
    }
  }

  function estimate(services) {
    const lines = [];
    let belowMinimum = false;
    for (const monthly of [false, true]) {
      const priced = services.filter(service => service.amount !== null && service.monthly === monthly);
      if (!priced.length) continue;
      const amount = priced.reduce((sum, service) => sum + service.amount, 0);
      const prefix = priced.some(service => service.startingAt) ? "от " : "";
      lines.push([monthly ? "Ежемесячно" : "Разово", prefix + currency.format(amount) + " ₽"]);
      if (!monthly && amount < catalogData.minimum) belowMinimum = true;
    }
    const quote = services.filter(service => service.amount === null);
    if (quote.length) lines.push(["Оценим отдельно", quote.map(service => service.name).join("\n")]);
    return {lines, belowMinimum};
  }

  function renderRows(target, rows) {
    target.replaceChildren(...rows.map(([label, value]) => {
      const row = document.createElement("div");
      const term = document.createElement("dt");
      const details = document.createElement("dd");
      term.textContent = label;
      details.textContent = value;
      row.append(term, details);
      return row;
    }));
  }

  function names(choices) {
    return choices.filter(choice => choice.checked)
      .map(choice => choice.nextElementSibling.textContent.trim()).join("\n");
  }

  function updateReview(draft) {
    const services = draft.services.map(id => catalog.get(id)).filter(Boolean);
    const rows = [
      ["Услуги", services.map(service => service.name + " — " + service.price + " · " + service.unit).join("\n")],
      ["Функции", names(groups.features)],
      ["Дополнения", names(groups.additions)],
      ["Бюджет", draft.budget.trim()],
      ["Желаемый срок", draft.timing.trim()],
      ["Задача", draft.description.trim()],
    ].filter(row => row[1]);
    const {lines, belowMinimum} = estimate(services);
    renderRows(element("project-brief-details"), rows);
    renderRows(element("project-price-breakdown"), lines);

    const empty = rows.length === 0;
    element("project-review-empty").hidden = !empty;
    element("project-brief").hidden = empty;
    element("project-handoff-hint").hidden = empty;
    element("project-price-breakdown").hidden = !lines.length;
    element("project-price-empty").hidden = !!lines.length;
    element("project-price-minimum").hidden = !belowMinimum;
    copy.hidden = empty;

    const estimateText = lines.length
      ? ["Ориентир по базовым ценам", ...lines.map(([name, value]) => name + " — " + value),
        element("project-price-terms").textContent.trim()]
      : [];
    briefText.value = ["Бриф проекта", ...rows.map(([name, value]) => name + "\n" + value), ...estimateText].join("\n\n");
    const url = new URL("contact.html#request-form", location.href);
    if (services.length) url.searchParams.set("estimate", services.map(service => service.id).join(","));
    request.href = url.href;
  }

  function updateControls() {
    const draft = collect();
    reset.hidden = !haveDetails(draft) && !draft.keep && step === steps.services;
    for (const {panel, count, choices} of disclosures) {
      const picked = choices.filter(choice => choice.checked && panel.contains(choice)).length;
      count.textContent = picked ? "Выбрано " + picked : "";
    }
  }

  function show(destination, focus) {
    step = destination;
    panels.forEach((panel, i) => { panel.hidden = i !== step; });
    progress.forEach((marker, i) => {
      if (i === step) marker.setAttribute("aria-current", "step");
      else marker.removeAttribute("aria-current");
    });
    prev.hidden = step === steps.services;
    next.hidden = step === steps.review;
    next.textContent = step === steps.task ? "Проверить бриф" : "Продолжить";
    manualCopy.hidden = true;
    copyStatus.textContent = "";
    if (step === steps.review) updateReview(collect());
    updateControls();
    if (focus) panels[step].querySelector("h2").focus();
  }

  function track(type) {
    document.dispatchEvent(new CustomEvent("trofim:activity", {detail: type}));
  }

  function start() {
    if (started) return;
    started = true;
    track("project_start");
  }

  function clearEntrySelection() {
    const url = new URL(location.href);
    if (!url.searchParams.has("estimate")) return;
    url.searchParams.delete("estimate");
    history.replaceState(history.state, "", url);
  }

  const sessionDraft = read("sessionStorage");
  const localDraft = read("localStorage");
  const draft = sessionDraft || (localDraft?.keep === true ? localDraft : {});
  if (localDraft?.keep !== true) draft.keep = false;
  const incoming = new URLSearchParams(location.search).get("estimate");
  if (incoming) {
    const ids = incoming.split(",").filter(id => catalog.has(id));
    const saved = Array.isArray(draft.services) ? draft.services : [];
    draft.services = [...new Set([...saved, ...ids])];
    if (ids.length) draft.step = steps.services;
    clearEntrySelection();
  }

  apply(draft);
  element("project-fallback").hidden = true;
  workspace.hidden = false;
  show(step, false);
  save();

  workspace.addEventListener("input", event => {
    if (event.target === briefText) return;
    const draft = collect();
    if (event.target !== keepDraft && haveDetails(draft)) start();
    updateControls();
    save(event.target === keepDraft);
  });
  window.addEventListener("storage", event => {
    if (event.key === draftKey && event.newValue === null && keepDraft.checked) {
      keepDraft.checked = false;
      updateControls();
      save();
    }
  });
  prev.addEventListener("click", () => {
    show(step - 1, true);
    save();
  });
  next.addEventListener("click", () => {
    start();
    show(step + 1, true);
    if (step === steps.review && collect().services.some(id => typeof catalog.get(id)?.amount === "number")) {
      track("project_review");
    }
    save();
  });
  reset.addEventListener("click", () => {
    apply({});
    const tabCleared = store("sessionStorage", null);
    const browserCleared = store("localStorage", null);
    clearEntrySelection();
    show(steps.services, true);
    tell(tabCleared && browserCleared ? "Черновик очищен." : "Поля черновика очищены.");
  });
  copy.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(briefText.value);
      manualCopy.hidden = true;
      copyStatus.textContent = "Бриф скопирован. Откройте форму и вставьте его в описание задачи.";
    } catch {
      manualCopy.hidden = false;
      briefText.focus();
      briefText.select();
      copyStatus.textContent = "Выделенный текст можно скопировать вручную.";
    }
  });
})();
