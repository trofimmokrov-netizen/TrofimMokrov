#!/usr/bin/env python3
"""Generate portable static HTML with Python's standard library."""
import json
import os
import re
from datetime import date
from html import escape as e
from pathlib import Path
from urllib.parse import quote, urlsplit
ROOT=Path(__file__).resolve().parents[1]
def read(path): return json.loads((ROOT/path).read_text())
site=read('content/site.json'); services=read('content/services.json'); projects=read('content/projects.json')
telegram_projects=read('content/telegram-projects.json')
pilot=read('content/pilot.json')
articles=[json.loads(p.read_text()) for p in sorted((ROOT/'content/articles').glob('*.json'))]
base=site.get('base_url','').rstrip('/')
if base and (urlsplit(base).scheme!='https' or not urlsplit(base).netloc or urlsplit(base).query or urlsplit(base).fragment): raise ValueError('base_url must be an absolute HTTPS URL without query or fragment')
bot_url=site['bot_url'].rstrip('/')
bot_address=urlsplit(bot_url)
if bot_address.scheme!='https' or bot_address.netloc!='t.me' or not re.fullmatch(r'/[A-Za-z0-9_]{5,32}',bot_address.path) or bot_address.query or bot_address.fragment:raise ValueError('bot_url must be a public HTTPS t.me username link')
for group in (services,projects,articles):
 keys=[item.get('slug',item.get('id')) for item in group]
 if len(keys)!=len(set(keys)): raise ValueError('Duplicate identifiers')
 for key in keys:
  if not re.fullmatch('[a-z0-9-]+',key or ''):raise ValueError('Invalid identifier')
def icon(path):return '<svg class="ui-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="'+path+'"/></svg>'
ICONS={
 '↗':icon('M5 19 19 5M5 5h14v14'),
 '→':icon('M4 12h16m-6-6 6 6-6 6'),
 '↔':icon('M4 12h16M9 7l-5 5 5 5m6-10 5 5-5 5'),
 '▯':icon('M7 3h10v18H7zM10 17h4'),
 '⌘':icon('M8 4h8v16H8zM4 8h16v8H4z'),
 '✳':icon('M12 2v20M2 12h20M5 5l14 14M5 19 19 5'),
 '≋':icon('M3 5h18M3 12h13M3 19h18'),
 '⊞':icon('M3 3h18v18H3zM12 3v18M3 12h18'),
 '◇':icon('m12 3 9 9-9 9-9-9z')}
TELEGRAM_ICON=icon('M21 3 3 10.5l6.5 2.7L18 7l-6.5 8 6 5L21 3zM9.5 13.2l2 6 2.4-2.2')
MENU_ICON=icon('M4 7h16M4 12h16M4 17h16')
MENU_CLOSE_ICON=icon('m6 6 12 12M18 6 6 18')
INSTAGRAM_ICON=icon('M7 3h10a4 4 0 0 1 4 4v10a4 4 0 0 1-4 4H7a4 4 0 0 1-4-4V7a4 4 0 0 1 4-4zM15.5 12a3.5 3.5 0 1 1-7 0 3.5 3.5 0 0 1 7 0zM17.5 6.5h.01')
SOCIAL_PROFILES=(
 ('instagram','Instagram',INSTAGRAM_ICON),
 ('telegram','Личный Telegram',TELEGRAM_ICON),
)
def social_profile(key,label,symbol):
 url=site[key]
 return f'<a class="social-link" href="{e(url,quote=True)}"><span class="social-icon">{symbol}</span>{label}</a>'
def social_links():
 return '<nav class="social-links" aria-label="Социальные сети">'+''.join(social_profile(*profile) for profile in SOCIAL_PROFILES)+'</nav>'
NAV=[('index.html','Главная'),('about.html','Обо мне'),('services.html','Услуги и цены'),('portfolio.html','Портфолио'),('articles.html','Статьи'),('updates.html','Обновления'),('contact.html','Контакты')]
BITRIX_SITE_WIDGET='''<script>
(function (w, d, u) {
  var s = d.createElement('script');
  s.async = true;
  s.src = u + '?' + (Date.now() / 60000 | 0);
  var h = d.getElementsByTagName('script')[0];
  h.parentNode.insertBefore(s, h);
})(window, document, 'https://cdn-ru.bitrix24.ru/b38606320/crm/site_button/loader_3_gbqxj4.js');
</script>'''
outputs=[]
def href(current,target):
 if current=='404.html' and base:return base+'/'+target
 return os.path.relpath(ROOT/target,(ROOT/current).parent).replace(os.sep,'/')
def link(current,target):return e(href(current,target),quote=True)
def portrait(current):
 return f'''<figure class="owner-portrait"><img src="{link(current,'assets/trofim-mokrov-portrait.jpg')}" width="1024" height="1536" alt="{e(site['name'])}" decoding="async"><figcaption>{e(site['name'])}<span>{e(site['tagline'])}</span></figcaption></figure>'''
def bot_link(service_id=None):
 payload='service_'+service_id if service_id else 'site'
 if not re.fullmatch('[A-Za-z0-9_-]{1,64}',payload):raise ValueError('Invalid Telegram start payload')
 return e(bot_url+'?start='+payload,quote=True)
def telegram_action(service_id=None,secondary=False):
 style=' secondary' if secondary else ''
 return f'<a class="button telegram-action{style}" href="{bot_link(service_id)}">{TELEGRAM_ICON}Обсудить в Telegram</a>'
def form_action(current):
 return f'<a class="button form-action" href="{link(current,"contact.html")}#request-form">Заполнить форму ↗</a>'
def eyebrow(text):return f'<div class="eyebrow">{e(text)}</div>'
def contact(current,service_id=None):return f'''<section class="contact-banner" data-reveal><h2>Обсудим вашу задачу</h2><p>Расскажите, какой результат нужен. Я помогу определить объём работ, стоимость и сроки.</p><div class="actions">{form_action(current)}{telegram_action(service_id,secondary=True)}</div></section>'''
def steps():return '''<div><article class="step"><span>01</span><div><h3>Разбираемся в задаче</h3><p>Что сейчас не работает, кто пользуется инструментами и какой результат нужен.</p></div></article><article class="step"><span>02</span><div><h3>Согласуем состав и стоимость</h3><p>Фиксируем объём, сроки, порядок правок и условия дальнейшей поддержки.</p></div></article><article class="step"><span>03</span><div><h3>Создаём и проверяем</h3><p>Проверяем результат на согласованных примерах и разбираемся, как им пользоваться.</p></div></article></div>'''
def pilot_section(current):
 examples=''.join(f'<li>{e(item)}</li>' for item in pilot['examples'])
 return f'''<section class="section" id="pilot"><div class="section-head">{eyebrow(pilot['name'])}<h2>{e(pilot['headline'])}</h2><p>{e(pilot['intro'])}</p></div><div class="grid"><article class="card"><h3>1. Выбираем небольшой результат</h3><p>Что можно обсудить:</p><ul>{examples}</ul></article><article class="card"><h3>2. Согласуем условия</h3><p>{e(pilot['terms'])}</p><p>{e(pilot['continuation'])}</p></article><article class="card"><h3>3. По желанию — кейс в портфолио</h3><p>{e(pilot['portfolio'])}</p></article></div><div class="actions"><a class="button" href="{e(bot_url,quote=True)}?start=pilot" target="_blank" rel="noopener noreferrer">Обсудить пробную задачу ↗</a><a class="button secondary" href="{e(site['telegram'])}" target="_blank" rel="noopener noreferrer">Задать вопрос лично</a></div></section>'''
def article_cards(current,limit=None):
 out=''
 for a in articles[:limit]:
  out+=f'''<article class="card article-card" data-reveal><div class="category">{e(a['category'])}</div><h2>{e(a['title'])}</h2><p>{e(a['description'])}</p><a class="text-link" href="{link(current,'articles/'+a['slug']+'.html')}">Читать статью ↗</a></article>'''
 return '<div class="grid">'+out+'</div>'
def heading(label,title,desc):return f'<section class="page-heading">{eyebrow(label)}<h1>{title}</h1><p class="lead">{e(desc)}</p></section>'
def render(path,title,description,body,active=None,article=False):
 if path in ('services.html','portfolio.html'):
  body=body.replace(contact(path),pilot_section(path)+contact(path),1)
 nav=''.join(f'<a href="{link(path,p)}"'+(' aria-current="page"' if p==(active or path) else '')+f'>{e(label)}</a>' for p,label in NAV)
 nav+=f'<a href="{e(bot_url,quote=True)}?start=app">Мини-приложение ↗</a>'
 canonical=f'<link rel="canonical" href="{e(base+"/"+path)}">\n<meta property="og:url" content="{e(base+"/"+path)}">' if base else ''
 font_preload=f'<link rel="preload" href="{link(path,"assets/fonts/nunito-semibold.woff2")}" as="font" type="font/woff2" crossorigin>' if path=='index.html' else ''
 ogimage=f'<meta property="og:image" content="{e(base)}/assets/share-card.png"><meta property="og:image:secure_url" content="{e(base)}/assets/share-card.png"><meta property="og:image:type" content="image/png"><meta property="og:image:width" content="1200"><meta property="og:image:height" content="630"><meta property="og:image:alt" content="Трофим Мокров — сайты, AI и автоматизация"><meta name="twitter:card" content="summary_large_image"><meta name="twitter:image" content="{e(base)}/assets/share-card.png">' if base else ''
 full_title='Трофим Мокров — сайты, AI и автоматизация' if path=='index.html' else title+' — Трофим Мокров'
 schema={'@context':'https://schema.org','@type':'Person','name':site['name'],'email':site['email'],'telephone':site['phone'],'sameAs':[site['telegram']]}
 if base:schema['url']=base+'/'
 content=f'''<!doctype html>
<html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta name="theme-color" content="#f5f5ee"><title>{e(full_title)}</title><meta name="description" content="{e(description)}"><meta property="og:title" content="{e(full_title)}"><meta property="og:description" content="{e(description)}"><meta property="og:type" content="{'article' if article else 'website'}"><meta property="og:locale" content="ru_RU"><meta property="og:site_name" content="Трофим Мокров">{canonical}{ogimage}{font_preload}<link rel="icon" href="{link(path,'logo.svg')}" type="image/svg+xml"><link rel="stylesheet" href="{link(path,'assets/styles.css')}"><script>document.documentElement.classList.add('js');</script><script src="{link(path,'assets/main.js')}" defer></script><script type="application/ld+json">{json.dumps(schema,ensure_ascii=False).replace('<','&lt;')}</script></head>
<body><a class="skip" href="#main">К содержанию</a>
<div class="wrap">
 <header class="site-header">
  <a class="brand" href="{link(path,'index.html')}"><img src="{link(path,'logo.svg')}" width="36" height="36" alt=""><span>{e(site['name'])}</span></a>
  <div class="header-actions">
   <a class="header-telegram" href="{bot_link()}" aria-label="Открыть Telegram-бота">{TELEGRAM_ICON}Telegram</a>
   <button class="menu-button" type="button" aria-controls="main-nav" aria-expanded="false" aria-label="Меню"><span class="menu-open-icon" aria-hidden="true">{MENU_ICON}</span><span class="menu-close-icon" aria-hidden="true">{MENU_CLOSE_ICON}</span></button>
  </div>
  <nav id="main-nav" aria-label="Основная навигация">{nav}</nav>
 </header>
 <main id="main">{body}</main>
 <footer class="footer">
  <div class="footer-name">© {e(site['name'])}</div>
  {social_links()}
  <div class="footer-links"><a href="{bot_link()}">Бот для заявок ↗</a><a href="{link(path,'contact.html')}">Контакты</a><a href="{link(path,'contact.html')}#payment">Оплата</a></div>
 </footer>
</div>
{BITRIX_SITE_WIDGET}
</body></html>'''
 for symbol,svg in ICONS.items():content=content.replace(symbol,svg)
 target=ROOT/path;target.parent.mkdir(parents=True,exist_ok=True);target.write_text(content+'\n');outputs.append(path)
faqs=[('Можно сначала посмотреть, каким будет сайт?', 'Да. Сначала показываю предварительный вариант, чтобы вы могли оценить идею и подачу. После обсуждения согласуем дальнейшую доработку, стоимость и условия оплаты. Базовый сайт с помощью AI — от 10 000 ₽.'),('Можно дополнить сайт после запуска?', 'Да. Можно начать с небольшой версии, а затем добавлять услуги, статьи, проекты и страницы. Новые задачи и их стоимость согласуются отдельно.'),('Кто следит за системой после запуска?', 'При подключении проверяю согласованный сценарий и объясняю его работу. Дальнейшее наблюдение и изменения можно поручить мне отдельно: заранее согласуем график проверок, канал связи, сроки реакции и стоимость. Постоянная доступность и устранение любых технических проблем в разовое подключение не входят.'),('AI-агент публикует во всех соцсетях?', 'Подключаем согласованные площадки, где доступны необходимые интеграции. До оплаты проверяем возможности ваших аккаунтов и фиксируем состав. Обещать одинаковую работу во всех соцсетях без такой проверки было бы некорректно.'),('Что входит в подключение AI-агента за 10 000 ₽?', 'Подбор сценария, подключение согласованных аккаунтов, настройка стиля и расписания, тестовая публикация и объяснение работы. Подписки сервисов, нестандартная разработка и дальнейшее ведение оплачиваются отдельно.'),('Можно обратиться с личной задачей, без бизнеса?', 'Да. Можно обсудить настройку компьютера или приложений, личный сайт, AI-инструменты и контент для собственного проекта. Решение и объём подбираются индивидуально.'),('Можно начать с небольшой задачи?','Да. Можно настроить одно устройство, подготовить изображение или автоматизировать один понятный процесс. Состав небольшой задачи согласуем заранее.'),('Что нужно для расчёта стоимости?','Расскажите, чем занимаетесь, какой результат нужен и какими инструментами уже пользуетесь. Примеры и ссылки помогут точнее определить объём. Пароли и персональные данные в первом сообщении не нужны.'),('Что означает цена «от»?','Это стоимость базового объёма, описанного в услуге. Дополнительные страницы, сценарии, площадки и нестандартные интеграции оцениваются отдельно до начала работы.'),('Вы гарантируете рост продаж?','Нет. Я отвечаю за согласованный результат работы: сайт, контент, настройку или сценарий. Продажи зависят также от продукта, аудитории, рекламы и обработки обращений.'),('Что со сроками, правками и поддержкой?','Сроки, количество согласований и условия поддержки определяются для конкретной задачи до начала работы. Бессрочная поддержка и неограниченные правки в тарифы не входят.')]
bot_service=next(s for s in services if s['id']=='telegram-bots')
faqs.extend([('Можно заказать бот и мини-приложение как TrofimAI?', 'Да. Базовая настройка под ваш стиль — от 10 000 ₽: меню, услуги, ссылки на сайт, форма заявки и уведомление владельцу. Точный состав согласуем до начала. Можно предложить свой бюджет.'),('Как оплачивается дальнейшая работа бота?',bot_service['separate'])])

def faq_section(items):
 entries=''.join(f'<details><summary>{e(question)}</summary><p>{e(answer)}</p></details>' for question,answer in items)
 return f'<section class="section home-faq" data-reveal><div class="section-head"><h2>Частые вопросы</h2></div><div class="faq">{entries}</div></section>'
# Home
p='index.html'
featured_ids=('websites','telegram-bots','business-system','automation','ai-agents','social-actions')
services_by_id={service['id']:service for service in services}
featured=''.join(
 f'''<a class="home-service" href="services.html#{service['id']}">
 <span class="home-service-icon" aria-hidden="true">{e(service['icon'])}</span>
 <h3>{e(service['name'])}</h3>
 <p class="home-service-summary">{e(service['summary'])}</p>
 <span class="home-service-meta"><span class="home-service-price">{e(service['price'])}</span><span class="tile-arrow" aria-hidden="true">↗</span></span></a>'''
 for service in (services_by_id[key] for key in featured_ids)
)
featured_project=next(project for project in projects if project['slug']=='ksusha-epoxy')
telegram_project_names=''.join(f'<li>{e(project["name"])}</li>' for project in telegram_projects)
body=f'''
<section class="hero" aria-labelledby="home-title">
 <div class="hero-copy">
  {eyebrow('Сайты · Telegram · Автоматизация')}
  <h1 id="home-title">{e(site['name'])}</h1>
  <p class="lead">Разрабатываю сайты и Telegram-ботов, подключаю Битрикс24 и автоматизирую рутинные задачи бизнеса.</p>
  <div class="actions hero-actions">
   {form_action(p)}
   {telegram_action(secondary=True)}
  </div>
  {social_links()}
 </div>
 <div class="hero-portrait">
  <img src="{link(p,'assets/trofim-mokrov-portrait-800.webp')}"
   srcset="{link(p,'assets/trofim-mokrov-portrait-240.webp')} 240w, {link(p,'assets/trofim-mokrov-portrait-800.webp')} 800w"
   sizes="(max-width: 600px) 76px, (max-width: 900px) 32vw, 380px"
   width="800" height="1200" alt="{e(site['name'])}" decoding="async" fetchpriority="high">
 </div>
</section>
<section class="section home-services" aria-labelledby="home-services-title" data-reveal>
 <div class="section-head"><h2 id="home-services-title">Чем могу помочь</h2><a class="text-link action-link" href="services.html">Все услуги ↗</a></div>
 <div class="home-service-list">{featured}</div>
</section>
<section class="section home-projects" aria-labelledby="home-projects-title" data-reveal>
 <div class="section-head"><h2 id="home-projects-title">Избранные проекты</h2><a class="text-link action-link" href="portfolio.html">Все проекты ↗</a></div>
 <div class="project-showcase">
  <a class="project-feature" href="portfolio.html#{e(featured_project['slug'])}">
   <div class="project-feature-media"><img src="{link(p,'assets/ksusha-site-cover.webp')}" width="896" height="653" alt="{e(featured_project['alt'])}" loading="lazy" decoding="async"></div>
   <div class="project-feature-caption">
    <div><h3>Сайт ZEMLYANOVVA EPOXY</h3><p>Коллекция авторских столов из дерева и смолы.</p></div><span class="tile-arrow" aria-hidden="true">↗</span>
   </div>
  </a>
  <article class="project-cluster">
   <span class="project-cluster-icon">{TELEGRAM_ICON}</span>
   <h3>Боты и мини-приложения</h3>
   <ul>{telegram_project_names}</ul>
   <a class="text-link action-link" href="portfolio.html#telegram-projects">Проекты в Telegram ↗</a>
  </article>
 </div>
</section>
'''
body+=faq_section(faqs[:2]+faqs[-2:-1])+contact(p)
render(p,'Сайты, Telegram и автоматизация','Трофим Мокров: создание сайтов и Telegram-ботов, настройка Битрикс24 и AI-инструментов для бизнеса.',body)
# About
p='about.html'
body=heading('Обо мне','Технологии — под задачу.<br>Работа — с человеком.','Я Трофим Мокров. Работаю на стыке IT, искусственного интеллекта и практических задач. Помогаю бизнесу и частным клиентам подобрать и настроить цифровые инструменты.')
body+=f'''<section class="section split"><div class="bio"><p>Этот сайт я тоже создаю с помощью AI-агента: от идеи и структуры до страниц и последующих обновлений. Это пример моего подхода — использовать AI как рабочий инструмент и проверять полученный результат.</p><p>Моё основное направление — AI для бизнеса и повседневной работы: контент-агенты, автоматизация, сайты и цифровые инструменты.</p><p>Учился системному администрированию. Уверенно работаю с компьютером и использую техническую базу, чтобы разбираться в настройках, соединять инструменты и объяснять их работу понятным языком.</p><p>Сейчас развиваю направление AI-агентов, которые помогают готовить контент и публиковать его на нескольких согласованных площадках. Для каждого проекта важны собственные темы, стиль и порядок согласования.</p><p>Помогаю продумать идею, название и визуальный стиль под конкретный бизнес. Могу подключиться к отдельной задаче: настроить телефон для публикаций, подготовить изображение или собрать сайт. А могу помочь объединить площадки и процессы в понятную систему.</p><p>Моя специализация — связать AI, контент и техническую настройку в работающий процесс. Ценность такого подхода — в понимании всей цепочки: от идеи публикации до её выхода и проверки результата.</p><p>По отдельной договорённости могу сопровождать систему: проверять публикации, разбирать сбои и корректировать сценарии. Заранее определяем, что именно я отслеживаю, как часто проверяю и какие изменения входят в работу.</p><p>Мне важно разобраться в вашей работе: что повторяется, что отнимает время и где клиенту сложно сделать следующий шаг. Инструменты подбираю после этого.</p></div><div>{portrait(p)}{eyebrow('Как проходит сотрудничество')}{steps()}</div></section><section class="dark" data-reveal><h2>Не обязательно<br>делать всё сразу.</h2><p>Начнём с самого полезного изменения. Например, уточним предложение на сайте, упорядочим публикации или уберём ручной перенос заявок. Следующие шаги можно определить после проверки результата.</p></section><section class="section"><div class="section-head"><h2>Что можно поручить мне</h2><p>Отдельные задачи и сочетание нескольких направлений.</p></div><div class="grid"><article class="card"><h3>Представить бизнес</h3><p>Сайт, описания услуг, оформление площадок и актуальные контакты.</p></article><article class="card"><h3>Организовать контент</h3><p>План публикаций, посты, AI-изображения и настройка устройств.</p></article><article class="card"><h3>Упростить процессы</h3><p>Сценарии передачи данных, уведомления и связки инструментов.</p></article></div></section>'''+contact(p)
body=body.replace(contact(p),'''<section class="section"><div class="section-head"><h2>Кому могу быть полезен</h2><p>Не обязательно разбираться в AI или приходить с готовым техническим заданием.</p></div><div class="grid"><article class="card"><h3>Компаниям из разных сфер</h3><p>Помогу организовать контент, представить услуги в интернете и подобрать автоматизацию под процессы вашей команды.</p></article><article class="card"><h3>Экспертам и самостоятельным специалистам</h3><p>Личный сайт, индивидуальный стиль, регулярные публикации и инструменты, которые освобождают время для основной работы.</p></article><article class="card"><h3>Частным клиентам</h3><p>Настройка компьютера и приложений, знакомство с AI-инструментами и помощь с личным цифровым проектом.</p></article></div></section>'''+contact(p))
render(p,'Обо мне','Трофим Мокров: подход к созданию сайтов, автоматизации и контенту. Сначала задача бизнеса, затем инструменты и проверяемый результат.',body)
# Services
p='services.html';body=heading('Услуги и цены','Понятный объём.<br>Понятная стоимость.','Для бизнеса и личных задач: от подключения AI-агента за 10 000 ₽ до сайта, настройки компьютера или индивидуальной автоматизации. Ниже — состав услуг и отдельные расходы.')
body+='<nav class="service-index" aria-label="Список услуг">'+''.join(f'<a href="#{s["id"]}">{e(s["name"])}</a>' for s in services)+'</nav>'
for s in services:
 inc=''.join(f'<li>{e(item)}</li>' for item in s['includes'])
 body+=f'''<section class="service-detail" id="{s['id']}" data-reveal><div class="detail-top"><div><h2>{e(s['name'])}</h2><p>{e(s['audience'])}</p></div><div class="price">{e(s['price'])}<small>{e(s['unit'])}</small></div></div><div class="detail-body"><div><h3>Что входит</h3><ul>{inc}</ul><h3>Что получите</h3><p>{e(s['result'])}</p></div><div><h3>Что увеличивает стоимость</h3><p>{e(s['extra'])}</p><h3>Отдельные расходы</h3><p>{e(s['separate'])}</p><div class="actions">{telegram_action(s['id'])}<a class="text-link action-link" href="{e(site['telegram'])}">Написать лично ↗</a></div></div></div></section>'''
body+='<p class="note">Цены указаны для базового объёма. Сроки, объём работ, критерии приёмки и поддержка согласуются до начала проекта.</p>'+faq_section(faqs)+contact(p)
render(p,'Услуги и цены','Состав и стоимость услуг: сайты, автоматизация, настройка устройств, AI-изображения, посты, ведение соцсетей и запуск цифровой инфраструктуры.',body)
# Portfolio
p='portfolio.html';body=heading('Портфолио','Работы с понятным<br>контекстом.','Здесь — проекты с описанием задачи и выполненной работы. В каждом проекте указаны мой вклад и границы подтверждённых результатов.')
body+='<section class="section telegram-projects" id="telegram-projects" aria-labelledby="telegram-projects-title"><div class="section-head"><h2 id="telegram-projects-title">Боты и мини-приложения в Telegram</h2></div><div class="grid">'
for project in telegram_projects:
 handle=project['handle']
 bot_profile='https://t.me/'+quote(handle,safe='')
 website=''
 if project.get('website'):
  website=f'<a class="text-link action-link bot-project-site" href="{e(project["website"],quote=True)}" target="_blank" rel="noopener noreferrer">{e(project["website_label"])} ↗</a>'
 body+=f'''<article class="bot-project" data-reveal>
 <h3>{e(project['name'])}</h3>
 <p>{e(project['description'])}</p>{website}
 <a class="bot-project-link" href="{e(bot_profile,quote=True)}" target="_blank" rel="noopener noreferrer">
  {TELEGRAM_ICON}<span><strong>Открыть в Telegram</strong><small>@{e(handle)}</small></span><span class="bot-project-arrow" aria-hidden="true">↗</span>
 </a>
</article>'''
body+='</div></section>'
for item in projects:
 body+=f'''<section class="section" id="{e(item['slug'])}"><span class="project-label">{e(item['kind'])}</span><h2>{e(item['title'])}</h2><p class="lead">{e(item['description'])}</p>'''
 if item.get('image'):
  body+=f'''<figure class="project-image"><img src="{e(item['image'])}" width="1440" height="1050" loading="lazy" alt="{e(item['alt'])}">'''
  if item.get('watermark'):body+='<figcaption class="watermark">Трофим Мокров</figcaption>'
  body+='</figure>'
 if item.get('diagram'):
  body+='<div class="dark case-map"><div class="eyebrow">Направления работы в проекте</div><div class="flow"><span>Оформление площадок</span><b aria-hidden="true">↔</b><span>Посты и публикации</span><b aria-hidden="true">↔</b><span>Сайт и инструменты</span></div><p>Схема участия автора, а не скриншот интерфейса или подтверждение коммерческих результатов.</p></div>'
 if item.get('url'):
  body+=f'<p><a class="text-link" href="{e(item["url"])}" target="_blank" rel="noopener noreferrer">{e(item.get("url_label","Открыть проект"))} ↗</a></p>'
 body+='<div class="project-details">'
 for label,key in [('Задача','task'),('Что сделано','work'),('Инструменты','tools'),('Результат','result')]:body+=f'<div><h3>{label}</h3><p>{e(item[key])}</p></div>'
 body+='</div></section>'
body+=contact(p);render(p,'Портфолио','Проекты Трофима Мокрова: сайт Ксении ZEMLYANOVVA EPOXY, цифровое оформление «Древесного замысла» и собственный сайт с помощью AI.',body)
# Articles
p='articles.html';body=heading('Статьи','Сначала разобраться.<br>Потом внедрять.','Практические материалы о сайтах, автоматизации и контенте. Без обещаний волшебных инструментов и гарантированных продаж.')+article_cards(p)+contact(p)
render(p,'Статьи о сайтах, AI и автоматизации','Шесть практических руководств: выбор сайта, первая автоматизация, цифровая инфраструктура, AI-контент, соцсети и стоимость внедрения.',body)
for a in articles:
 p='articles/'+a['slug']+'.html';body=f'<div class="breadcrumbs"><a href="{link(p,"articles.html")}">Статьи</a> / {e(a["category"])}</div>'+heading(a['category'],e(a['title']),a['description'])
 body+='<article class="reading"><nav class="article-toc" aria-label="Содержание статьи"><div><strong>В этой статье</strong><ol>'
 for i,s in enumerate(a['sections'],1):body+=f'<li><a href="#part-{i}">{e(s["heading"])}</a></li>'
 body+='</ol></div></nav>'
 for i,s in enumerate(a['sections'],1):body+=f'<section id="part-{i}"><h2>{e(s["heading"])}</h2><p>{e(s["text"])}</p></section>'
 body+=f'<p class="note">Примеры в статье иллюстрируют подход и не описывают клиентские результаты. Состав внедрения зависит от конкретной задачи и возможностей выбранных сервисов.</p><a class="text-link" href="{link(p,"services.html")}#{e(a["service"])}">Услуга по этой теме ↗</a></article>'+contact(p,a['service'])
 render(p,a['title'],a['description'],body,active='articles.html',article=True)
# Contact
p='contact.html';body=heading('Контакты','Обсудим вашу задачу','Оставьте заявку на сайте или напишите мне напрямую.')
body+='''
<div class="contact-layout">
 <section class="request-form" id="request-form" aria-labelledby="request-form-title">
  <h2 id="request-form-title">Оставить заявку</h2>
  <div class="request-form-content">
  <div id="request-form-status" class="request-form-status" role="status"></div>
  <script data-b24-form="inline/25/h8a51a" data-b24-form-telemetry-sign="v1:25:site.bd5cb31496b0978c850786c0526098386316cc31190a6437e3d5b2a90988bd56" data-skip-moving="true">
  (function (w, d, u) {
    var s = d.createElement('script');
    s.async = true;
    s.src = u + '?' + (Date.now() / 180000 | 0);
    s.addEventListener('error', function () {
      d.getElementById('request-form-status').textContent = 'Форма не загрузилась. Вы можете связаться со мной через Telegram или почту.';
    });
    var h = d.getElementsByTagName('script')[0];
    h.parentNode.insertBefore(s, h);
  })(window, document, 'https://cdn-ru.bitrix24.ru/b38606320/crm/form/loader_25.js');
  </script>
  <noscript><p>Для загрузки формы нужен JavaScript. Вы можете связаться со мной через Telegram или почту.</p></noscript>
  </div>
 </section>
 <section class="contact-methods" aria-labelledby="contact-methods-title">
  <h2 id="contact-methods-title">Другие способы связи</h2>
  <div class="contact-list">
'''
telegram_handle='@'+urlsplit(site['telegram']).path.strip('/')
for label,value,url,symbol in [
 ('Личный Telegram',telegram_handle,site['telegram'],TELEGRAM_ICON),
 ('Telegram-бот','@'+bot_address.path.lstrip('/'),bot_link(),icon('M12 3v3M9 3h3M6 7h12a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V9a2 2 0 0 1 2-2zM2 12h2m16 0h2M8 12h1m6 0h1m-7 3h6')),
 ('Instagram','@'+urlsplit(site['instagram']).path.strip('/'),site['instagram'],INSTAGRAM_ICON),
 ('Электронная почта',site['email'],'mailto:'+site['email'],icon('M4 6h16v12H4zM4 7l8 6 8-6')),
 ('Телефон',site['phone_display'],'tel:'+site['phone'],icon('M7 4h3l1 4-2 2a14 14 0 0 0 5 5l2-2 4 1v3a3 3 0 0 1-3 3C10 20 4 14 4 7a3 3 0 0 1 3-3z')),
]:
 body+=f'''<a class="contact-row" href="{e(url,quote=True)}"><span class="contact-row-icon">{symbol}</span>
 <span class="contact-row-copy"><strong>{e(label)}</strong><small>{e(value)}</small></span><span class="contact-row-arrow" aria-hidden="true">↗</span></a>'''
body+=f'''</div>
 <a class="telegram-qr-card" id="telegram" href="{e(site['telegram'],quote=True)}">
  <span><strong>QR-код личного Telegram</strong><small>{e(telegram_handle)}</small></span>
  <img src="{link(p,'assets/telegram-qr.svg')}" width="116" height="116" alt="" loading="lazy">
 </a>
 </section></div>'''
payment_methods=(
 ('USDT','TRON (TRC-20)',site['usdt_tron_address'],'assets/usdt-tron-qr.svg','Tronscan','https://tronscan.org/address/{}/transactions'),
 ('Bitcoin','Сеть Bitcoin (BTC)',site['bitcoin_address'],'assets/bitcoin-qr.svg','Blockchair','https://blockchair.com/bitcoin/address/{}'),
)
body+='<section class="payment-section" id="payment" aria-labelledby="payment-title"><h2 id="payment-title">Оплата в криптовалюте</h2><div class="payment-grid">'
for currency,network,address,qr,explorer,explorer_url in payment_methods:
 body+=f'''
 <div class="payment-method">
  <div class="wallet-heading">
   <h3>{currency}</h3>
   <p>{network}</p>
  </div>
  <img class="wallet-qr" src="{link(p,qr)}" width="128" height="128" alt="QR-код адреса {currency}" loading="lazy">
  <div class="wallet-address"><code>{e(address)}</code></div>
  <div class="wallet-actions">
   <button class="button secondary wallet-copy" type="button" aria-label="Скопировать адрес {currency}" hidden>Скопировать адрес</button>
   <a class="button secondary wallet-explorer" href="{e(explorer_url.format(address),quote=True)}" target="_blank" rel="noopener noreferrer"><span class="sr-only">Проверить адрес в </span>{explorer} ↗<span class="sr-only"> (в новой вкладке)</span></a>
  </div>
  <p class="wallet-status" role="status"></p>
 </div>
'''
body+='</div></section>'
render(p,'Контакты','Обсудить сайт, автоматизацию или контент с Трофимом Мокровым: Telegram @TrofimMokrov, trofimmokrov@gmail.com, +7 (915) 998-25-54.',body)
# Site news and owner-approved updates from the private Telegram publishing queue.
p='updates.html'
body='<section class="page-heading"><h1>Обновления</h1><p class="lead">Новые проекты, услуги и изменения на сайте.</p></section>'
updates=[]
for source in (ROOT/'content/updates').glob('*.json'):
 item=json.loads(source.read_text())
 if not re.fullmatch(r'[0-9a-f]{32}',item.get('id','')):raise ValueError('Invalid update ID')
 updates.append(item)
if not updates:body+='<section class="section"><p class="lead">Здесь появятся заметки о новых проектах и работе над ними.</p></section>'
if updates:body+='<div class="updates-feed">'
for item in sorted(updates,key=lambda update:(update['date'],update['id']),reverse=True):
 published=date.fromisoformat(item['date'])
 body+=f'''<article class="section update-entry" id="post-{item['id']}" data-reveal><time datetime="{published.isoformat()}">{published:%d.%m.%Y}</time><h2>{e(item['title'])}</h2>'''
 image=item.get('image')
 if image:
  if image!=f"assets/updates/{item['id']}.jpg":raise ValueError('Invalid update image')
  body+=f'<img class="update-photo" src="{e(image,quote=True)}" loading="lazy" alt="Фотография к публикации: {e(item["title"],quote=True)}">'
 body+='<div class="reading">'+''.join('<p>'+e(part).replace('\n','<br>')+'</p>' for part in item['text'].split('\n\n'))+'</div>'
 if item.get('links'):
  body+='<div class="update-links actions">'
  for cta in item['links']:
   target=cta['target']
   if not re.fullmatch(r'[a-z0-9-]+\.html(?:#[a-z0-9-]+)?',target):raise ValueError('Invalid update link')
   page,separator,fragment=target.partition('#')
   body+=f'<a class="text-link action-link" href="{link(p,page)}{separator}{fragment}">{e(cta["label"])} ↗</a>'
  body+='</div>'
 body+='</article>'
if updates:body+='</div>'
render(p,'Обновления','Новые публикации Трофима Мокрова о проектах, сайтах, AI и автоматизации.',body)
# Custom 404, portable relative to deployment path when URL is configured
p='404.html';body=heading('404 / Страница не найдена','Кажется, здесь<br>пока ничего нет.','Проверьте адрес или вернитесь на главную страницу.')+'<div class="actions" style="margin-bottom:70px"><a class="button" href="'+(e(base)+'/' if base else 'index.html')+'">На главную ↗</a></div>'
render(p,'Страница не найдена','Перейдите на главную страницу сайта Трофима Мокрова.',body)
(ROOT/'.nojekyll').touch()
if base:
 xml='<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'+''.join('<url><loc>'+e(base+'/'+p)+'</loc></url>' for p in outputs if p!='404.html')+'</urlset>\n'
 (ROOT/'sitemap.xml').write_text(xml);(ROOT/'robots.txt').write_text('User-agent: *\nAllow: /\nSitemap: '+base+'/sitemap.xml\n')
else:
 for file in ('sitemap.xml','robots.txt'):
  if (ROOT/file).exists():(ROOT/file).unlink()
miniapp=ROOT/'miniapp';miniapp.mkdir(exist_ok=True)
miniapp_catalog={'version':1,'site':{key:site[key] for key in ('name','telegram','instagram','vk','bot_url','email','base_url')},'services':services,'pilot':pilot}
(miniapp/'catalog.json').write_text(json.dumps(miniapp_catalog,ensure_ascii=False,indent=2)+'\n')
print(f'Built {len(outputs)} HTML pages and Mini App catalogue. '+('Canonical and sitemap enabled.' if base else 'Public URL unconfirmed; canonical and sitemap omitted.'))
