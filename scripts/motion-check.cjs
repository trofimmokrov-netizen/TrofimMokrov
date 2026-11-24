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
        window.entrances.push({element: this, keyframes, options});
        return animate.call(this, keyframes, options);
      };
    });

    await page.goto(base);
    await page.waitForFunction(() => window.entrances.some(({element}) => element.matches('.hero-copy > .lead')));
    const homeTitle = page.getByRole('heading', {level: 1});
    assert(await homeTitle.isVisible());
    const homeTitleText = await homeTitle.textContent();
    const intro = await page.evaluate(() => {
      const heading = window.entrances.find(({element}) => element.matches('.hero-copy > h1'));
      const lead = window.entrances.find(({element}) => element.matches('.hero-copy > .lead'));
      return {
        titleDelay: heading.options.delay,
        leadDelay: lead.options.delay,
        maskedHeading: heading.keyframes.every(frame => frame.clipPath),
        controlsMove: window.entrances.some(({element}) => element.matches('.hero-copy a, .hero-actions, .hero-copy')),
      };
    });
    assert(intro.titleDelay < intro.leadDelay, 'The home headline should enter before its description');
    assert(intro.maskedHeading, 'The native home heading should use the text mask');
    assert.equal(intro.controlsMove, false, 'Hero links should stay in place');

    const photo = page.locator('.hero-portrait img');
    await photo.scrollIntoViewIfNeeded();
    await page.waitForFunction(() => window.entrances.some(({element, keyframes}) =>
      element.matches('.hero-portrait img') && keyframes[0].transform.startsWith('scale(')));

    const service = page.locator('.home-service').first();
    await service.scrollIntoViewIfNeeded();
    await page.waitForFunction(() => window.entrances.some(({element}) => element.matches('.home-service .home-service-summary')));
    assert.equal(await service.evaluate(card => card.getAnimations().length), 0, 'Service links should stay in place');

    const projectFrame = page.locator('.project-feature-media').first();
    await projectFrame.scrollIntoViewIfNeeded();
    const projectImage = projectFrame.locator('img');
    await projectImage.evaluate(image => image.decode());
    const imageElement = await projectImage.elementHandle();
    await page.waitForFunction(image => window.entrances.some(({element}) => element === image), imageElement);
    assert(await projectImage.evaluate(image => {
      const reveal = window.entrances.find(({element}) => element === image);
      return reveal.keyframes[0].scale > 1 && reveal.keyframes[0].clipPath !== reveal.keyframes[1].clipPath;
    }), 'Project media should reveal inside its frame');
    assert.equal(await projectFrame.evaluate(frame => {
      const card = frame.closest('.project-feature');
      return window.entrances.filter(({element}) => element === frame || element === card).length;
    }), 0, 'Project frame and link should stay in place');

    const section = page.locator('[data-reveal]').last();
    const sectionHeading = section.locator('h2, h3').first();
    assert.equal(await sectionHeading.evaluate(heading => window.entrances.some(({element}) => element === heading)), false);
    await section.scrollIntoViewIfNeeded();
    await page.waitForFunction(heading => window.entrances.some(({element}) => element === heading), await sectionHeading.elementHandle());
    await page.evaluate(() => window.scrollTo({top: 0, behavior: 'instant'}));
    await section.scrollIntoViewIfNeeded();
    assert.equal(await sectionHeading.evaluate(heading => window.entrances.filter(({element}) => element === heading).length), 1);
    assert.equal(await projectImage.evaluate(image => window.entrances.filter(({element}) => element === image).length), 1);

    await page.setViewportSize({width: 1440, height: 700});
    await page.goto(base);
    await page.locator('.home-service').first().scrollIntoViewIfNeeded();
    await page.waitForFunction(() => window.entrances.filter(({element}) => element.matches('.home-service h3')).length >= 2);
    const titleDelays = await page.evaluate(() => window.entrances
      .filter(({element}) => element.matches('.home-service h3'))
      .map(({options}) => options.delay));
    assert(titleDelays[0] < titleDelays[1] && titleDelays.every(delay => delay <= 90), 'Visible service tiles should stagger briefly');

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
    assert.equal(await plain.getByRole('heading', {level: 1}).textContent(), homeTitleText);
    assert(await plain.locator('h1').isVisible());
    assert(await plain.getByRole('navigation', {name: 'Основная навигация'}).isVisible());
    assert(await plain.locator('[data-reveal]').last().isVisible());
    assert.deepEqual(errors, []);
    console.log('PASS: 28 responsive page checks, masked heading, portrait and project media reveals, staggered service text, mobile menu, reduced motion and no-JS fallback.');
  } finally {
    await browser.close();
  }
})().catch(error => {
  console.error(error);
  process.exitCode = 1;
});
