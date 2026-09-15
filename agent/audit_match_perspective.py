#!/usr/bin/env python3
"""Audit source-backed high-scoring questions; repair in place only with --apply."""
import sys,sqlite3,json,hashlib,datetime,collections
from concurrent.futures import ThreadPoolExecutor
import build_v3_bank as v3
import build_v4_bank as v4
def main():
 con=sqlite3.connect(v3.DB);con.row_factory=sqlite3.Row
 clubs=con.execute('select * from clubs where active=1').fetchall()
 with ThreadPoolExecutor(max_workers=3) as pool:
  fd=dict(zip((2023,2024,2025),pool.map(v3.fetch_fd_season,(2023,2024,2025))))
 built={}
 for club in clubs:
  b=v3.Builder.__new__(v3.Builder)
  b.slug=club['slug'];b.name=club['name'];b.fd=fd;b.q=[];b.keys=set()
  b.fd_last3()
  for q in b.q:
   if '|high_scoring|' in q['semantic_key']:
    digest=hashlib.sha256(q['semantic_key'].encode()).hexdigest()[:16]
    built[(club['slug'],digest)]=q
 changes=[];total=0;unmatched=[]
 for club in clubs:
  for old in con.execute("select * from questions where club_id=? and question_text like '%high-scoring%' and semantic_key like 'v4bank|%'",(club['id'],)).fetchall():
   total+=1;parts=old['semantic_key'].split('|');base=built.get((club['slug'],parts[2]))
   if base is None:unmatched.append(old['id']);continue
   new=v4.make_variant(club['slug'],club['name'],base,int(parts[3][1:]))
   fields=('question_text','options_json','correct_index','explanation')
   if any(old[f]!=new[f] for f in fields):
    changes.append((club['slug'],dict(old),new))
 assert not unmatched,unmatched
 print(json.dumps({'audited':total,'changes':len(changes),'by_club':dict(collections.Counter(x[0] for x in changes))}))
 for slug,old,new in changes:
  print(json.dumps({'id':old['id'],'club':slug,'before':old['question_text'],'after':new['question_text']}))
 if '--apply' in sys.argv:
  path='/var/lib/clubdailyfive/clubquiz-before-perspective-fix-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S')+'.sqlite'
  with sqlite3.connect(path) as backup:con.backup(backup)
  with con:
   for slug,old,new in changes:
    con.execute('update questions set question_text=?,options_json=?,correct_index=?,explanation=?,content_hash=? where id=?',
     (new['question_text'],new['options_json'],new['correct_index'],new['explanation'],new['content_hash'],old['id']))
  assert con.execute('pragma integrity_check').fetchone()[0]=='ok'
  print('APPLIED; backup:',path)
if __name__=='__main__':main()
