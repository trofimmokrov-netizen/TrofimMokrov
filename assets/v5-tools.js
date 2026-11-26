(() => {
  "use strict";

  const workspace = document.querySelector(".digital-tools");
  if (!workspace) return;
  const catalog = JSON.parse(document.getElementById("digital-tools-catalog").textContent);
  const serviceById = new Map(catalog.services.map(service => [service.id, service]));
  const numbers = new Intl.NumberFormat("ru-RU", {maximumFractionDigits: 2});
  const money = value => numbers.format(value) + " ₽";
  const hours = minutes => numbers.format(minutes / 60) + " ч";
  const requested = "Уточнить при обсуждении.";

  function get(data, name) {
    return String(data.get(name) ?? "").trim();
  }

  function webUrl(value) {
    if (!/^https?:\/\//i.test(value) || /[\u0000-\u0020\u007f\\]/.test(value)) return null;
    try {
      const url = new URL(value);
      return url.username || url.password ? null : url;
    } catch {
      return null;
    }
  }

  function error(name, message) {
    return {name, message};
  }

  function entry(label, value) {
    return label + "\n" + (value || requested);
  }

  function websiteBrief(data) {
    const reference = get(data, "reference");
    const url = reference ? webUrl(reference) : null;
    if (reference && !url) return error("reference", "Введите полный адрес HTTP или HTTPS без пароля.");
    return [
      "Бриф на сайт — " + get(data, "project"),
      entry("Аудитория", get(data, "audience")),
      entry("Главное действие посетителя", get(data, "goal")),
      entry("Страницы и разделы", get(data, "pages")),
      entry("Материалы", get(data, "materials")),
      entry("Пример для обсуждения", url?.href),
      "Перед запуском\nНазначьте ответственного за материалы. На телефоне проверьте путь от первого экрана до выбранного действия. Согласуйте срок и критерий готовности сайта.",
    ].join("\n\n");
  }

  function telegramBrief(data) {
    return [
      "Бриф на Telegram-бота — " + get(data, "project"),
      entry("Пользователи", get(data, "audience")),
      entry("Основной сценарий", get(data, "journey")),
      entry("Получатель обращения", get(data, "handoff")),
      entry("Интеграции", get(data, "integrations")),
      entry("Мини-приложение", get(data, "miniapp")),
      "Перед запуском\nУточните команды запуска и помощи. Согласуйте, что увидит пользователь при ошибке и кто проверит получение тестового обращения.",
    ].join("\n\n");
  }

  const editorialIdeas = {
    introduce: [
      "Представьте тему через один частый вопрос читателя.",
      "Покажите рабочий пример и объясните, как его читать.",
      "Составьте словарь из трёх полезных терминов.",
      "Соберите первые шаги для человека, который знакомится с темой.",
    ],
    explain: [
      "Разложите процесс на этапы и покажите результат каждого.",
      "Сравните два подхода для разных условий.",
      "Разберите одну типичную ошибку и способ проверки.",
      "Дайте короткий чек-лист перед принятием решения.",
    ],
    requests: [
      "Объясните, что нужно подготовить перед обращением.",
      "Опишите, как проходит первый этап работы.",
      "Ответьте на вопросы об объёме и условиях заказа.",
      "Покажите, как выбрать подходящий вариант и связаться.",
    ],
  };
  const followUpIdeas = [
    "Ответьте на вопрос, который остался после прошлой публикации.",
    "Покажите закулисье работы через конкретный артефакт.",
    "Сопоставьте сценарий новичка и опытного пользователя.",
    "Разберите, когда нужно пересмотреть исходное решение.",
    "Превратите длинное объяснение в короткую памятку.",
    "Соберите примеры удачных решений для разных задач.",
    "Предложите читателю проверить один шаг самостоятельно.",
    "Ответьте на возражение, которое получили от аудитории.",
  ];
  const channelFormats = {
    telegram: ["Короткий пост", "Пост с примером", "Памятка"],
    vk: ["Пост", "Карточки", "Разбор с иллюстрацией"],
    instagram: ["Карусель", "Сценарий короткого видео", "Серия историй"],
    website: ["Статья", "Ответ на частый вопрос", "Короткий кейс"],
  };
  const channelNames = {telegram: "Telegram", vk: "ВКонтакте", instagram: "Instagram", website: "Сайт"};

  function contentPlan(data) {
    const goal = get(data, "goal");
    const channel = get(data, "channel");
    const weeks = Number(get(data, "weeks"));
    const frequency = Number(get(data, "frequency"));
    const ideas = [...editorialIdeas[goal], ...followUpIdeas];
    const lines = [
      "План публикаций — " + get(data, "topic"),
      "Для кого — " + get(data, "audience"),
      "Площадка — " + channelNames[channel],
    ];
    for (let week = 0; week < weeks; week++) {
      lines.push("", "Неделя " + (week + 1));
      for (let slot = 0; slot < frequency; slot++) {
        const index = week * frequency + slot;
        const formats = channelFormats[channel];
        lines.push((slot + 1) + ". " + formats[(slot + week) % formats.length] + " — " + ideas[index]);
      }
    }
    lines.push("", "Для каждого пункта выберите конкретный пример, проверьте факты и добавьте одно понятное действие для читателя.");
    return lines.join("\n");
  }

  function budget(data) {
    const selection = data.getAll("service").map(id => serviceById.get(id)).filter(Boolean);
    if (!selection.length) return error(null, "Выберите хотя бы одну услугу.");
    const images = Number(get(data, "images"));
    const months = Number(get(data, "months"));
    const lines = ["Предварительный бюджет", ""];
    const priced = selection.filter(service => service.amount !== null);

    for (const service of selection) {
      const count = service.id === "ai-content" ? " × " + images : "";
      lines.push("• " + service.name + " — " + service.price + " · " + service.unit + count);
    }
    for (const [monthly, label] of [[false, "Разовые работы по известным ценам"], [true, "Известные ежемесячные расходы"]]) {
      const group = priced.filter(service => service.monthly === monthly);
      if (!group.length) continue;
      const amount = group.reduce((sum, service) => sum + service.amount * (service.id === "ai-content" ? images : 1), 0);
      const prefix = group.some(service => service.startingAt) ? "от " : "";
      lines.push("", label + " — " + prefix + money(amount));
      if (monthly && months > 1) lines.push("Период в месяцах — " + months, "За указанный период — " + prefix + money(amount * months));
      if (!monthly && amount < catalog.minimum) {
        lines.push("Сумма базовых разовых работ ниже минимального заказа.");
      }
    }
    if (selection.some(service => service.amount === null)) lines.push("", "Работы с индивидуальным расчётом оцениваются отдельно.");
    lines.push(
      "",
      "Минимальный заказ — " + money(catalog.minimum) + ".",
      catalog.advanceTerms,
      "Расчёт по базовым объёмам. Домен, хостинг, лицензии, подписки и другие внешние расходы учитываются отдельно при необходимости.",
    );
    return lines.join("\n");
  }

  function checklist(data, form) {
    const checked = new Set(data.getAll("done"));
    const labels = [...form.querySelectorAll(".tool-choice")];
    const project = get(data, "project");
    return [
      form.querySelector(".tool-inputs > legend").textContent,
      ...(project ? [project] : []),
      "Готово " + checked.size + " из " + labels.length,
      "",
      ...labels.map(label => {
        const choice = label.querySelector("input");
        return (checked.has(choice.value) ? "[x] " : "[ ] ") + label.querySelector("span").textContent;
      }),
    ].join("\n");
  }

  function seo(data) {
    const topic = get(data, "topic");
    const benefit = get(data, "benefit");
    const brand = get(data, "brand");
    const region = get(data, "region");
    const type = get(data, "pageType");
    const suffix = brand ? " | " + brand : "";
    const localized = type === "service" && region ? topic + " · " + region : topic;
    const ending = /[.!?…]$/.test(benefit) ? benefit : benefit + ".";
    const titleOptions = {
      service: [localized, localized + " — описание услуги"],
      article: [topic, topic + " — практическое руководство"],
      case: [topic + " — проект", topic + " — задача и результат"],
    };
    const alternative = {
      service: "Посмотрите, кому подходит услуга и что можно обсудить перед началом.",
      article: "В материале собраны пояснения и практические примеры по теме.",
      case: "В кейсе описаны исходная задача, выполненная работа и её результат.",
    };
    const count = value => [...value].length;
    return [
      "Шаблоны метатегов",
      "",
      ...titleOptions[type].map((option, index) => {
        const title = option + suffix;
        return "Title " + (index + 1) + " · " + count(title) + " симв.\n" + title;
      }),
      "",
      "Description · " + count(ending) + " симв.\n" + ending,
      "",
      "Дополнение для description, если это есть на странице\n" + alternative[type],
      "",
      "Проверьте метатеги на соответствие содержанию страницы. Поисковые системы могут показывать другой фрагмент.",
    ].join("\n");
  }

  function utm(data) {
    const url = webUrl(get(data, "url"));
    if (!url) return error("url", "Введите полный адрес HTTP или HTTPS без пароля.");
    for (const key of ["utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term"]) {
      const value = get(data, key);
      if (value) url.searchParams.set(key, value);
      else url.searchParams.delete(key);
    }
    return url.href;
  }

  function telegramLink(data) {
    const username = get(data, "username").replace(/^@/, "");
    if (!/^[A-Za-z0-9_]{5,32}$/.test(username)) {
      return error("username", "Укажите от 5 до 32 знаков. Подойдут латиница, цифры и подчёркивание.");
    }
    const base = "https://t.me/" + username;
    const mode = get(data, "mode");
    if (mode === "profile") return base;
    const payload = get(data, "payload");
    const limit = mode === "app" ? 512 : 64;
    if (payload && (!/^[A-Za-z0-9_-]+$/.test(payload) || payload.length > limit)) {
      return error("payload", "Используйте до " + limit + " знаков. Подойдут латиница, цифры, подчёркивание и дефис.");
    }
    if (mode === "start") return payload ? base + "?start=" + payload : base;
    const appName = get(data, "appName");
    if (appName && !/^[A-Za-z0-9_]{3,30}$/.test(appName)) {
      return error("appName", "Укажите короткое имя приложения из BotFather. Подойдут от 3 до 30 знаков латиницы, цифр и подчёркиваний.");
    }
    return base + (appName ? "/" + appName : "") + "?startapp" + (payload ? "=" + payload : "");
  }

  function automationTime(data) {
    const frequency = Number(get(data, "frequency"));
    const manual = Number(get(data, "before")) * frequency;
    const automated = Number(get(data, "after")) * frequency + Number(get(data, "maintenance"));
    const setup = Number(get(data, "setup"));
    const saving = Math.round((manual - automated) * 10) / 10;
    const change = saving >= 0 ? "Экономия" : "Дополнительная работа";
    const lines = [
      "Оценка времени на автоматизацию",
      "",
      "До внедрения — " + hours(manual) + " в неделю",
      "После внедрения с обслуживанием — " + hours(automated) + " в неделю",
      change + " — " + hours(Math.abs(saving)) + " в неделю",
      change + " за четыре недели — " + hours(Math.abs(saving) * 4),
    ];
    if (saving > 0 && setup > 0) {
      lines.push("Время на настройку вернётся примерно за " + numbers.format(setup * 60 / saving) + " нед.");
    }
    if (saving <= 0 && setup > 0) {
      lines.push("При этих вводных еженедельной экономии для возврата времени на настройку нет.");
    }
    lines.push("", "Проверьте вводные на нескольких реальных повторах и пересчитайте после тестового периода.");
    return lines.join("\n");
  }

  const generators = {
    "website-brief": websiteBrief,
    "telegram-brief": telegramBrief,
    "content-plan": contentPlan,
    budget,
    "launch-checklist": checklist,
    "crm-checklist": checklist,
    seo,
    utm,
    "telegram-link": telegramLink,
    "automation-time": automationTime,
  };

  function activeTelegramFields(form) {
    const mode = form.elements.mode.value;
    for (const [name, available] of [["payload", mode !== "profile"], ["appName", mode === "app"]]) {
      const input = form.elements[name];
      input.disabled = !available;
      input.setCustomValidity("");
      input.closest("label").hidden = !available;
    }
  }

  function openLinkedTool() {
    const linked = document.getElementById(window.location.hash.slice(1));
    if (linked?.matches(".digital-tool")) linked.open = true;
  }

  for (const card of workspace.querySelectorAll("[data-tool]")) {
    const tool = card.dataset.tool;
    const generate = generators[tool];
    const form = card.querySelector(".tool-form");
    const result = form.querySelector("[data-tool-result]");
    const output = form.querySelector("[data-tool-output]");
    const status = form.querySelector(".tool-status");
    const copy = form.querySelector("[data-tool-copy]");
    const download = form.querySelector("[data-tool-download]");

    form.addEventListener("submit", event => {
      event.preventDefault();
      const blank = [...form.querySelectorAll("input[required], textarea[required]")].find(control => !control.value.trim());
      if (blank) {
        blank.setCustomValidity("Заполните это поле.");
        blank.reportValidity();
        return;
      }
      const generated = generate(new FormData(form), form);
      if (typeof generated !== "string") {
        status.textContent = generated.message;
        if (generated.name) {
          const control = form.elements[generated.name];
          control.setCustomValidity(generated.message);
          control.reportValidity();
        } else {
          form.querySelector("input[type=checkbox]").focus();
        }
        return;
      }

      output.value = generated;
      output.scrollTop = 0;
      result.hidden = false;
      status.textContent = "Результат готов.";
      document.dispatchEvent(new CustomEvent("trofim:activity", {detail: "tools_use"}));
    });

    function clearResult(event) {
      const control = event.target;
      if (control.matches("[data-tool-output]")) return;
      control.setCustomValidity?.("");
      if (tool === "telegram-link" && control.name === "mode") activeTelegramFields(form);
      if (!result.hidden) {
        result.hidden = true;
        output.value = "";
        status.textContent = "Соберите результат заново после изменений.";
      } else {
        status.textContent = "";
      }
    }
    form.addEventListener("input", clearResult);

    copy.addEventListener("click", async () => {
      const snapshot = output.value;
      try {
        await navigator.clipboard.writeText(snapshot);
        if (!result.hidden && output.value === snapshot) status.textContent = "Результат скопирован.";
      } catch {
        if (result.hidden || output.value !== snapshot) return;
        output.focus();
        output.select();
        status.textContent = "Текст выделен для копирования.";
      }
    });

    download.addEventListener("click", () => {
      const link = document.createElement("a");
      const url = URL.createObjectURL(new Blob([output.value + "\n"], {type: "text/plain;charset=utf-8"}));
      link.href = url;
      link.download = tool + ".txt";
      document.body.append(link);
      link.click();
      link.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 1000);
      status.textContent = "Текстовый файл подготовлен к скачиванию.";
    });

    form.querySelector(".tool-inputs").disabled = false;
    if (tool === "telegram-link") activeTelegramFields(form);
    card.querySelector("[data-tool-unavailable]").hidden = true;
    form.hidden = false;
  }

  openLinkedTool();
  window.addEventListener("hashchange", openLinkedTool);
})();
