#!/usr/bin/env python3
"""Send a bounded batch of already approved drafts. Dry-run by default."""
import argparse
import os
import time
from pathlib import Path
from core import Store,Problem,smtp_config
ROOT=Path(__file__).resolve().parent

def run_batch(store,limit=10,interval=30,send=False,deliver=None,pause=time.sleep):
 leads=[row for row in store.all() if row['state']=='approved'][:max(1,min(limit,50))]
 if not send:return {'approved':len(leads),'sent':0,'failed':0,'unknown':0,'dry_run':True}
 if deliver is None:smtp_config()
 result={'approved':len(leads),'sent':0,'failed':0,'unknown':0,'dry_run':False}
 for index,lead in enumerate(leads):
  if index:pause(max(interval,5))
  status=store.send(lead['id'],deliver)['state'];result[status]+=1
  # Unknown outcomes and definite provider rejections stop the batch for inspection.
  if status!='sent':break
 return result

def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--db',default=os.environ.get('LEADFINDER_DB_PATH',str(ROOT/'data/leads.sqlite3')));parser.add_argument('--limit',type=int,default=10);parser.add_argument('--interval',type=int,default=30);parser.add_argument('--send-approved',action='store_true');args=parser.parse_args()
 try:print(run_batch(Store(args.db),args.limit,args.interval,args.send_approved))
 except Problem as error:parser.exit(1,str(error)+'\n')
if __name__=='__main__':main()
