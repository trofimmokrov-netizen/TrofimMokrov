#!/usr/bin/env python3
"""Private loopback-only control panel; do not publish on GitHub Pages."""
import argparse
import hmac
import json
import os
import secrets
import sys
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit
from core import Store,Problem,read_csv,yandex_search
ROOT=Path(__file__).resolve().parent

def make_server(store,port=8090):
 token=secrets.token_urlsafe(32)
 class Handler(BaseHTTPRequestHandler):
  def log_message(self,*args):pass
  def reply(self,code,data):
   body=json.dumps(data,ensure_ascii=False).encode();self.send_response(code);self.send_header('Content-Type','application/json; charset=utf-8');self.headers_out();self.end_headers();self.wfile.write(body)
  def headers_out(self):
   self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.send_header('Referrer-Policy','no-referrer');self.send_header('X-Frame-Options','DENY');self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; form-action 'none'; base-uri 'none'")
  def allowed(self):
   hosts={f'127.0.0.1:{self.server.server_port}',f'localhost:{self.server.server_port}'}
   if self.headers.get('Host') not in hosts:return False
   origin=self.headers.get('Origin')
   return (not origin or origin in {'http://'+host for host in hosts}) and self.headers.get('Sec-Fetch-Site','none') in ('none','same-origin')
  def do_GET(self):
   if not self.allowed():return self.reply(403,{'error':'Откройте панель на локальном адресе сервера.'})
   path=urlsplit(self.path).path
   if path=='/api/session':return self.reply(200,{'token':token,'yandex_configured':bool(os.environ.get('YANDEX_SEARCH_API_KEY')),'smtp_configured':all(os.environ.get(k) for k in ('SMTP_HOST','SMTP_USER','SMTP_PASSWORD','SMTP_FROM'))})
   if path=='/api/leads':return self.reply(200,{'leads':store.all()})
   files={'/':('index.html','text/html; charset=utf-8'),'/app.js':('app.js','text/javascript; charset=utf-8'),'/style.css':('style.css','text/css; charset=utf-8')}
   if path not in files:return self.reply(404,{'error':'Не найдено'})
   name,kind=files[path];data=(ROOT/'static'/name).read_bytes();self.send_response(200);self.send_header('Content-Type',kind);self.headers_out();self.end_headers();self.wfile.write(data)
  def do_POST(self):
   if not self.allowed() or not hmac.compare_digest(self.headers.get('X-Leadfinder-Token',''),token):return self.reply(403,{'error':'Обновите страницу локальной панели.'})
   if self.headers.get('Content-Type','').split(';')[0]!='application/json':return self.reply(400,{'error':'Ожидается JSON.'})
   try:
    length=int(self.headers.get('Content-Length','0'))
    if length<1 or length>1100000:raise Problem('Размер запроса недопустим.')
    data=json.loads(self.rfile.read(length))
    if not isinstance(data,dict):raise Problem('Ожидается объект.')
    path=urlsplit(self.path).path
    if path=='/api/import':result=store.import_rows(read_csv(data.get('csv','')))
    elif path=='/api/search':
     query=str(data.get('query','')).strip();city=str(data.get('city','')).strip()
     if not query or not city:raise Problem('Укажите сферу и город / регион.')
     result=store.import_rows(yandex_search(query,city,data.get('limit',10)))
    elif path=='/api/leads':result=store.import_rows([data])
    else:
     parts=path.strip('/').split('/')
     if len(parts)!=4 or parts[:2]!=['api','leads'] or not parts[2].isdigit():return self.reply(404,{'error':'Не найдено'})
     identifier=int(parts[2]);action=parts[3]
     if action=='update':result=store.update(identifier,data)
     elif action=='check':result=store.check(identifier)
     elif action=='draft':result=store.draft(identifier)
     elif action=='approve':result=store.approve(identifier)
     elif action=='send':result=store.send(identifier)
     elif action=='block':result=store.block(identifier)
     else:return self.reply(404,{'error':'Не найдено'})
    self.reply(200,{'result':result})
   except (Problem,ValueError,TypeError,OverflowError):
    error=sys.exc_info()[1];self.reply(400,{'error':str(error) if isinstance(error,Problem) else 'Проверьте формат данных.'})
   except Exception:self.reply(500,{'error':'Внутренняя ошибка. Проверьте состояние записи перед повторным действием.'})
 return ThreadingHTTPServer(('127.0.0.1',port),Handler)

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--port',type=int,default=8090);parser.add_argument('--db',default=os.environ.get('LEADFINDER_DB_PATH',str(ROOT/'data/leads.sqlite3')));args=parser.parse_args()
 server=make_server(Store(args.db),args.port)
 print(f'Leadfinder: http://127.0.0.1:{server.server_port} (private local control panel)',flush=True)
 try:server.serve_forever()
 except KeyboardInterrupt:pass
 finally:server.server_close()
if __name__=='__main__':main()
