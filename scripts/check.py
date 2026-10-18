#!/usr/bin/env python3
"""Check generated artifacts and references without external dependencies."""
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit,unquote
import json
ROOT=Path(__file__).resolve().parents[1]
class Page(HTMLParser):
 def __init__(self):super().__init__();self.ids=[];self.refs=[];self.h1=0;self.title=False;self.description=False;self.og=False;self.text=[]
 def handle_starttag(self,tag,attrs):
  a=dict(attrs)
  if 'id' in a:self.ids.append(a['id'])
  if tag=='h1':self.h1+=1
  if tag=='title':self.title=True
  if tag=='meta' and a.get('name')=='description':self.description=bool(a.get('content'))
  if tag=='meta' and a.get('property')=='og:title':self.og=True
  if tag=='img':assert 'alt' in a,'Image missing alt'
  if tag=='script' and a.get('type')=='application/ld+json':self.in_json=True
  for key in ('href','src'):
   if key in a:self.refs.append(a[key])
 def handle_data(self,data):self.text.append(data)
pages={}
for path in list(ROOT.glob('*.html'))+list((ROOT/'articles').glob('*.html')):
 page=Page();page.feed(path.read_text());pages[path.resolve()]=page
 assert page.h1==1,(path,'h1 count',page.h1)
 assert len(page.ids)==len(set(page.ids)),(path,'duplicate IDs')
 assert page.title and page.description and page.og,(path,'metadata')
 assert 'Макров' not in path.read_text(),(path,'surname')
for path,page in pages.items():
 for ref in page.refs:
  u=urlsplit(ref)
  if u.scheme or u.netloc:continue
  target=(path.parent/unquote(u.path or path.name)).resolve()
  assert target.is_relative_to(ROOT),(path,'escaped root',ref)
  assert target.exists(),(path,'missing file',ref)
  if u.fragment and target.suffix=='.html':assert unquote(u.fragment) in pages[target].ids,(path,'missing anchor',ref)
print(f'PASS: {len(pages)} pages; headings, metadata, surname, local files and fragment targets.')
