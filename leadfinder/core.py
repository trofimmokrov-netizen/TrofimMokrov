"""Local lead research and reviewed email outreach. Standard library only."""
import csv
import hashlib
import io
import ipaddress
import json
import os
import re
import smtplib
import socket
import sqlite3
import ssl
import threading
from datetime import datetime, timezone
from contextlib import contextmanager
from email.message import EmailMessage
from email.utils import formatdate,make_msgid
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit, urljoin
from urllib.request import Request, build_opener, HTTPRedirectHandler

EMAIL=re.compile(r'^[A-Za-z0-9.!#$%&\'*+/=?^_`{|}~-]+@[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?\.[A-Za-z]{2,63}$')
STATES={'new','draft','approved','sending','sent','failed','unknown','blocked'}
LOCK=threading.RLock()
def serialized(method):
 def wrapped(*args,**kwargs):
  with LOCK:return method(*args,**kwargs)
 return wrapped
def now():return datetime.now(timezone.utc).isoformat(timespec='seconds')
def clean(value,limit=2000):return str(value or '').strip()[:limit]
def email_valid(value):return bool(EMAIL.fullmatch(value)) and '\n' not in value and '\r' not in value
class Problem(ValueError):pass

def public_url(value):
 value=clean(value)
 if '://' not in value:value='https://'+value
 u=urlsplit(value)
 if u.scheme not in ('https','http') or not u.hostname or u.username or u.password or u.port not in (None,80,443):raise Problem('Нужен публичный HTTP(S)-адрес без логина и нестандартного порта.')
 host=u.hostname.lower().rstrip('.')
 if host=='localhost' or host.endswith(('.localhost','.local','.internal')):raise Problem('Локальные адреса не проверяются.')
 try:addresses=socket.getaddrinfo(host,u.port or (443 if u.scheme=='https' else 80),type=socket.SOCK_STREAM)
 except OSError:raise Problem('Не удалось определить адрес сайта.')
 if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):raise Problem('Доступ к локальным и служебным адресам закрыт.')
 return value
class CheckedRedirect(HTTPRedirectHandler):
 def redirect_request(self,req,fp,code,msg,headers,newurl):
  public_url(newurl)
  return super().redirect_request(req,fp,code,msg,headers,newurl)
class Title(HTMLParser):
 def __init__(self):super().__init__();self.inside=False;self.text=''
 def handle_starttag(self,t,a):
  if t=='title':self.inside=True
 def handle_endtag(self,t):
  if t=='title':self.inside=False
 def handle_data(self,d):
  if self.inside:self.text+=d

def check_website(value):
 url=public_url(value)
 try:
  req=Request(url,headers={'User-Agent':'TrofimLeadfinder/1.0 (manual website verification)','Accept':'text/html'})
  with build_opener(CheckedRedirect()).open(req,timeout=12) as response:
   raw=response.read(300000);charset=response.headers.get_content_charset() or 'utf-8'
   try:html=raw.decode(charset,errors='replace')
   except LookupError:html=raw.decode('utf-8',errors='replace')
   title=Title();title.feed(html)
   return {'website_state':'reachable','check_note':'HTTP '+str(response.status)+(' · '+clean(title.text,180) if title.text else ''),'checked_at':now()}
 except HTTPError as error:
  return {'website_state':'uncertain','check_note':f'HTTP {error.code}. Ошибка или ограничение доступа не доказывают отсутствие сайта.','checked_at':now()}
 except (URLError,TimeoutError,OSError):
  return {'website_state':'uncertain','check_note':'Проверка не завершена: сеть, TLS или таймаут. Проверьте адрес вручную.','checked_at':now()}

def yandex_search(query,city,limit=10):
 key=os.environ.get('YANDEX_SEARCH_API_KEY','')
 if not key:raise Problem('Не задан YANDEX_SEARCH_API_KEY. Пока можно импортировать CSV.')
 params={'apikey':key,'text':clean(city,100)+' '+clean(query,150),'lang':'ru_RU','type':'biz','results':max(1,min(int(limit),50))}
 # No provider credentials or request URLs are written to logs or returned to the UI.
 req=Request('https://search-maps.yandex.ru/v1/?'+urlencode(params),headers={'Accept':'application/json'})
 try:
  with build_opener().open(req,timeout=20) as response:data=json.loads(response.read(3000000))
 except (HTTPError,URLError,TimeoutError,ValueError,OSError):raise Problem('Поиск Яндекса недоступен. Проверьте ключ, тариф, доступ к search-maps.yandex.ru и условия API.')
 if not isinstance(data,dict) or not isinstance(data.get('features'),list):raise Problem('Неожиданный ответ поиска Яндекса.')
 rows=[]
 for feature in data['features']:
  props=feature.get('properties',{});meta=props.get('CompanyMetaData',{})
  identifier=clean(meta.get('id'),100)
  rows.append({'name':meta.get('name') or props.get('name',''),'address':meta.get('address',''),'city':city,'category':', '.join(x.get('name','') for x in meta.get('Categories',[])),'website':meta.get('url',''),'email':'','source_id':('yandex:'+identifier) if identifier else '', 'source_url':('https://yandex.ru/maps/org/'+identifier+'/') if identifier.isdigit() else 'https://yandex.ru/maps/','source':'Яндекс · Поиск по организациям'})
 return rows

def read_csv(text):
 if len(text)>1000000:raise Problem('CSV должен быть меньше 1 МБ.')
 text=text.lstrip('\ufeff')
 try:delimiter=csv.Sniffer().sniff(text[:4000],delimiters=',;\t').delimiter
 except csv.Error:delimiter=','
 reader=csv.DictReader(io.StringIO(text),delimiter=delimiter)
 if not reader.fieldnames or 'name' not in reader.fieldnames:raise Problem('CSV должен содержать колонку name. Остальные: address, city, category, website, email, source_url.')
 rows=[]
 try:
  for row in reader:
   if len(rows)>=500:raise Problem('За один импорт — не больше 500 строк.')
   if not clean(row.get('name')):continue
   rows.append(row)
 except csv.Error:raise Problem('Не удалось прочитать CSV. Проверьте разделители и кавычки.')
 return rows

class Store:
 def __init__(self,path):
  self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True)
  with self.connect() as db:
   db.executescript('''
   CREATE TABLE IF NOT EXISTS leads(
   id INTEGER PRIMARY KEY, identity TEXT UNIQUE NOT NULL, name TEXT NOT NULL,
   address TEXT NOT NULL DEFAULT '', city TEXT NOT NULL DEFAULT '', category TEXT NOT NULL DEFAULT '',
   website TEXT NOT NULL DEFAULT '', email TEXT NOT NULL DEFAULT '', source_url TEXT NOT NULL DEFAULT '', source TEXT NOT NULL DEFAULT '',
   website_state TEXT NOT NULL DEFAULT 'not_listed', check_note TEXT NOT NULL DEFAULT '', checked_at TEXT,
   absence_confirmed INTEGER NOT NULL DEFAULT 0, state TEXT NOT NULL DEFAULT 'new', subject TEXT NOT NULL DEFAULT '', body TEXT NOT NULL DEFAULT '',
   created_at TEXT NOT NULL, updated_at TEXT NOT NULL, approved_at TEXT, sent_at TEXT, send_note TEXT NOT NULL DEFAULT '');
   CREATE TABLE IF NOT EXISTS suppression(email TEXT PRIMARY KEY, created_at TEXT NOT NULL);
   CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY, lead_id INTEGER, kind TEXT NOT NULL, note TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL);
   ''')
   if 'research_json' not in {r['name'] for r in db.execute('PRAGMA table_info(leads)')}:db.execute("ALTER TABLE leads ADD COLUMN research_json TEXT NOT NULL DEFAULT '{}'")
 @contextmanager
 def connect(self):
  db=sqlite3.connect(self.path,timeout=15);db.row_factory=sqlite3.Row
  try:
   with db:yield db
  finally:db.close()
 def all(self):
  with self.connect() as db:return [dict(r) for r in db.execute('SELECT * FROM leads ORDER BY id DESC')]
 def get(self,identifier):
  with self.connect() as db:row=db.execute('SELECT * FROM leads WHERE id=?',(identifier,)).fetchone()
  if row is None:raise Problem('Компания не найдена.')
  return dict(row)
 def import_rows(self,rows):
  added=0;duplicates=0;skipped=0
  with self.connect() as db:
   for row in rows:
    name=clean(row.get('name'),250)
    if not name:skipped+=1;continue
    address=clean(row.get('address'),600);city=clean(row.get('city'),100)
    identity=clean(row.get('source_id'),200) or hashlib.sha256((name.casefold()+'|'+address.casefold()+'|'+city.casefold()).encode()).hexdigest()
    website=clean(row.get('website'),1000);email=clean(row.get('email'),250).lower()
    if email and not email_valid(email):email=''
    state='blocked' if email and db.execute('SELECT 1 FROM suppression WHERE email=?',(email,)).fetchone() else 'new'
    cursor=db.execute('INSERT OR IGNORE INTO leads(identity,name,address,city,category,website,email,source_url,source,website_state,state,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',(identity,name,address,city,clean(row.get('category'),300),website,email,clean(row.get('source_url'),1000),clean(row.get('source') or 'CSV / вручную',100),'unchecked' if website else 'not_listed',state,now(),now()))
    if cursor.rowcount:added+=1
    else:duplicates+=1
  return {'added':added,'duplicates':duplicates,'skipped':skipped}
 @serialized
 def update(self,identifier,values):
  allowed={'email','website','absence_confirmed','subject','body','website_state','check_note','checked_at'}
  if not values or not set(values)<=allowed:raise Problem('Недопустимое изменение.')
  lead=self.get(identifier)
  if lead['state'] in ('sending','sent','unknown','blocked'):raise Problem('Эту запись нельзя менять: письмо отправлено, заблокировано или статус отправки требует проверки.')
  if 'email' in values:
   values['email']=clean(values['email'],250).lower()
   if values['email'] and not email_valid(values['email']):raise Problem('Проверьте email: нужен один корректный адрес.')
  if 'website' in values:
   values['website']=clean(values['website'],1000)
   if values['website']!=lead['website']:values.update(website_state='unchecked' if values['website'] else 'not_listed',checked_at=None,check_note='',absence_confirmed=0)
  if 'absence_confirmed' in values:values['absence_confirmed']=int(bool(values['absence_confirmed']))
  for key in ('subject','body'):
   if key in values:values[key]=clean(values[key],200 if key=='subject' else 10000)
  if '\n' in values.get('subject','') or '\r' in values.get('subject',''):raise Problem('Тема письма должна быть одной строкой.')
  with self.connect() as db:
   if db.execute('SELECT 1 FROM suppression WHERE email=?',(values.get('email',lead['email']),)).fetchone():raise Problem('Адрес находится в списке «Не писать».')
   values.update(state='draft',approved_at=None,updated_at=now())
   cursor=db.execute('UPDATE leads SET '+','.join(k+'=?' for k in values)+" WHERE id=? AND state NOT IN ('sending','sent','unknown','blocked')",(*values.values(),identifier))
   if not cursor.rowcount:raise Problem('Состояние записи изменилось. Обновите карточку.')
  return self.get(identifier)
 def draft(self,identifier):
  lead=self.get(identifier)
  if not lead['absence_confirmed']:raise Problem('Сначала вручную подтвердите отсутствие сайта. Пустое поле в карточке этого не доказывает.')
  name=lead['name'];subject='Сайт для '+name
  body=f'''Здравствуйте!\n\nМеня зовут Трофим Мокров. Посмотрел информацию о «{name}»{(' в '+lead['city']) if lead['city'] else ''} и хотел предложить обсудить сайт для вашей компании.\n\nСоздаю сайты с помощью AI: базовый сайт-визитка — от 10 000 ₽. На нём можно понятно представить услуги, разместить контакты и помочь посетителю обратиться к вам. Сначала показываю предварительный вариант для обсуждения; дальнейший объём и условия согласуем отдельно.\n\nЕсли это актуально, могу предложить структуру под вашу задачу. Если предложение не подходит, сообщите — больше писать не буду.\n\nТрофим Мокров\nhttps://t.me/TrofimMokrov\ntrofimmokrov@gmail.com\n+7 (915) 998-25-54'''
  return self.update(identifier,{'subject':subject,'body':body})
 @serialized
 def approve(self,identifier):
  lead=self.get(identifier)
  if lead['state'] not in ('draft','failed'):raise Problem('Сначала подготовьте и проверьте черновик.')
  if not email_valid(lead['email']) or not lead['absence_confirmed'] or not lead['subject'] or not lead['body']:raise Problem('Нужны проверенный email, подтверждение отсутствия сайта и полный текст письма.')
  with self.connect() as db:
   if db.execute('SELECT 1 FROM suppression WHERE email=?',(lead['email'],)).fetchone():raise Problem('Адрес находится в списке «Не писать».')
   if db.execute("SELECT 1 FROM leads WHERE email=? AND state IN ('sending','sent','unknown')",(lead['email'],)).fetchone():raise Problem('На этот адрес уже отправляли письмо либо статус требует проверки.')
   cursor=db.execute("UPDATE leads SET state='approved',approved_at=?,updated_at=? WHERE id=? AND state IN ('draft','failed')",(now(),now(),identifier))
   if not cursor.rowcount:raise Problem('Состояние записи изменилось. Обновите карточку.')
  return self.get(identifier)
 def block(self,identifier):
  lead=self.get(identifier)
  if not email_valid(lead['email']):raise Problem('Сначала укажите email для списка «Не писать».')
  with LOCK,self.connect() as db:
   db.execute('INSERT OR IGNORE INTO suppression VALUES(?,?)',(lead['email'],now()))
   db.execute("UPDATE leads SET state='blocked',updated_at=? WHERE email=? AND state NOT IN ('sent','unknown')",(now(),lead['email']))
   db.execute('INSERT INTO events(lead_id,kind,created_at) VALUES(?,?,?)',(identifier,'blocked',now()))
  return self.get(identifier)
 def check(self,identifier):
  lead=self.get(identifier)
  if not lead['website']:raise Problem('Сайт не указан. Проверьте компанию вручную; не делайте вывод только по карточке.')
  return self.update(identifier,check_website(lead['website']))
 def research(self,identifier):
  from research import research_site
  lead=self.get(identifier)
  if lead['state'] in ('sending','sent','unknown','blocked'):raise Problem('Разбор недоступен для этой записи.')
  if not lead['website']:raise Problem('Адрес сайта не указан. Возьмите контакты из открытого источника или добавьте известный адрес; отсутствие сайта не подтверждается автоматически.')
  result=research_site(lead['website'])
  with LOCK,self.connect() as db:
   cursor=db.execute("UPDATE leads SET research_json=?,state='draft',approved_at=NULL,updated_at=? WHERE id=? AND state NOT IN ('sending','sent','unknown','blocked')",(json.dumps(result,ensure_ascii=False),now(),identifier))
   if not cursor.rowcount:raise Problem('Запись изменилась во время разбора. Обновите страницу.')
  return self.get(identifier)
 def send(self,identifier,deliver=None):
  config=smtp_config() if deliver is None else None
  with LOCK:
   with self.connect() as db:
    db.execute('BEGIN IMMEDIATE')
    lead=dict(db.execute('SELECT * FROM leads WHERE id=?',(identifier,)).fetchone() or {})
    if not lead or lead['state']!='approved':raise Problem('Отправлять можно только одобренное письмо.')
    if db.execute('SELECT 1 FROM suppression WHERE email=?',(lead['email'],)).fetchone():raise Problem('Адрес находится в списке «Не писать».')
    if db.execute("SELECT 1 FROM leads WHERE email=? AND id!=? AND state IN ('sending','sent','unknown')",(lead['email'],identifier)).fetchone():raise Problem('Повторная отправка на этот адрес остановлена.')
    db.execute("UPDATE leads SET state='sending',updated_at=? WHERE id=?",(now(),identifier))
   try:
    (deliver or (lambda row: smtp_deliver(row,config)))(lead)
    state='sent';note='Почтовый сервер принял письмо. Доставка и прочтение не подтверждены.'
   except (smtplib.SMTPAuthenticationError,smtplib.SMTPRecipientsRefused,smtplib.SMTPSenderRefused):
    state='failed';note='Почтовый сервер отказал в отправке. Проверьте отправителя и подключение.'
   except Exception:
    state='unknown';note='Результат отправки неизвестен. Проверьте почтовый ящик и журналы провайдера перед повторной отправкой.'
   with self.connect() as db:
    db.execute('UPDATE leads SET state=?,sent_at=?,send_note=?,updated_at=? WHERE id=?',(state,now() if state=='sent' else None,note,now(),identifier))
    db.execute('INSERT INTO events(lead_id,kind,note,created_at) VALUES(?,?,?,?)',(identifier,state,note,now()))
  return self.get(identifier)

def smtp_config():
 names=('SMTP_HOST','SMTP_USER','SMTP_PASSWORD','SMTP_FROM')
 if any(not os.environ.get(k) for k in names):raise Problem('Нужны SMTP_HOST, SMTP_USER, SMTP_PASSWORD и SMTP_FROM в окружении сервера.')
 sender=os.environ['SMTP_FROM']
 if not email_valid(sender):raise Problem('SMTP_FROM должен содержать один корректный email.')
 try:port=int(os.environ.get('SMTP_PORT','465'))
 except ValueError:raise Problem('SMTP_PORT должен быть 465 или 587.')
 if port not in (465,587):raise Problem('Поддерживаются SMTP SSL (465) и STARTTLS (587).')
 return {k:os.environ[k] for k in names}|{'port':port}
def smtp_deliver(lead,config):
 message=EmailMessage();message['Date']=formatdate(localtime=False);message['Message-ID']=make_msgid(domain=config['SMTP_FROM'].split('@')[1]);message['From']=config['SMTP_FROM'];message['To']=lead['email'];message['Subject']=lead['subject'];message['Reply-To']=config['SMTP_FROM'];message['List-Unsubscribe']='<mailto:'+config['SMTP_FROM']+'?subject=Unsubscribe>';message.set_content(lead['body'])
 context=ssl.create_default_context()
 if config['port']==465:client=smtplib.SMTP_SSL(config['SMTP_HOST'],465,timeout=20,context=context)
 else:
  client=smtplib.SMTP(config['SMTP_HOST'],587,timeout=20);client.ehlo();client.starttls(context=context);client.ehlo()
 with client:
  client.login(config['SMTP_USER'],config['SMTP_PASSWORD']);refused=client.send_message(message)
  if refused:raise smtplib.SMTPRecipientsRefused(refused)
