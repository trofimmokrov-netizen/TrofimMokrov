#!/usr/bin/env python3
"""Generate portable static HTML with Python's standard library."""
import json
import os
import re
from html import escape as e
from pathlib import Path
from urllib.parse import quote, urlsplit
ROOT=Path(__file__).resolve().parents[1]
def read(path): return json.loads((ROOT/path).read_text())
site=read('content/site.json'); services=read('content/services.json'); projects=read('content/projects.json')
articles=[json.loads(p.read_text()) for p in sorted((ROOT/'content/articles').glob('*.json'))]
base=site.get('base_url','').rstrip('/')
if base and (urlsplit(base).scheme!='https' or not urlsplit(base).netloc or urlsplit(base).query or urlsplit(base).fragment): raise ValueError('base_url must be an absolute HTTPS URL without query or fragment')
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
NAV=[('index.html','Главная'),('about.html','Обо мне'),('services.html','Услуги и цены'),('portfolio.html','Портфолио'),('articles.html','Статьи'),('contact.html','Контакты')]
outputs=[]
def href(current,target):
 if current=='404.html' and base:return base+'/'+target
 return os.path.relpath(ROOT/target,(ROOT/current).parent).replace(os.sep,'/')
def link(current,target):return e(href(current,target),quote=True)
def eyebrow(text):return f'<div class="eyebrow">{e(text)}</div>'
def contact(current):return f'''<section class="contact-banner" data-reveal>{eyebrow('Начнём с вашей задачи')}<h2>Расскажите, что хотите<br>сделать проще.</h2><p>Опишите бизнес, текущую задачу и желаемый результат. Обсудим подходящий объём, стоимость и сроки до начала работы.</p><div class="actions"><a class="button" href="{e(site['telegram'])}" target="_blank" rel="noopener noreferrer">Написать в Telegram <span aria-hidden="true">↗</span></a><a class="button secondary" href="mailto:{e(site['email'])}">Написать на почту</a></div></section>'''
def steps():return '''<div><article class="step"><span>01</span><div><h3>Разбираемся в задаче</h3><p>Что сейчас не работает, кто пользуется инструментами и какой результат нужен.</p></div></article><article class="step"><span>02</span><div><h3>Согласуем состав и стоимость</h3><p>Фиксируем объём, сроки, порядок правок и условия дальнейшей поддержки.</p></div></article><article class="step"><span>03</span><div><h3>Создаём и проверяем</h3><p>Проверяем результат на согласованных примерах и разбираемся, как им пользоваться.</p></div></article></div>'''
def article_cards(current,limit=None):
 out=''
 for a in articles[:limit]:
  out+=f'''<article class="card article-card" data-reveal><div class="category">{e(a['category'])}</div><h2>{e(a['title'])}</h2><p>{e(a['description'])}</p><a class="text-link" href="{link(current,'articles/'+a['slug']+'.html')}">Читать статью ↗</a></article>'''
 return '<div class="grid">'+out+'</div>'
def heading(label,title,desc):return f'<section class="page-heading">{eyebrow(label)}<h1>{title}</h1><p class="lead">{e(desc)}</p></section>'
def render(path,title,description,body,active=None,article=False):
 nav=''.join(f'<a href="{link(path,p)}"'+(' aria-current="page"' if p==(active or path) else '')+f'>{e(label)}</a>' for p,label in NAV)
 canonical=f'<link rel="canonical" href="{e(base+"/"+path)}">\n<meta property="og:url" content="{e(base+"/"+path)}">' if base else ''
 ogimage=f'<meta property="og:image" content="{e(base)}/brand-art.png"><meta property="og:image:alt" content="Концептуальная иллюстрация бренда Трофима Мокрова">' if base else ''
 schema={'@context':'https://schema.org','@type':'Person','name':site['name'],'email':site['email'],'telephone':site['phone'],'sameAs':[site['telegram']]}
 if base:schema['url']=base+'/'
 content=f'''<!doctype html>
<html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta name="theme-color" content="#16201c"><title>{e(title)} — Трофим Мокров</title><meta name="description" content="{e(description)}"><meta property="og:title" content="{e(title)} — Трофим Мокров"><meta property="og:description" content="{e(description)}"><meta property="og:type" content="{'article' if article else 'website'}"><meta property="og:locale" content="ru_RU"><meta property="og:site_name" content="Трофим Мокров">{canonical}{ogimage}<link rel="icon" href="{link(path,'logo.svg')}" type="image/svg+xml"><link rel="stylesheet" href="{link(path,'assets/styles.css')}"><script>document.documentElement.classList.add('js');</script><script src="{link(path,'assets/main.js')}" defer></script><script type="application/ld+json">{json.dumps(schema,ensure_ascii=False).replace('<','&lt;')}</script></head>
<body><a class="skip" href="#main">К содержанию</a><div class="wrap"><header><a class="brand" href="{link(path,'index.html')}"><img src="{link(path,'logo.svg')}" width="36" height="36" alt=""><span>Трофим Мокров<small>Сайты · AI · Автоматизация</small></span></a><button class="menu-button" type="button" aria-controls="main-nav" aria-expanded="false">Меню <span aria-hidden="true">↗</span></button><nav id="main-nav" aria-label="Основная навигация">{nav}</nav></header><main id="main">{body}</main><footer class="footer"><div>© Трофим Мокров<br>Технологии, которые работают на вас.</div><div class="footer-links"><a href="{e(site['telegram'])}" target="_blank" rel="noopener noreferrer">Telegram ↗</a><a href="mailto:{e(site['email'])}">Почта ↗</a><a href="tel:{e(site['phone'])}">{e(site['phone_display'])}</a></div></footer></div></body></html>'''
 for symbol,svg in ICONS.items():content=content.replace(symbol,svg)
 target=ROOT/path;target.parent.mkdir(parents=True,exist_ok=True);target.write_text(content+'\n');outputs.append(path)
# Home
p='index.html'
body=f'''<section class="hero">{eyebrow('Для предпринимателей, экспертов и небольших команд')}<h1>Меньше рутины.<br>Больше <em>возможностей.</em></h1><div class="hero-bottom"><div><p class="lead">Я Трофим Мокров. Создаю сайты, автоматизирую процессы и помогаю вести соцсети с помощью AI. Соединяю инструменты в систему, которой удобно пользоваться.</p><div class="actions"><a class="button" href="{site['telegram']}" target="_blank" rel="noopener noreferrer">Обсудить задачу ↗</a><a class="button secondary" href="services.html">Услуги и цены</a></div></div><div class="hero-note"><span class="sr-only">Сайты, контент и автоматизация под вашу задачу.</span><div class="living-note" aria-hidden="true"><span class="note-kicker">ТЕХНОЛОГИИ ПОД ВАШ БИЗНЕС</span><div class="phrase-stack"><span class="living-phrase is-current">Идеи становятся сайтами.</span><span class="living-phrase">Контент обретает характер.</span><span class="living-phrase">Рутина становится проще.</span></div></div><button class="motion-toggle" type="button" aria-label="Остановить смену фраз" aria-pressed="false" hidden>Пауза</button></div></div><div class="visual"><img src="assets/brand-art.webp" width="1536" height="1024" fetchpriority="high" alt="Абстрактная скульптура с переплетёнными вершинами в зелёных тонах"><div class="visual-copy"><h2>Ваш следующий<br>шаг — системный.</h2><p>От одной настройки до связанной цифровой инфраструктуры.</p></div><div class="visual-caption">Концептуальная иллюстрация бренда</div></div></section>
<section class="section"><div class="section-head"><div>{eyebrow('01 / Чем могу помочь')}<h2>От точечной задачи<br>до целой системы.</h2></div><p>Начать можно с одного инструмента. Расширять — когда в этом появляется смысл.</p></div><div class="grid">'''
for s in services:
 body+=f'''<article class="card" data-reveal><span class="card-number">{s['number']} / {e(s['name'])}</span><div class="icon" aria-hidden="true">{s['icon']}</div><h3>{e(s['name'])}</h3><p>{e(s['summary'])}</p><div class="price">{e(s['price'])}<small>{e(s['unit'])}</small></div><a class="text-link" href="services.html#{s['id']}">Что входит ↗</a></article>'''
body+='''</div><p class="note">Цены относятся к указанному стартовому объёму. Состав, сроки, правки и поддержка согласуются до начала работы. Сторонние сервисы оплачиваются отдельно.</p></section>'''
body+=f'''<section class="dark" data-reveal>{eyebrow('Как это работает вместе')}<h2>Вас находят.<br>Понимают предложение.<br>Знают, куда написать.</h2><div class="flow"><span>Яндекс Карты и соцсети</span><b aria-hidden="true">→</b><span>Сайт и полезный контент</span><b aria-hidden="true">→</b><span>Обращение и обработка</span></div><p>Создаю связку из сайта, площадок, контента и рабочих процессов. Чтобы обновлять информацию и работать с обращениями было проще.</p></section><section class="section split"><div>{eyebrow('02 / Подход')}<h2>Лично разбираюсь.<br>Понятно объясняю.</h2><p class="lead">Могу помочь с отдельной задачей или связать несколько направлений. Без обещаний, которые невозможно проверить.</p><a class="text-link" href="about.html">Подробнее обо мне ↗</a></div>{steps()}</section><section class="section"><div class="section-head"><div>{eyebrow('03 / Практика')}<h2>От оформления площадок<br>до своего сайта.</h2></div><p>«Древесный замысел» — контент и помощь с настройкой. Этот сайт — собственный проект. В каждом кейсе указан мой вклад.</p></div><a class="text-link" href="portfolio.html">Посмотреть проект ↗</a></section><section class="section"><div class="section-head"><div>{eyebrow('04 / Полезные материалы')}<h2>Разобраться до того,<br>как заказывать.</h2></div><a class="text-link" href="articles.html">Все статьи ↗</a></div>{article_cards(p,3)}</section><section class="section"><div class="section-head"><div>{eyebrow('05 / Частые вопросы')}<h2>Что важно знать<br>перед началом.</h2></div></div><div class="faq">'''
faqs=[('Можно начать с небольшой задачи?','Да. Можно настроить одно устройство, подготовить изображение или автоматизировать один понятный процесс. Состав небольшой задачи согласуем заранее.'),('Что нужно для расчёта стоимости?','Расскажите, чем занимаетесь, какой результат нужен и какими инструментами уже пользуетесь. Примеры и ссылки помогут точнее определить объём. Пароли и персональные данные в первом сообщении не нужны.'),('Что означает цена «от»?','Это стоимость базового объёма, описанного в услуге. Дополнительные страницы, сценарии, площадки и нестандартные интеграции оцениваются отдельно до начала работы.'),('Вы гарантируете рост продаж?','Нет. Я отвечаю за согласованный результат работы: сайт, контент, настройку или сценарий. Продажи зависят также от продукта, аудитории, рекламы и обработки обращений.'),('Что со сроками, правками и поддержкой?','Сроки, количество согласований и условия поддержки определяются для конкретной задачи до начала работы. Бессрочная поддержка и неограниченные правки в тарифы не входят.')]
for q,a in faqs:body+=f'<details><summary>{e(q)}</summary><p>{e(a)}</p></details>'
body+='</div></section>'+contact(p)
render(p,'Сайты, AI и автоматизация для бизнеса','Трофим Мокров: сайты от 20 000 ₽, автоматизация от 10 000 ₽, настройка устройств, AI-контент и ведение соцсетей. Понятный состав работ и личный подход.',body)
# About
p='about.html'
body=heading('Обо мне','Технологии — под задачу.<br>Работа — с человеком.','Я Трофим Мокров. Помогаю предпринимателям, экспертам и небольшим командам выстраивать цифровую сторону бизнеса.')
body+=f'''<section class="section split"><div class="bio"><p>Занимаюсь созданием сайтов, автоматизацией, настройкой инструментов и контентом с помощью AI.</p><p>Помогаю продумать идею, название и визуальный стиль под конкретный бизнес. Могу подключиться к отдельной задаче: настроить телефон для публикаций, подготовить изображение или собрать сайт. А могу помочь объединить площадки и процессы в понятную систему.</p><p>Мне важно разобраться в вашей работе: что повторяется, что отнимает время и где клиенту сложно сделать следующий шаг. Инструменты подбираю после этого.</p></div><div>{eyebrow('Как проходит сотрудничество')}{steps()}</div></section><section class="dark" data-reveal><h2>Не обязательно<br>делать всё сразу.</h2><p>Начнём с самого полезного изменения. Например, уточним предложение на сайте, упорядочим публикации или уберём ручной перенос заявок. Следующие шаги можно определить после проверки результата.</p></section><section class="section"><div class="section-head"><h2>Что можно поручить мне</h2><p>Отдельные задачи и сочетание нескольких направлений.</p></div><div class="grid"><article class="card"><h3>Представить бизнес</h3><p>Сайт, описания услуг, оформление площадок и актуальные контакты.</p></article><article class="card"><h3>Организовать контент</h3><p>План публикаций, посты, AI-изображения и настройка устройств.</p></article><article class="card"><h3>Упростить процессы</h3><p>Сценарии передачи данных, уведомления и связки инструментов.</p></article></div></section>'''+contact(p)
render(p,'Обо мне','Трофим Мокров: подход к созданию сайтов, автоматизации и контенту. Сначала задача бизнеса, затем инструменты и проверяемый результат.',body)
# Services
p='services.html';body=heading('Услуги и цены','Понятный объём.<br>Понятная стоимость.','Можно начать с одной небольшой задачи или обсудить систему из нескольких инструментов. Ниже — базовый состав каждой услуги.')
for s in services:
 inc=''.join(f'<li>{e(item)}</li>' for item in s['includes'])
 body+=f'''<section class="service-detail" id="{s['id']}" data-reveal><div class="detail-top"><div>{eyebrow(s['number']+' / Услуга')}<h2>{e(s['name'])}</h2><p>{e(s['audience'])}</p></div><div class="price">{e(s['price'])}<small>{e(s['unit'])}</small></div></div><div class="detail-body"><div><h3>Что входит</h3><ul>{inc}</ul><h3>Что получите</h3><p>{e(s['result'])}</p></div><div><h3>Что увеличивает стоимость</h3><p>{e(s['extra'])}</p><h3>Отдельные расходы</h3><p>{e(s['separate'])}</p><a class="button" href="{site['telegram']}" target="_blank" rel="noopener noreferrer">Обсудить задачу ↗</a></div></div></section>'''
body+='<p class="note">Это ориентиры для базового объёма, а не обещание любой сложности по минимальной цене. Сроки, количество правок, критерии приёмки и поддержка согласуются до начала работы. Точные условия фиксируются для конкретного проекта.</p>'+contact(p)
render(p,'Услуги и цены','Состав и стоимость услуг: сайты, автоматизация, настройка устройств, AI-изображения, посты, ведение соцсетей и запуск цифровой инфраструктуры.',body)
# Portfolio
p='portfolio.html';body=heading('Портфолио','Работы с понятным<br>контекстом.','Здесь — проекты с описанием задачи и выполненной работы. В каждом проекте указаны мой вклад и границы подтверждённых результатов.')
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
body+=contact(p);render(p,'Портфолио','Проекты Трофима Мокрова: участие в цифровом оформлении «Древесного замысла» и собственный персональный сайт.',body)
# Articles
p='articles.html';body=heading('Статьи','Сначала разобраться.<br>Потом внедрять.','Практические материалы о сайтах, автоматизации и контенте. Без обещаний волшебных инструментов и гарантированных продаж.')+article_cards(p)+contact(p)
render(p,'Статьи о сайтах, AI и автоматизации','Шесть практических руководств: выбор сайта, первая автоматизация, цифровая инфраструктура, AI-контент, соцсети и стоимость внедрения.',body)
for a in articles:
 p='articles/'+a['slug']+'.html';body=f'<div class="breadcrumbs"><a href="{link(p,"articles.html")}">Статьи</a> / {e(a["category"])}</div>'+heading(a['category'],e(a['title']),a['description'])
 body+='<article class="reading"><nav class="article-toc" aria-label="Содержание статьи"><div><strong>В этой статье</strong><ol>'
 for i,s in enumerate(a['sections'],1):body+=f'<li><a href="#part-{i}">{e(s["heading"])}</a></li>'
 body+='</ol></div></nav>'
 for i,s in enumerate(a['sections'],1):body+=f'<section id="part-{i}"><h2>{e(s["heading"])}</h2><p>{e(s["text"])}</p></section>'
 body+=f'<p class="note">Примеры в статье иллюстрируют подход и не описывают клиентские результаты. Состав внедрения зависит от конкретной задачи и возможностей выбранных сервисов.</p><a class="text-link" href="{link(p,"services.html")}#{e(a["service"])}">Услуга по этой теме ↗</a></article>'+contact(p)
 render(p,a['title'],a['description'],body,active='articles.html',article=True)
# Contact
p='contact.html';body=heading('Контакты','Начнём с простого<br>разговора о задаче.','Удобнее всего написать в Telegram. Если предпочитаете почту или звонок — контакты ниже.')
body+='<section class="section split"><div class="contact-list">'
for label,value,url in [('Telegram','@TrofimMokrov',site['telegram']),('Электронная почта',site['email'],'mailto:'+site['email']),('Телефон',site['phone_display'],'tel:'+site['phone'])]:body+=f'<a class="contact-item" href="{e(url)}"'+(' target="_blank" rel="noopener noreferrer"' if url.startswith('https') else '')+f'><span><small>{label}</small>{e(value)}</span><span aria-hidden="true">↗</span></a>'
body+='''</div><div><h2>Что написать<br>в первом сообщении</h2><ol><li>Чем занимаетесь и кому помогаете.</li><li>Какую задачу хотите решить.</li><li>Что уже есть: сайт, площадки, инструменты.</li><li>Какие ограничения по объёму и бюджету важно учесть.</li></ol><p class="note">Не отправляйте пароли, ключи доступа и личные данные клиентов. При необходимости отдельно согласуем безопасный способ доступа.</p></div></section>'''
render(p,'Контакты','Обсудить сайт, автоматизацию или контент с Трофимом Мокровым: Telegram @TrofimMokrov, trofimmokrov@gmail.com, +7 (915) 998-25-54.',body)
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
print(f'Built {len(outputs)} HTML pages. '+('Canonical and sitemap enabled.' if base else 'Public URL unconfirmed; canonical and sitemap omitted.'))
