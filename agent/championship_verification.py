#!/usr/bin/env python3
"""Championship verification pass over attributed cached player sources."""
import datetime as dt,json,pathlib,re,sqlite3,hashlib
import collect_efl_players as r
BASE=pathlib.Path('/var/lib/clubdailyfive')
MONTH='January|February|March|April|May|June|July|August|September|October|November|December'
original_debut=r.debut
def contextual_debut(raw,member,first_year):
 found=original_debut(raw,member,first_year)
 if found[0]:return found
 aliases={member['name'].lower(),member['team'].lower(),member['name'].lower().removesuffix(' city').removesuffix(' town').removesuffix(' united')}
 heading='';candidates=[]
 for chunk in re.findall(r'<h[234]\b[^>]*>.*?</h[234]>|<p\b[^>]*>.*?</p>',raw,re.S):
  text=r.clean(chunk)
  if chunk.startswith('<h'):heading=text.lower();continue
  sentences=re.split(r'(?<=[.!?])\s+',text);before=''
  for sentence in sentences:
   low=sentence.lower()
   if 'debut' in low and not any(s in low for s in ('league debut','international','under-','friendly','second debut','second spell','next day','following day')):
    own=[a for a in aliases if len(a)>3 and (a in heading or a in (before+' '+sentence).lower())]
    full=re.findall(r'\b(\d{1,2} (?:'+MONTH+r') (?:19|20)\d{2})\b',before)
    partial=re.findall(r'\b(\d{1,2} (?:'+MONTH+r'))\b',sentence)
    # Only resolve an omitted year from one explicit earlier date in the same paragraph.
    if own and len(full)==1 and len(partial)==1 and not re.search(r'\b(?:19|20)\d{2}\b',sentence):
     context=dt.datetime.strptime(full[0],'%d %B %Y').date()
     date=dt.datetime.strptime(partial[0]+' '+str(context.year),'%d %B %Y').date()
     if context<=date and date.year in (first_year,first_year+1):
      candidates.append((date,'Year supplied by explicit same-paragraph date '+full[0]+': '+text))
   before+=' '+sentence
 return min(candidates,key=lambda x:x[0]) if candidates else (None,None)
def main():
 c=sqlite3.connect(str(BASE/'player-wordle/game.sqlite3'),timeout=60);c.execute('pragma foreign_keys=on')
 folder=BASE/'verification-backups';folder.mkdir(exist_ok=True)
 c.backup(sqlite3.connect(str(folder/('championship-'+dt.datetime.now().strftime('%Y%m%d-%H%M%S')+'.sqlite3'))))
 members=[m for m in json.load(open(BASE/'efl-clubs.json')) if m['league']=='championship']
 def cached(url,cache,days=7):
  path=pathlib.Path(cache)/hashlib.sha256(url.encode()).hexdigest()
  if path.exists():return path.read_text()
  raise ValueError('No saved independent source')
 r.fetch=cached;r.debut=contextual_debut
 report={};added=[];checked=0
 for m in members:
  cid=c.execute('select id from clubs where slug=?',(m['slug'],)).fetchone()[0]
  before=c.execute('select count(*) from players where club_id=?',(cid,)).fetchone()[0]
  rows=c.execute('select profile_id,player_name,evidence_json from transfermarkt_research where club_id=?',(cid,)).fetchall()
  for pid,name,e in rows:
   if c.execute('select 1 from players where club_id=? and name=?',(cid,name)).fetchone():continue
   evidence=json.loads(e);profile=evidence['profile']
   try:x=r.research(m,profile,evidence['recent_appearances'],True)
   except Exception:continue
   checked+=1
   if x['status']!='approved':continue
   earliest=evidence.get('earliest_dataset_appearance')
   if earliest and earliest['date']<x['debut_date']:continue
   now=r.stamp()
   c.execute('insert into players(club_id,name,debut_age,position,position_rank,nationality,continent,appearances,prior_clubs,source_url,source_updated_at,debut_year) values(?,?,?,?,?,?,?,?,?,?,?,?)',(cid,name,x['debut_age'],x['position'],r.RANK[x['position']],x['nationality'],x['continent'],x['appearances'],x['prior_clubs'],x['source'],now,x['debut_year']))
   player=c.execute('select id from players where club_id=? and name=?',(cid,name)).fetchone()[0]
   r.protect(c,player,x['position'],x['source'],'Cross-checked prominent position; Championship verification')
   evidence['verified_game_facts']=x
   c.execute('update transfermarkt_research set status="approved",evidence_json=?,missing_json="[]",checked_at=? where club_id=? and profile_id=?',(json.dumps(evidence,ensure_ascii=False),now,cid,pid))
   c.execute('insert or replace into efl_player_research values(?,?,?,?,?,?,?,?)',(cid,name,pid,'approved',x['reason'],x['source'],json.dumps(x,ensure_ascii=False),now))
   c.execute('update player_candidates set status="approved" where club_id=? and name=?',(cid,name))
   c.execute('update enrichment_queue set status="approved" where club_id=? and player_name=?',(cid,name))
   added.append({'club':m['name'],'player':name,'debut':x['debut_date'],'evidence':x['evidence']})
  c.commit();after=c.execute('select count(*) from players where club_id=?',(cid,)).fetchone()[0]
  report[m['name']]={'added':after-before,'total':after}
 c.execute('insert into agent_runs(ran_at,status,details) values(?,?,?)',(r.stamp(),'championship-verification',json.dumps({'checked':checked,'added':len(added),'clubs':report})))
 c.commit();assert not c.execute('pragma foreign_key_check').fetchall();assert c.execute('pragma integrity_check').fetchone()[0]=='ok'
 result={'checked':checked,'added':len(added),'clubs':report,'players':added}
 (BASE/'championship-verification-latest.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));print(json.dumps(result,ensure_ascii=False))
if __name__=='__main__':main()
