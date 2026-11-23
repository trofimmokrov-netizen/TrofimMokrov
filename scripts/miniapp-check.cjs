/* Bitrix24 and Telegram are simulated. No lead is submitted to a real service. */
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const {site,services}=require('../miniapp/catalog.json');
const base=(process.env.SITE_URL||'http://127.0.0.1:8011').replace(/\/$/,'')+'/miniapp/';
const sdkURL='https://telegram.org/js/telegram-web-app.js*';
const bitrixBase='https://cdn-ru.bitrix24.ru/b38606320/crm/';
const formURL=bitrixBase+'form/loader_25.js';
const widgetURL=bitrixBase+'site_button/loader_3_gbqxj4.js';
const formCode='inline/25/h8a51a';
const formSign='v1:25:site.bd5cb31496b0978c850786c0526098386316cc31190a6437e3d5b2a90988bd56';
const socialLinks=[
  ['#instagram-link','https://www.instagram.com/trofimmokrov/'],
  ['#vk-link','https://vk.com/trofimmokrov'],
];

function sdk(theme) {
  return 'window.__siteLinks=[];window.__telegramLinks=[];window.__sent=[];window.Telegram={WebApp:{'
    +'platform:"ios",colorScheme:'+JSON.stringify(theme)+',ready(){},expand(){},onEvent(){},'
    +'BackButton:{show(){},hide(){},onClick(callback){window.__back=callback}},'
    +'openLink(url){window.__siteLinks.push(url)},openTelegramLink(url){window.__telegramLinks.push(url)},'
    +'sendData(data){window.__sent.push(data)}}};';
}

async function mockBitrix(context,{failForm=false}={}) {
  const requests={form:0,widget:0};
  await context.route(formURL+'*',route=>{
    requests.form++;
    if (failForm) return route.abort();
    return route.fulfill({contentType:'application/javascript',body:
      'const marker=document.querySelector("script[data-b24-form]");'
      +'window.__formMountedVisible=!document.getElementById("request-view").hidden;'
      +'window.__formAttributes=[marker.dataset.b24Form,marker.dataset.b24FormTelemetrySign,marker.dataset.skipMoving];'
      +'const form=document.createElement("form");form.id="mock-bitrix-form";'
      +'form.innerHTML='+JSON.stringify('<label>Имя<input class="b24-form-control" required></label><button type="submit">Отправить</button>')+';'
      +'form.addEventListener("submit",event=>{event.preventDefault();window.__bitrixSubmit=(window.__bitrixSubmit||0)+1});'
      +'marker.after(form);'
    });
  });
  await context.route(widgetURL+'*',route=>{
    requests.widget++;
    return route.fulfill({contentType:'application/javascript',body:
      'const launcher=document.createElement("button");launcher.type="button";'
      +'launcher.className="b24-widget-button-wrapper b24-widget-button-position-bottom-right";'
      +'launcher.style="position:fixed;right:12px;bottom:12px;height:40px";'
      +'launcher.textContent="Чат";document.body.append(launcher);'
    });
  });
  return requests;
}

(async()=>{
  const browser=await chromium.launch({headless:true,executablePath:process.env.CHROMIUM_PATH||'/usr/bin/chromium',args:['--no-sandbox']});
  const errors=[];
  let layouts=0;
  try {
    for (const theme of ['light','dark']) {
      for (const width of [320,390,768]) {
        const context=await browser.newContext({isMobile:width<=390,hasTouch:true,viewport:{width,height:844}});
        await context.route(sdkURL,route=>route.fulfill({contentType:'application/javascript',body:sdk(theme)}));
        const requests=await mockBitrix(context);
        const page=await context.newPage();
        page.on('pageerror',error=>errors.push(error.message));
        await page.goto(base);
        await page.waitForSelector('.service-card');
        await page.waitForSelector('.b24-widget-button-wrapper');
        assert.equal(await page.locator('#catalog-title').textContent(),'Трофим Мокров');
        assert.equal(await page.locator('.service-card').count(),services.length);
        assert.equal(await page.locator('html').evaluate((el,name)=>el.classList.contains(name),theme),true);
        assert.deepEqual(requests,{form:0,widget:1});
        await page.evaluate(()=>{
          document.documentElement.style.setProperty('--tg-safe-area-inset-top','24px');
          document.documentElement.style.setProperty('--tg-content-safe-area-inset-top','16px');
          document.documentElement.style.setProperty('--tg-safe-area-inset-bottom','30px');
        });
        assert.equal(await page.locator('body').evaluate(el=>getComputedStyle(el).paddingTop),'40px');
        assert.equal(await page.locator('.tabs').evaluate(el=>getComputedStyle(el).paddingBottom),'40px');

        const projectsURL=new URL(await page.locator('#hero-projects').getAttribute('href'),base);
        assert.equal(projectsURL.href,site.base_url+'/portfolio.html#telegram-projects');
        assert.equal(await page.locator('#hero-services').getAttribute('href'),'#service-list-title');
        await page.locator('#hero-services').tap();
        assert.equal(await page.locator(':focus').getAttribute('id'),'service-list-title');
        await page.locator('#hero-contact').tap();
        const contactView=page.locator('#contact-view');
        assert.equal(await contactView.isVisible(),true);
        assert.equal(await contactView.getByRole('link',{name:/Написать лично/}).getAttribute('href'),site.telegram);
        assert.equal(await contactView.getByRole('link',{name:/Написать на почту/}).getAttribute('href'),'mailto:'+site.email);
        const contactLinks=await contactView.getByRole('link').evaluateAll(links=>links.map(link=>link.href));
        assert.deepEqual(contactLinks.sort(),[site.telegram,'mailto:'+site.email,...socialLinks.map(([,url])=>url)].sort());
        for (const [selector,url] of socialLinks) {
          assert.equal(await contactView.locator(selector).getAttribute('href'),url);
        }
        assert.deepEqual(requests,{form:0,widget:1});
        await page.evaluate(()=>window.__back());
        await page.locator('#hero-request').tap();
        await page.locator('#mock-bitrix-form').waitFor();
        assert.equal(await page.locator('#request-form-status').isHidden(),true);
        assert.equal(await page.locator('#request-contact-fallback').isHidden(),true);
        assert.equal(await page.locator(':focus').getAttribute('id'),'request-title');
        assert.equal(await page.evaluate(()=>window.__formMountedVisible),true);
        assert.deepEqual(await page.evaluate(()=>window.__formAttributes),[formCode,formSign,'true']);
        await page.locator('#mock-bitrix-form input').fill('Черновик');

        for (const view of ['services','request','contact']) {
          await page.locator('[data-view="'+view+'"]').tap();
          assert.equal(await page.locator('#'+view+'-view').isVisible(),true);
          assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,'overflow '+theme+' '+width+' '+view);
          const tabBox=await page.locator('.tabs').boundingBox();
          const widgetBox=await page.locator('.b24-widget-button-wrapper').boundingBox();
          assert(widgetBox.y+widgetBox.height<tabBox.y,'chat launcher must sit above tabs');
          layouts++;
        }
        await page.locator('[data-view="request"]').tap();
        assert.equal(await page.locator('#mock-bitrix-form input').inputValue(),'Черновик');

        await page.evaluate(()=>window.__back());
        const service=page.locator('.service-card').filter({has:page.getByRole('heading',{name:'Сайты с помощью AI',exact:true})});
        await service.getByRole('button').tap();
        assert.equal(await page.locator('#request-topic').textContent(),'Сайты с помощью AI');
        await page.locator('#mock-bitrix-form input').fill('Тест');
        await page.locator('#mock-bitrix-form button').tap();
        assert.equal(await page.evaluate(()=>window.__bitrixSubmit),1);

        await page.locator('[data-view="services"]').tap();
        await page.locator('#choose-pilot').tap();
        assert.equal(await page.locator('#request-topic').textContent(),'Пробная задача');
        await page.locator('[data-view="services"]').tap();
        await page.locator('#choose-other').tap();
        assert.equal(await page.locator('#request-topic').isHidden(),true);
        assert.deepEqual(requests,{form:1,widget:1});
        assert.equal(page.url(),base);
        assert.equal(context.pages().length,1);
        assert.deepEqual(await page.evaluate(()=>window.__sent),[]);
        assert.deepEqual(await page.evaluate(()=>window.__siteLinks),[]);
        await page.locator('[data-view="contact"]').tap();
        await page.locator('#personal-link').tap();
        assert.deepEqual(await page.evaluate(()=>window.__telegramLinks),[site.telegram]);
        for (const [selector] of socialLinks) await page.locator(selector).tap();
        assert.deepEqual(await page.evaluate(()=>window.__siteLinks),socialLinks.map(([,url])=>url));
        assert.equal(context.pages().length,1);
        assert.equal(page.url(),base);
        await context.close();
      }
    }

    const failed=await browser.newContext();
    await failed.route('**/catalog.json',route=>route.fulfill({status:503,body:'unavailable'}));
    await failed.route(sdkURL,route=>route.abort());
    const requests=await mockBitrix(failed,{failForm:true});
    const page=await failed.newPage();
    page.on('pageerror',error=>errors.push(error.message));
    await page.goto(base);
    await page.getByText('Не удалось загрузить услуги.',{exact:false}).waitFor();
    await page.locator('#hero-request').click();
    await page.getByText('Не удалось загрузить форму.',{exact:false}).waitFor();
    await page.locator('#request-contact-fallback').click();
    assert.equal(await page.locator('#personal-link').isVisible(),true);
    for (const [selector,url] of socialLinks) {
      await failed.route(url,route=>route.fulfill({contentType:'text/html',body:'<!doctype html><title>Test social profile</title>'}));
      const [popup]=await Promise.all([page.waitForEvent('popup'),page.locator(selector).click()]);
      await popup.waitForURL(url);
      await popup.close();
    }
    assert.deepEqual(requests,{form:1,widget:1});
    assert.equal(page.url(),base);
    await failed.close();

    assert.deepEqual(errors,[]);
    console.log('PASS: '+layouts+' theme and viewport layouts, hero navigation, direct contacts and social links, lazy Bitrix24 form and persistent chat, draft preservation, mobile touch, failure fallbacks and no external navigation during applications.');
  } finally {
    await browser.close();
  }
})().catch(error=>{console.error(error);process.exit(1)});
