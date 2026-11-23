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
      window.entrances = [];
      Element.prototype.animate = function (keyframes, options) {
        window.entrances.push({element: this, options});
        return animate.call(this, keyframes, options);
      };
    });

    await page.goto(base);
    await page.waitForFunction(() => window.entrances.some(({element}) => element.matches('.hero-copy > .lead')));
    const homeTitle = page.getByRole('heading', {level: 1, name: 'Трофим Мокров'});
    assert(await homeTitle.isVisible());
    const intro = await page.evaluate(() => {
      const delay = selector => window.entrances.find(({element}) => element.matches(selector)).options.delay;
      return {
        titleDelay: delay('.hero-copy > h1'),
        leadDelay: delay('.hero-copy > .lead'),
        controlsMove: window.entrances.some(({element}) => element.matches('.hero-copy a, .hero-actions, .hero-copy')),
      };
    });
    assert(intro.titleDelay < intro.leadDelay, 'The home headline should enter before its description');
    assert.equal(intro.controlsMove, false, 'Hero links should stay in place');

    const section = page.locator('[data-reveal]').last();
    const sectionHeading = section.locator('h2, h3').first();
    assert.equal(await sectionHeading.evaluate(heading => window.entrances.some(({element}) => element === heading)), false);
    await section.scrollIntoViewIfNeeded();
    await page.waitForFunction(heading => window.entrances.some(({element}) => element === heading), await sectionHeading.elementHandle());
    await page.evaluate(() => window.scrollTo({top: 0, behavior: 'instant'}));
    await section.scrollIntoViewIfNeeded();
    assert.equal(await sectionHeading.evaluate(heading => window.entrances.filter(({element}) => element === heading).length), 1);

    await page.goto(base + 'contact.html');
    await page.waitForFunction(() => window.entrances.some(({element}) => element.matches('.page-heading > h1')));

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
    await page.waitForFunction(() => window.entrances.some(({element}) => element.id === 'main-nav'));
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
    assert.equal(await page.evaluate(() => window.entrances.length), 0);

    const plain = await browser.newPage({javaScriptEnabled: false, viewport: {width: 320, height: 844}});
    await plain.goto(base);
    assert(await plain.locator('h1').isVisible());
    assert(await plain.getByRole('navigation', {name: 'Основная навигация'}).isVisible());
    assert(await plain.locator('[data-reveal]').last().isVisible());
    assert.deepEqual(errors, []);
    console.log('PASS: 28 responsive page checks, staggered text, one-time scroll motion, mobile menu, reduced-motion changes and no-JS fallback.');
  } finally {
    await browser.close();
  }
})().catch(error => {
  console.error(error);
  process.exitCode = 1;
});
