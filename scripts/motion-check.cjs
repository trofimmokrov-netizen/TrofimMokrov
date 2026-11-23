const assert = require('node:assert/strict');
const {chromium} = require('playwright');

const base = (process.env.SITE_URL || 'http://127.0.0.1:8000').replace(/\/$/, '') + '/';
const pages = [
  'index.html',
  'about.html',
  'services.html',
  'portfolio.html',
  'articles.html',
  'contact.html',
  'articles/automation-start.html',
];

(async () => {
  const browser = await chromium.launch({
    headless: true,
    ...(process.env.CHROMIUM_PATH ? {executablePath: process.env.CHROMIUM_PATH} : {}),
    args: ['--no-sandbox'],
  });
  try {
    const page = await browser.newPage({viewport: {width: 390, height: 844}});
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.addInitScript(() => {
      const animate = Element.prototype.animate;
      window.animatedElements = [];
      Element.prototype.animate = function (...args) {
        window.animatedElements.push(this);
        return animate.apply(this, args);
      };
    });

    await page.goto(base);
    await page.waitForFunction(() => window.animatedElements.some(element => element.matches('.hero-copy')));
    assert.equal((await page.locator('h1').innerText()).trim(), 'Трофим Мокров');
    const section = page.locator('[data-reveal]').last();
    assert.equal(await section.evaluate(element => window.animatedElements.includes(element)), false);
    await section.scrollIntoViewIfNeeded();
    await page.waitForFunction(element => window.animatedElements.includes(element), await section.elementHandle());

    for (const width of [320, 390, 768, 1440]) {
      await page.setViewportSize({width, height: 1000});
      for (const file of pages) {
        await page.goto(base + file);
        assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), 'Overflow at ' + width + 'px on ' + file);
      }
    }

    await page.setViewportSize({width: 390, height: 844});
    await page.goto(base);
    const menu = page.getByRole('button', {name: 'Меню'});
    const navigation = page.locator('#main-nav');
    await menu.click();
    assert.equal(await menu.getAttribute('aria-expanded'), 'true');
    await page.waitForFunction(() => window.animatedElements.some(element => element.id === 'main-nav'));
    await page.keyboard.press('Escape');
    assert.equal(await menu.getAttribute('aria-expanded'), 'false');
    await navigation.waitFor({state: 'hidden'});
    assert(await menu.evaluate(element => element === document.activeElement));

    await menu.click();
    await page.emulateMedia({reducedMotion: 'reduce'});
    await page.waitForFunction(() => !document.getAnimations().some(animation => animation.playState === 'running'));
    assert(await navigation.isVisible());
    assert(!(await navigation.evaluate(element => element.classList.contains('is-animating'))));
    await page.reload();
    await menu.click();
    assert.equal(await page.evaluate(() => window.animatedElements.length), 0);

    const plain = await browser.newPage({javaScriptEnabled: false, viewport: {width: 320, height: 844}});
    await plain.goto(base);
    assert(await plain.locator('h1').isVisible());
    assert(await plain.getByRole('navigation', {name: 'Основная навигация'}).isVisible());
    assert(await plain.locator('[data-reveal]').last().isVisible());
    assert.deepEqual(errors, []);
    console.log('PASS: 28 responsive page checks, intro and scroll motion, mobile menu, reduced-motion changes and no-JS fallback.');
  } finally {
    await browser.close();
  }
})().catch(error => {
  console.error(error);
  process.exitCode = 1;
});
