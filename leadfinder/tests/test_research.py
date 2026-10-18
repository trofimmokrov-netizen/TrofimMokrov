import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from research import Contacts,research_site,osm_search
from core import Store,Problem

class ResearchTests(unittest.TestCase):
 def test_extracts_public_contacts_not_scripts_or_external_links(self):
  parser=Contacts('https://workshop.ru/')
  parser.feed('<script>const hidden="hidden@workshop.ru";</script><a href="mailto:info%40workshop.ru?subject=Hi">Почта</a><p>sales&#64;workshop.ru</p><a href="/contacts">Контакты</a><a href="https://elsewhere.ru/contact">Other</a>')
  self.assertEqual({x['email'] for x in parser.emails},{'info@workshop.ru','sales@workshop.ru'})
  self.assertEqual(parser.links,['https://workshop.ru/contacts'])
  self.assertTrue(all(x['url']=='https://workshop.ru/' for x in parser.emails))
 def test_respects_robots(self):
  calls=[]
  def fetch(url):calls.append(url);return 'User-agent: *\nDisallow: /'
  with patch('research.public_url',return_value='https://workshop.ru/'):
   result=research_site('https://workshop.ru/',fetch=fetch,pause=lambda _:None)
  self.assertEqual(calls,['https://workshop.ru/robots.txt']);self.assertEqual(result['emails'],[])
 def test_visits_at_most_three_pages_and_tracks_sources(self):
  pages={'https://workshop.ru/robots.txt':'User-agent: *\nAllow: /','https://workshop.ru/':'<a href="/contact">Contacts</a><a href="/kontakt2">More</a><a href="/kontakt3">More</a>','https://workshop.ru/contact':'<a href="mailto:info@workshop.ru">Пишите</a>','https://workshop.ru/kontakt2':'<p>sales@workshop.ru</p>'}
  with patch('research.public_url',return_value='https://workshop.ru/'):
   result=research_site('https://workshop.ru/',fetch=pages.__getitem__,pause=lambda _:None)
  self.assertEqual(len(result['pages']),3);self.assertEqual(len(result['emails']),2)
  self.assertIn({'email':'info@workshop.ru','url':'https://workshop.ru/contact','kind':'mailto'},result['emails'])
 def test_robots_403_stops(self):
  def fetch(url):raise HTTPError(url,403,'Forbidden',{},None)
  with patch('research.public_url',return_value='https://workshop.ru/'):
   result=research_site('https://workshop.ru/',fetch=fetch,pause=lambda _:None)
  self.assertEqual(result['status'],'blocked');self.assertEqual(result['pages'],[])
 def test_osm_maps_contacts_and_absent_website(self):
  data={'elements':[{'type':'node','id':123,'tags':{'name':'Мастерская','craft':'carpenter','contact:email':'info@workshop.ru','addr:city':'Москва'}}]}
  with patch('research.build_opener') as opener:
   opener.return_value.open.return_value.__enter__.return_value=io.BytesIO(json.dumps(data).encode())
   rows=osm_search('Мебель и мастерские','Москва')
   request=opener.return_value.open.call_args.args[0]
   self.assertIn(b'carpenter',request.data)
  self.assertEqual(rows[0]['email'],'info@workshop.ru');self.assertEqual(rows[0]['website'],'');self.assertEqual(rows[0]['source_id'],'osm:node:123')
 def test_osm_refuses_entire_world_query(self):
  with self.assertRaises(Problem):osm_search('Мебель','Москва',bbox='-90,-180,90,180')
 def test_store_research_preserves_email_and_does_not_auto_approve(self):
  with tempfile.TemporaryDirectory() as d:
   store=Store(Path(d)/'db');store.import_rows([{'name':'Тест','website':'https://workshop.ru','email':'existing@workshop.ru'}]);identifier=store.all()[0]['id']
   evidence={'status':'checked','emails':[{'email':'info@workshop.ru','url':'https://workshop.ru/contact'}],'pages':['https://workshop.ru/contact'],'note':'Found'}
   with patch('research.research_site',return_value=evidence):lead=store.research(identifier)
   self.assertEqual(lead['email'],'existing@workshop.ru');self.assertEqual(lead['state'],'draft');self.assertFalse(lead['absence_confirmed']);self.assertEqual(json.loads(lead['research_json']),evidence)

if __name__=='__main__':unittest.main()
