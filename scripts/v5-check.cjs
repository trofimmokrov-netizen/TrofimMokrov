const assert = require('node:assert/strict');
const {readFile} = require('node:fs/promises');
const {chromium} = require('playwright');

const base = new URL((process.env.SITE_URL || 'http://127.0.0.1:8000').replace(/\/$/, '') + '/');
const draftKey = 'trofim-project-draft-v1';
const consentKey = 'trofim.activity.opt-in.v1';
const countsKey = 'trofim.activity.counts.v1';
const budget = '35 000–45 000 ₽';
const timing = 'К 18 марта';
const description = 'Тестовый бриф для каталога мастерской';
const privateMarker = 'synthetic-activity@example.test';
const selectedServices = ['personal-solutions', 'social', 'telegram-bots', 'websites'];
const caseSlugs = ['aik-base', 'device-workshop', 'drevesniy-zamysel', 'drevesny-3d', 'ksusha-epoxy', 'personal-site'];
const formFixture = `
  const place = document.querySelector('[data-b24-form]');
  const form = document.createElement('form');
  form.id = 'v5-bitrix-fixture';
  const input = document.createElement('input');
  input.setAttribute('aria-label', 'Описание задачи');
  form.append(input);
  form.addEventListener('submit', event => event.preventDefault());
  place.after(form);
`;

async function navigate(page, target) {
  const response = await page.goto(new URL(target, base).href);
  assert.equal(response?.status(), 200, `HTTP status for ${target}`);
}

async function layout(page, width) {
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - innerWidth);
  assert.ok(overflow <= 1, `Horizontal overflow on ${page.url()} at ${width}px (${overflow}px)`);
}

function normalized(text) {
  return text.replace(/[\u00a0\u202f]/g, ' ');
}

async function checkTheme(page, width) {
  await navigate(page, 'index.html');
  await layout(page, width);
  const toggle = page.getByRole('button', {name: 'Оформление сайта'});
  const options = page.locator('#v5-theme-options');
  await toggle.click();
  await options.getByRole('radio', {name: 'Тёмная'}).check();
  assert.equal(await page.locator('html').getAttribute('data-theme'), 'dark');
  await page.keyboard.press('Escape');
  assert.equal(await toggle.getAttribute('aria-expanded'), 'false');
  await navigate(page, 'articles/website-or-landing.html#part-1');
  assert.equal(new URL(page.url()).hash, '#part-1');
  assert.equal(await page.locator('html').getAttribute('data-theme'), 'dark');
  await page.reload();
  assert.equal(await page.locator('html').getAttribute('data-theme'), 'dark');
  await toggle.click();
  await options.getByRole('radio', {name: 'Светлая'}).check();
  assert.equal(await page.locator('html').getAttribute('data-theme'), 'light');
  await options.getByRole('radio', {name: 'Как в системе'}).check();
  await page.emulateMedia({colorScheme: 'dark'});
  await page.waitForFunction(() => document.documentElement.dataset.theme === 'dark');
  await page.emulateMedia({colorScheme: 'light'});
  await page.waitForFunction(() => document.documentElement.dataset.theme === 'light');
}

async function checkWizard(page, context, width) {
  await navigate(page, 'project.html?estimate=websites,missing-service');
  const service = id => page.locator(`input[name="project-service"][value="${id}"]`);
  await page.locator('#project-workspace').waitFor();
  assert.ok(await service('websites').isChecked(), 'Valid intake ID is preselected');
  assert.equal(new URL(page.url()).search, '', 'The consumed query was removed');
  await service('telegram-bots').check();
  await service('social').check();
  await page.locator('#project-more-service summary').click();
  await service('personal-solutions').check();
  await page.locator('#project-more-feature summary').click();
  await page.locator('input[name="project-feature"][value="crm"]').check();
  await page.locator('#project-more-addition summary').click();
  await page.locator('input[name="project-addition"][value="content"]').check();
  await layout(page, width);

  const next = page.locator('#project-next');
  await next.click();
  assert.equal(await page.locator(':focus').getAttribute('id'), 'project-task-title');
  await page.locator('#project-budget').fill(budget);
  await page.locator('#project-timing').fill(timing);
  await page.locator('#project-description').fill(description);
  assert.equal(await page.evaluate(key => localStorage.getItem(key), draftKey), null, 'Draft storage requires opt-in');
  await page.reload();
  assert.equal(await page.locator('#project-description').inputValue(), description, 'Tab draft survives reload');
  await page.locator('#project-keep-draft').check();
  await next.click();
  assert.equal(await page.locator(':focus').getAttribute('id'), 'project-review-title');
  const costs = normalized(await page.locator('#project-price-breakdown').innerText());
  assert.match(costs, /Разово\s+от 20 000 ₽/);
  assert.match(costs, /Ежемесячно\s+от 15 000 ₽/);
  assert.match(costs, /Оценим отдельно/);
  await layout(page, width);

  await page.locator('#project-copy').click();
  await page.waitForFunction(() => document.querySelector('#project-copy-status').textContent.includes('скопирован'));
  const copied = await page.evaluate(() => window.v5Clipboard);
  for (const part of [budget, timing, description, 'Передача заявок в CRM', 'Подготовка текстов и визуалов']) {
    assert.ok(copied.includes(part), `Copied brief contains ${part}`);
  }

  const restored = await context.newPage();
  try {
    await navigate(restored, 'project.html');
    await restored.locator('#project-review-title').waitFor();
    assert.ok((await restored.locator('#project-brief-details').innerText()).includes(description), 'New tab restores opted-in draft');
    await restored.locator('#project-reset').click();
    assert.ok(await restored.locator('#project-services-title').isVisible());
    assert.equal(await restored.locator('input[name="project-service"]:checked').count(), 0);
    assert.ok(!await restored.locator('#project-keep-draft').isChecked());
    assert.deepEqual(await restored.evaluate(key => [localStorage.getItem(key), sessionStorage.getItem(key)], draftKey), [null, null]);
  } finally {
    await restored.close();
  }

  await page.locator('#project-request').click();
  await page.waitForURL(url => url.pathname.endsWith('/contact.html') && url.hash === '#request-form');
  const handoff = new URL(page.url());
  assert.deepEqual([...handoff.searchParams.keys()], ['estimate']);
  assert.deepEqual(handoff.searchParams.get('estimate').split(',').sort(), selectedServices);
  await page.locator('#v5-bitrix-fixture input').waitFor();
  assert.equal(await page.locator('#v5-bitrix-fixture input').inputValue(), '');
  await page.locator('#request-estimate').waitFor();
}

const toolScenarios = [
  {id: 'website-brief', fields: {project: 'Мастерская', audience: 'Владельцы техники', goal: 'Записаться на ремонт'}, expect: /Бриф на сайт — Мастерская[\s\S]*Записаться на ремонт/},
  {id: 'telegram-brief', fields: {project: 'Бот студии', audience: 'Заказчики', journey: 'Запросить эскиз', handoff: 'Менеджеру'}, expect: /Бриф на Telegram-бота — Бот студии[\s\S]*Запросить эскиз[\s\S]*Менеджеру/},
  {id: 'content-plan', fields: {topic: 'Ремонт', audience: 'Жители района'}, select: {channel: 'vk', weeks: '2', frequency: '2'}, expect: /ВКонтакте[\s\S]*Неделя 1[\s\S]*Неделя 2/},
  {id: 'budget', fields: {images: '3', months: '2'}, check: {service: ['websites', 'social', 'ai-content']}, expect: /Разовые работы по известным ценам — от 13 000 ₽[\s\S]*Известные ежемесячные расходы — от 15 000 ₽[\s\S]*За указанный период — от 30 000 ₽/},
  {id: 'launch-checklist', fields: {project: 'Визитка'}, check: {done: ['mobile', 'forms']}, expect: /Визитка[\s\S]*Готово 2 из 8[\s\S]*\[x\] Формы/},
  {id: 'crm-checklist', fields: {project: 'Воронка'}, check: {done: ['routing']}, expect: /Воронка[\s\S]*Готово 1 из 8[\s\S]*\[x\] Назначение заявки/},
  {id: 'seo', fields: {topic: 'Ремонт техники', benefit: 'Проверьте сроки', brand: 'Мастерская', region: 'Тула'}, expect: /Ремонт техники · Тула \| Мастерская[\s\S]*Проверьте сроки\./},
  {id: 'utm', fields: {url: 'https://example.test/page?ref=guide#example', utm_source: 'telegram', utm_medium: 'social', utm_campaign: 'launch'}, expect: /^https:\/\/example\.test\/page\?ref=guide&utm_source=telegram&utm_medium=social&utm_campaign=launch#example$/},
  {id: 'telegram-link', fields: {username: '@example_bot', payload: 'campaign_1', appName: 'catalog'}, select: {mode: 'app'}, expect: /^https:\/\/t\.me\/example_bot\/catalog\?startapp=campaign_1$/},
  {id: 'automation-time', fields: {before: '20', after: '5', frequency: '12', maintenance: '30', setup: '5'}, expect: /Экономия — 2,5 ч в неделю[\s\S]*примерно за 2 нед\./},
];

async function openTool(page, id) {
  const tool = page.locator(`[data-tool="${id}"]`);
  if (!await tool.getAttribute('open').then(value => value !== null)) await tool.locator('summary').click();
  await tool.locator('form').waitFor();
  return tool;
}

async function checkTools(page, width) {
  await navigate(page, 'tools.html#tool-utm');
  const utm = page.locator('[data-tool="utm"]');
  await utm.locator('form').waitFor();
  assert.equal(await page.locator('[data-tool]').count(), toolScenarios.length);
  await utm.locator('[name="url"]').fill('ftp://example.test/file');
  for (const name of ['utm_source', 'utm_medium', 'utm_campaign']) await utm.locator(`[name="${name}"]`).fill('fixture');
  await utm.locator('[type="submit"]').click();
  assert.match(await utm.locator('.tool-status').innerText(), /HTTP или HTTPS/);
  assert.ok(!await utm.locator('[data-tool-result]').isVisible());

  for (const scenario of toolScenarios) {
    const tool = await openTool(page, scenario.id);
    for (const [name, value] of Object.entries(scenario.select || {})) await tool.locator(`[name="${name}"]`).selectOption(value);
    for (const [name, value] of Object.entries(scenario.fields)) await tool.locator(`[name="${name}"]`).fill(value);
    for (const [name, values] of Object.entries(scenario.check || {})) {
      for (const value of values) await tool.locator(`[name="${name}"][value="${value}"]`).check();
    }
    await tool.locator('[type="submit"]').click();
    const output = tool.locator('[data-tool-output]');
    await output.waitFor();
    const value = await output.inputValue();
    assert.match(normalized(value), scenario.expect, `Generated output for ${scenario.id}`);
    const [download] = await Promise.all([page.waitForEvent('download'), tool.locator('[data-tool-download]').click()]);
    assert.equal(download.suggestedFilename(), `${scenario.id}.txt`);
    assert.equal(await readFile(await download.path(), 'utf8'), value + '\n');
    await layout(page, width);
  }
}

async function checkActivity(page) {
  const optIn = page.locator('#activity-opt-in');
  await optIn.waitFor();
  const readStorage = () => page.evaluate(keys => keys.map(key => localStorage.getItem(key)), [consentKey, countsKey]);
  assert.ok(!await optIn.isChecked());
  assert.deepEqual(await readStorage(), [null, null], 'Generating tools before opt-in left no activity records');
  await optIn.check();
  const tool = await openTool(page, 'website-brief');
  const requests = [];
  const recordRequest = request => requests.push(request.method());
  page.on('request', recordRequest);
  try {
    await tool.locator('[name="project"]').fill(privateMarker);
    await tool.locator('[type="submit"]').click();
    assert.ok((await tool.locator('[data-tool-output]').inputValue()).includes(privateMarker));
    const [consent, counts] = await readStorage();
    assert.equal(consent, 'yes');
    assert.equal(JSON.parse(counts).tools_use, 1);
    assert.ok(!counts.includes(privateMarker));
    assert.ok(Object.values(JSON.parse(counts)).every(Number.isSafeInteger), 'Activity contains only aggregate numeric values');
    assert.deepEqual(requests, [], 'Input and local activity do not cause a network request');
  } finally {
    page.off('request', recordRequest);
  }
  await navigate(page, 'articles/website-or-landing.html');
  await page.waitForFunction(key => JSON.parse(localStorage.getItem(key) || '{}').article_view === 1, countsKey);
  await navigate(page, 'tools.html');
  await optIn.waitFor();
  assert.ok(await optIn.isChecked());
  assert.match(await page.locator('#activity-counters').innerText(), /Готовые результаты инструментов — 1/);
  await page.locator('#activity-clear').click();
  assert.deepEqual(await readStorage(), ['yes', null]);
  await optIn.uncheck();
  assert.deepEqual(await readStorage(), ['no', null]);
}

async function checkEcosystem(page, width) {
  await navigate(page, 'ecosystem.html#eco-supabase');
  const controls = page.locator('[data-eco-controls]');
  await controls.waitFor();
  assert.equal(await controls.locator('[data-eco-node]').count(), 10);
  const selected = () => controls.locator('[aria-pressed="true"]').getAttribute('data-eco-node');
  assert.equal(await selected(), 'supabase');
  assert.ok(await page.locator('#eco-supabase').isVisible());
  assert.equal(await page.locator('#eco-supabase a').getAttribute('href'), 'articles/supabase-table-model-and-migrations.html');
  await controls.locator('[data-eco-node="bitrix24"]').click();
  assert.equal(await selected(), 'bitrix24');
  assert.equal(await page.locator('[data-eco-panel]:visible').count(), 1);
  assert.equal(await page.locator('#eco-bitrix24 a').getAttribute('href'), 'contact.html#request-form');
  await page.evaluate(() => { location.hash = 'eco-github'; });
  await page.locator('#eco-github').waitFor();
  assert.equal(await selected(), 'github');
  await layout(page, width);

  await navigate(page, 'portfolio.html');
  const links = await page.locator('a.case-page-link').evaluateAll(anchors => anchors.map(a => a.getAttribute('href')).sort());
  const portfolioAnchors = await page.locator('[id]').evaluateAll(nodes => nodes.map(node => '#' + node.id));
  assert.deepEqual(links, caseSlugs.map(slug => `cases/${slug}.html`));
  for (const link of links) {
    await navigate(page, link);
    assert.equal(await page.locator('h1').count(), 1);
    const back = new URL(await page.getByRole('link', {name: 'Портфолио', exact: true}).last().getAttribute('href'), page.url());
    assert.equal(back.pathname, new URL('portfolio.html', base).pathname);
    assert.ok(portfolioAnchors.includes(back.hash), `The return link from ${link} targets an existing card`);
    await layout(page, width);
  }
}

async function main() {
  const browser = await chromium.launch({
    headless: true, args: ['--no-sandbox'],
    ...(process.env.CHROMIUM_PATH ? {executablePath: process.env.CHROMIUM_PATH} : {}),
  });
  try {
    for (const width of [320, 1440]) {
      const context = await browser.newContext({viewport: {width, height: 900}, reducedMotion: 'reduce', colorScheme: 'light'});
      try {
        context.setDefaultTimeout(5000);
        const errors = [];
        const mutations = [];
        await context.addInitScript(() => {
          Object.defineProperty(navigator, 'clipboard', {value: {
            writeText: async value => { window.v5Clipboard = value; },
          }});
        });
        await context.route('**/*', route => {
          const request = route.request();
          const url = new URL(request.url());
          if (!['GET', 'HEAD'].includes(request.method())) {
            mutations.push(request.method());
            return route.abort();
          }
          if (url.origin === base.origin) return route.continue();
          if (url.hostname === 'cdn-ru.bitrix24.ru' && url.pathname.endsWith('/crm/form/loader_25.js')) {
            return route.fulfill({contentType: 'application/javascript', body: formFixture});
          }
          return route.abort();
        });
        context.on('weberror', error => errors.push(error.error().message));
        const page = await context.newPage();
        await checkTheme(page, width);
        await checkWizard(page, context, width);
        await checkTools(page, width);
        await checkActivity(page);
        await checkEcosystem(page, width);
        assert.deepEqual(mutations, [], 'The flows do not send mutations');
        assert.deepEqual(errors, [], 'No browser exceptions');
        console.log(`PASS v5 ${width}px: theme, project draft, 10 tools and exports, local activity, ecosystem and six cases.`);
      } finally {
        await context.close();
      }
    }
  } finally {
    await browser.close();
  }
}

main().catch(error => { console.error(error); process.exitCode = 1; });
