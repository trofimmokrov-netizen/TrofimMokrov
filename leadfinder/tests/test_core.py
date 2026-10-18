import io
import json
import os
import smtplib
import socket
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request,urlopen
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from core import Store,Problem,read_csv,public_url,check_website,yandex_search
from server import make_server
from worker import run_batch

class StoreTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.store=Store(Path(self.tmp.name)/'test.sqlite3')
 def tearDown(self):self.tmp.cleanup()
 def lead(self,name='Мастерская «Пример»',email='owner@example.com'):
  self.store.import_rows([{'name':name,'city':'Москва','email':email}]);return self.store.all()[0]['id']
 def approved(self,name='Мастерская «Пример»'):
  identifier=self.lead(name);self.store.update(identifier,{'absence_confirmed':True});self.store.draft(identifier);self.store.approve(identifier);return identifier
 def test_csv_dedup_preserves_editor_changes(self):
  rows=read_csv('\ufeffname;city;email\nМастерская;Москва;owner@example.com\n')
  self.assertEqual(self.store.import_rows(rows)['added'],1)
  self.store.update(self.store.all()[0]['id'],{'subject':'Моя тема'})
  self.assertEqual(self.store.import_rows(rows)['duplicates'],1)
  self.assertEqual(self.store.all()[0]['subject'],'Моя тема')
 def test_absent_listing_not_confirmed_and_no_fake_email(self):
  identifier=self.lead(email='');self.assertEqual(self.store.get(identifier)['website_state'],'not_listed')
  with self.assertRaises(Problem):self.store.draft(identifier)
  self.store.update(identifier,{'absence_confirmed':True});self.store.draft(identifier)
  with self.assertRaises(Problem):self.store.approve(identifier)
  self.assertEqual(self.store.get(identifier)['email'],'')
 def test_edit_revokes_approval(self):
  identifier=self.approved();self.store.update(identifier,{'body':'Исправленный текст'})
  self.assertEqual(self.store.get(identifier)['state'],'draft')
  with self.assertRaises(Problem):self.store.send(identifier,lambda _:None)
 def test_one_send_per_email_and_accepted_not_delivered(self):
  identifier=self.approved();calls=[]
  result=self.store.send(identifier,lambda lead:calls.append(lead['email']))
  self.assertEqual(result['state'],'sent');self.assertIn('не подтверждены',result['send_note'])
  with self.assertRaises(Problem):self.store.send(identifier,lambda _:None)
  other=self.lead('Другая запись');self.store.update(other,{'absence_confirmed':True});self.store.draft(other)
  with self.assertRaises(Problem):self.store.approve(other)
  self.assertEqual(calls,['owner@example.com'])
 def test_timeout_does_not_retry(self):
  identifier=self.approved()
  def fail(_):raise TimeoutError()
  self.assertEqual(self.store.send(identifier,fail)['state'],'unknown')
  with self.assertRaises(Problem):self.store.send(identifier,lambda _:None)
 def test_smtp_rejection_is_distinct(self):
  identifier=self.approved()
  def fail(_):raise smtplib.SMTPAuthenticationError(535,b'rejected')
  self.assertEqual(self.store.send(identifier,fail)['state'],'failed')
 def test_blocked_address_covers_other_imports(self):
  identifier=self.approved();self.store.block(identifier)
  with self.assertRaises(Problem):self.store.send(identifier,lambda _:None)
  other=self.lead('Иное название');self.assertEqual(self.store.get(other)['state'],'blocked')
 def test_header_injection_rejected(self):
  identifier=self.lead()
  for values in ({'email':'x@example.com\nBcc: a@example.com'},{'subject':'Тема\nBcc: a@example.com'}):
   with self.assertRaises(Problem):self.store.update(identifier,values)
 def test_missing_smtp_does_not_consume_approval(self):
  identifier=self.approved()
  with patch.dict(os.environ,{},clear=True):
   with self.assertRaises(Problem):self.store.send(identifier)
  self.assertEqual(self.store.get(identifier)['state'],'approved')
 def test_worker_dry_run_never_sends(self):
  self.approved();calls=[]
  result=run_batch(self.store,deliver=lambda lead:calls.append(lead))
  self.assertTrue(result['dry_run']);self.assertEqual(calls,[])
 def test_worker_sends_only_approved_and_spaces_requests(self):
  self.approved();other=self.lead('Другая компания','second@example.com');self.store.update(other,{'absence_confirmed':True});self.store.draft(other);self.store.approve(other)
  self.lead('Не одобрена','third@example.com');calls=[];pauses=[]
  result=run_batch(self.store,send=True,deliver=lambda lead:calls.append(lead['email']),pause=pauses.append)
  self.assertEqual(result['sent'],2);self.assertEqual(len(calls),2);self.assertEqual(pauses,[30])
 def test_worker_stops_on_unknown_outcome(self):
  self.approved()
  def fail(_):raise TimeoutError()
  result=run_batch(self.store,send=True,deliver=fail,pause=lambda _:None)
  self.assertEqual(result['unknown'],1);self.assertEqual(result['sent'],0)
 def test_private_urls_rejected(self):
  with self.assertRaises(Problem):public_url('http://localhost/')
  with self.assertRaises(Problem):public_url('https://user:password@example.com/')
  with patch('core.socket.getaddrinfo',return_value=[(2,1,6,'',('127.0.0.1',80))]):
   with self.assertRaises(Problem):public_url('http://example.com')
 def test_provider_maps_missing_website_without_invented_email(self):
  data={'features':[{'properties':{'CompanyMetaData':{'id':'123','name':'Мастерская','address':'Москва','Categories':[{'name':'Мебель'}]}}}]}
  response=io.BytesIO(json.dumps(data).encode())
  with patch.dict(os.environ,{'YANDEX_SEARCH_API_KEY':'test-not-a-real-key'}),patch('core.build_opener') as opener:
   opener.return_value.open.return_value.__enter__.return_value=response
   rows=yandex_search('мебель','Москва')
  self.assertEqual(rows[0]['website'],'');self.assertEqual(rows[0]['email'],'');self.assertEqual(rows[0]['source_id'],'yandex:123')
  self.assertEqual(rows[0]['source_url'],'https://yandex.ru/maps/org/123/')
 def test_site_errors_are_not_absence(self):
  with patch('core.public_url',return_value='https://example.com'),patch('core.build_opener') as opener:
   opener.return_value.open.side_effect=HTTPError('https://example.com',403,'denied',{},None)
   result=check_website('https://example.com')
  self.assertEqual(result['website_state'],'uncertain')

class ServerTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.server=make_server(Store(Path(self.tmp.name)/'test.sqlite3'),0)
  self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start();self.url=f'http://127.0.0.1:{self.server.server_port}'
 def tearDown(self):self.server.shutdown();self.server.server_close();self.thread.join();self.tmp.cleanup()
 def test_http_workflow_and_no_public_storage(self):
  with urlopen(self.url+'/api/session') as r:session=json.load(r)
  req=Request(self.url+'/api/import',data=json.dumps({'csv':'name,city\nТест,Москва'}).encode(),headers={'Content-Type':'application/json','X-Leadfinder-Token':session['token']})
  with urlopen(req) as r:self.assertEqual(json.load(r)['result']['added'],1)
  with urlopen(self.url+'/api/leads') as r:self.assertEqual(len(json.load(r)['leads']),1)
  with self.assertRaises(HTTPError) as error:urlopen(self.url+'/data/leads.sqlite3')
  self.assertEqual(error.exception.code,404)
 def test_cross_origin_and_token_rejected(self):
  req=Request(self.url+'/api/leads',data=b'{"name":"Test"}',headers={'Content-Type':'application/json','Origin':'https://evil.example'})
  with self.assertRaises(HTTPError) as error:urlopen(req)
  self.assertEqual(error.exception.code,403)
  req=Request(self.url+'/api/leads',data=b'{"name":"Test"}',headers={'Content-Type':'application/json'})
  with self.assertRaises(HTTPError) as error:urlopen(req)
  self.assertEqual(error.exception.code,403)

if __name__=='__main__':unittest.main()
