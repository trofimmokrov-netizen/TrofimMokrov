"""Bounded public-source discovery and contact-page parsing; never sends mail."""
import json
import re
import time
from html.parser import HTMLParser
from urllib.error import HTTPError,URLError
from urllib.parse import urlencode,urlsplit,urljoin,urldefrag,unquote
from urllib.request import Request,build_opener
from urllib.robotparser import RobotFileParser
from core import Problem,CheckedRedirect,public_url,email_valid,clean,now
AGENT='TrofimLeadfinder'
UA=AGENT+'/1.0 (public business contact research)'
EMAIL_TEXT=re.compile(r'[A-Za-z0-9.!#$%&\'*+/=?^_`{|}~-]+@[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?\.[A-Za-z]{2,63}')
CONTACT_TERMS=('contact','kontakt','контакт','requisit','rekvizit')
class SameHostRedirect(CheckedRedirect):
 def redirect_request(self,req,fp,code,msg,headers,newurl):
  old=urlsplit(req.full_url);new=urlsplit(newurl)
  if new.hostname!=old.hostname or old.scheme=='https' and new.scheme!='https':raise Problem('Сайт перенаправляет на другой домен или HTTP. Проверьте его вручную.')
  return super().redirect_request(req,fp,code,msg,headers,newurl)

def fetch_page(url):
 url=public_url(url)
 with build_opener(SameHostRedirect()).open(Request(url,headers={'User-Agent':UA,'Accept':'text/html,text/plain'}),timeout=10) as response:
  raw=response.read(300001)
  if len(raw)>300000:raise Problem('Страница слишком большая для ограниченного разбора.')
  kind=response.headers.get_content_type()
  if kind not in ('text/html','text/plain','application/xhtml+xml'):raise Problem('По этому адресу нет HTML-страницы.')
  encoding=response.headers.get_content_charset() or 'utf-8'
  try:text=raw.decode(encoding,errors='replace')
  except LookupError:text=raw.decode('utf-8',errors='replace')
  return text

class Contacts(HTMLParser):
 def __init__(self,url):super().__init__(convert_charrefs=True);self.url=url;self.links=[];self.emails=[];self.skip=0;self.anchor=None
 def candidate(self,value,kind):
  value=unquote(value).strip().lower()
  if not email_valid(value) or value.split('@')[0] in ('noreply','no-reply','donotreply'):return
  if value.endswith(('.png','.jpg','.jpeg','.webp','.svg','.gif')):return
  item={'email':value,'url':self.url,'kind':kind}
  if item not in self.emails:self.emails.append(item)
 def handle_starttag(self,tag,attrs):
  a=dict(attrs)
  if tag in ('script','style','noscript'):self.skip+=1
  if self.skip:return
  if tag=='a':
   href=a.get('href','');self.anchor={'href':href,'text':''}
   if href.lower().startswith('mailto:'):
    for address in href[7:].split('?')[0].split(','):self.candidate(address,'mailto')
 def handle_endtag(self,tag):
  if tag in ('script','style','noscript'):self.skip=max(0,self.skip-1)
  if tag=='a' and self.anchor:
   href=self.anchor['href'];joined=urldefrag(urljoin(self.url,href))[0]
   u=urlsplit(joined)
   if u.scheme in ('http','https') and u.hostname==urlsplit(self.url).hostname and any(t in (href+' '+self.anchor['text']).lower() for t in CONTACT_TERMS):
    if joined not in self.links:self.links.append(joined)
   self.anchor=None
 def handle_data(self,text):
  if self.skip:return
  if self.anchor:self.anchor['text']+=' '+text
  for candidate in EMAIL_TEXT.findall(text):self.candidate(candidate,'visible_text')

def research_site(url,fetch=fetch_page,pause=time.sleep):
 root=public_url(url);parts=urlsplit(root);origin=parts.scheme+'://'+parts.netloc
 robot=RobotFileParser();robot.set_url(origin+'/robots.txt')
 try:robot.parse(fetch(origin+'/robots.txt').splitlines())
 except HTTPError as error:
  if error.code==404:robot.parse([])
  else:return {'status':'blocked','note':f'robots.txt недоступен (HTTP {error.code}); разбор остановлен.','emails':[],'pages':[],'at':now()}
 except (Problem,URLError,OSError):return {'status':'uncertain','note':'Не удалось проверить robots.txt; разбор остановлен.','emails':[],'pages':[],'at':now()}
 delay=max(1,robot.crawl_delay(AGENT) or 0)
 if delay>10:return {'status':'blocked','note':'robots.txt требует большой интервал. Используйте ручную проверку.','emails':[],'pages':[],'at':now()}
 queue=[root];pages=[];emails=[];notes=[];visited=set()
 while queue and len(visited)<3:
  current=queue.pop(0)
  if current in visited:continue
  visited.add(current)
  if not robot.can_fetch(AGENT,current):notes.append('robots.txt запрещает страницу.');continue
  pause(delay)
  try:
   html=fetch(current);parser=Contacts(current);parser.feed(html);pages.append(current)
   for item in parser.emails:
    if item not in emails:emails.append(item)
   queue.extend(link for link in parser.links if link not in visited and link not in queue)
  except (Problem,HTTPError,URLError,OSError):notes.append('Страница не прочитана: доступ, формат или сеть.')
 return {'status':'checked' if pages else 'uncertain','note':('Найдены публичные контакты; проверьте, подходят ли они для делового обращения.' if emails else 'Email не найден в просмотренных страницах.')+(' '+' '.join(dict.fromkeys(notes)) if notes else ''),'emails':emails[:30],'pages':pages,'at':now()}

def osm_search(query,city,limit=10,bbox='55.49,37.32,55.96,37.95'):
 try:
  bounds=[float(v.strip()) for v in bbox.split(',')]
  if len(bounds)!=4:raise ValueError()
  south,west,north,east=bounds
  if not (-90<=south<north<=90 and -180<=west<east<=180) or north-south>1 or east-west>2:raise ValueError()
 except (ValueError,TypeError):raise Problem('Укажите небольшой прямоугольник: юг,запад,север,восток. Не больше 1° × 2° за поиск.')
 term=clean(query,150).lower()
 if not term:raise Problem('Укажите сферу или название.')
 if any(x in term for x in ('мебел','мастерск','столяр')):selectors=['["shop"="furniture"]','["craft"="carpenter"]']
 elif any(x in term for x in ('красот','парикмах','салон')):selectors=['["shop"="beauty"]','["shop"="hairdresser"]']
 elif any(x in term for x in ('автосервис','авторемонт')):selectors=['["shop"="car_repair"]']
 elif 'стомат' in term:selectors=['["amenity"="dentist"]']
 else:selectors=['["name"~'+json.dumps(re.escape(term),ensure_ascii=False)+',i]']
 count=max(1,min(int(limit),50));area=','.join(str(v) for v in bounds)
 q='[out:json][timeout:20];('+''.join('nwr'+selector+'('+area+');' for selector in selectors)+');out center '+str(count)+';'
 request=Request('https://overpass-api.de/api/interpreter',data=urlencode({'data':q}).encode(),headers={'User-Agent':UA,'Accept':'application/json'})
 try:
  with build_opener().open(request,timeout=25) as response:data=json.loads(response.read(3000000))
 except (HTTPError,URLError,OSError,ValueError):raise Problem('Открытый поиск недоступен. Нужен HTTPS-доступ к overpass-api.de; провайдер также может ограничивать нагрузку.')
 if not isinstance(data,dict) or 'remark' in data or not isinstance(data.get('elements'),list):raise Problem('Источник вернул неполный или неожиданный ответ. Попробуйте меньшую область.')
 rows=[]
 for element in data['elements'][:count]:
  tags=element.get('tags',{});name=tags.get('name')
  if not name:continue
  email=clean(tags.get('contact:email') or tags.get('email'),250).lower()
  if not email_valid(email):email=''
  address=', '.join(str(tags.get(key,'')) for key in ('addr:city','addr:street','addr:housenumber') if tags.get(key))
  kind=element.get('type');identifier=element.get('id')
  if kind not in ('node','way','relation') or not isinstance(identifier,int):continue
  rows.append({'name':name,'address':address,'city':tags.get('addr:city') or clean(city,100),'category':tags.get('shop') or tags.get('craft') or tags.get('amenity',''),'website':tags.get('contact:website') or tags.get('website',''),'email':email,'source_id':f'osm:{kind}:{identifier}','source_url':f'https://www.openstreetmap.org/{kind}/{identifier}','source':'© OpenStreetMap contributors · ODbL'})
 return rows
