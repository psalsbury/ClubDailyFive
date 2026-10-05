#!/usr/bin/env python3
"""Transfermarkt dataset research for the supported clubs.
Earliest dataset appearances are evidence, never assumed to be true debuts.
Promote only when a separate explicit debut source verifies all five clues.
"""
import collections,csv,datetime as dt,gzip,hashlib,json,pathlib,re,sqlite3,sys,unicodedata
from zoneinfo import ZoneInfo
BASE=pathlib.Path('/var/lib/clubdailyfive')
DB=BASE/'player-wordle/game.sqlite3'
TARGET=100
def norm(s):
 s=unicodedata.normalize('NFKD',s).encode('ascii','ignore').decode().lower()
 s=re.sub(r'\b(?:afc|fc|football club)\b','',s)
 return re.sub('[^a-z0-9]','',s)
def season_year(s):
 y=int(s.split('/')[0])
 return 2000+y if y<50 else 1900+y
def main():
 import collect_efl_players as research
 now=dt.datetime.now(dt.timezone.utc).isoformat();today=dt.datetime.now(ZoneInfo('Europe/London')).date()
 quiz=sqlite3.connect('file:'+str(BASE/'clubquiz.sqlite')+'?mode=ro',uri=True)
 scope=quiz.execute("select slug,name,league from clubs where active=1 and league in ('premier-league','championship')").fetchall()
 metadata={m['slug']:m for m in json.load(open(BASE/'efl-clubs.json'))}
 c=sqlite3.connect(str(DB),timeout=60);c.execute('pragma foreign_keys=on')
 aliases={'manchester-city':'man-city','manchester-united':'man-utd','newcastle-united':'newcastle','tottenham-hotspur':'tottenham','leeds-united':'leeds','coventry-city':'coventry','hull-city':'hull','ipswich-town':'ipswich'}
 clubs={};lookup={}
 for slug,name,league in scope:
  ws=aliases.get(slug,slug);cid=c.execute('select id from clubs where slug=?',(ws,)).fetchone()
  if not cid:
   c.execute('insert into clubs(slug,name,active) values(?,?,1)',(ws,name));cid=(c.execute('select last_insert_rowid()').fetchone()[0],)
  clubs[slug]=(cid[0],name,league)
  for v in [name,metadata.get(slug,{}).get('team',name)]:lookup[norm(v)]=slug
 counts=collections.defaultdict(collections.Counter);recent=collections.defaultdict(set);team_ids={}
 with open(BASE/'player-sources/performances.csv',encoding='utf-8-sig') as f:
  for row in csv.DictReader(f):
   slug=lookup.get(norm(row['team_name']))
   if not slug:continue
   try:y=season_year(row['season_name']);n=int(float(row['nb_on_pitch'] or 0))
   except (ValueError,TypeError):continue
   if y>today.year or n<=0:continue
   team_ids[slug]=row['team_id']
   if today.year-10<=y<=today.year:counts[slug][row['player_id']]+=n
   if y>=today.year-1:recent[slug].add(row['player_id'])
 eligible={s:{p for p,n in counts[s].items() if n>=25}|recent[s] for s in clubs}
 wanted=set().union(*eligible.values());profiles={}
 with open(BASE/'player-sources/profiles.csv',encoding='utf-8-sig') as f:
  for p in csv.DictReader(f):
   if p['player_id'] in wanted:profiles[p['player_id']]=p
 selected={}
 for s in clubs:
  selected[s]=[p for p in sorted(eligible[s],key=lambda p:(-counts[s][p],p)) if p in profiles][:TARGET]
 wanted={p for ps in selected.values() for p in ps}
 first={};match_counts=collections.Counter()
 with gzip.open(BASE/'transfermarkt-data/appearances.csv.gz','rt',encoding='utf-8') as f:
  for row in csv.DictReader(f):
   pid=row['player_id']
   if pid not in wanted or row['date']>today.isoformat() or int(row['minutes_played'] or 0)<=0:continue
   key=(row['player_club_id'],pid);match_counts[key]+=1
   if key not in first or row['date']<first[key]['date']:first[key]=row
 transfers=collections.defaultdict(list)
 with gzip.open(BASE/'transfermarkt-data/transfers.csv.gz','rt',encoding='utf-8') as f:
  for row in csv.DictReader(f):
   if row['player_id'] in wanted and row['transfer_date']<=today.isoformat():transfers[row['player_id']].append(row)
 for rows in transfers.values():rows.sort(key=lambda r:r['transfer_date'])
 c.execute("""CREATE TABLE IF NOT EXISTS transfermarkt_research(
 club_id INTEGER NOT NULL REFERENCES clubs(id),profile_id TEXT NOT NULL,player_name TEXT NOT NULL,
 status TEXT NOT NULL,evidence_json TEXT NOT NULL,missing_json TEXT NOT NULL,checked_at TEXT NOT NULL,
 PRIMARY KEY(club_id,profile_id))""")
 # Work from saved pages only. Empty/challenged live pages never become evidence.
 fresh_requests=0
 original_fetch=research.fetch
 def cached(url,cache,days=7):
  nonlocal fresh_requests
  p=pathlib.Path(cache)/hashlib.sha256(url.encode()).hexdigest()
  if p.exists():return p.read_text()
  if fresh_requests>=40:raise ValueError('Fresh evidence request budget reached; retained for next run')
  fresh_requests+=1
  return original_fetch(url,cache,days)
 research.fetch=cached
 checked=added=0;summary={}
 for slug,(cid,name,league) in sorted(clubs.items(),key=lambda item:c.execute('select count(*) from players where club_id=?',(item[1][0],)).fetchone()[0]):
  for pid in selected[slug]:
   p=profiles[pid];player=re.sub(r' \(\d+\)$','',p['player_name'])
   url=f"https://www.transfermarkt.co.uk/{p['player_slug']}/profil/spieler/{pid}"
   old=c.execute('select id from players where club_id=? and name=?',(cid,player)).fetchone()
   evidence={'profile':p,'recent_appearances':counts[slug][pid],
     'earliest_dataset_appearance':first.get((team_ids.get(slug),pid)),
     'transfer_history':transfers[pid],'dataset_observed_at':now,
     'note':'Dataset first appearance is not proof of the true club debut; citizenship is not automatically football nationality.'}
   missing=['verified_competitive_club_debut','verified_prior_senior_clubs','verified_football_nationality','verified_prominent_club_position']
   status='existing' if old else 'review'
   if not old and c.execute('select count(*) from players where club_id=?',(cid,)).fetchone()[0]<TARGET:
    member={**metadata.get(slug,{}),'name':name,'team':metadata.get(slug,{}).get('team',name)}
    try:x=research.research(member,p,counts[slug][pid],True)
    except Exception:x=None
    if x and x['status']=='approved':
     # Reject a transfer date misread as a debut, and contradictory match evidence.
     sentence=x['evidence']
     partial=re.findall(r'\b\d{1,2} (?:January|February|March|April|May|June|July|August|September|October|November|December)\b',sentence)
     earliest=evidence['earliest_dataset_appearance']
     if len(partial)!=1 or (earliest and earliest['date']<x['debut_date']):
      x=None
    if x and x['status']=='approved':
     c.execute("""INSERT INTO players(club_id,name,debut_age,position,position_rank,nationality,continent,appearances,prior_clubs,source_url,source_updated_at,debut_year)
      VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",(cid,player,x['debut_age'],x['position'],research.RANK[x['position']],x['nationality'],x['continent'],x['appearances'],x['prior_clubs'],x['source'],now,x['debut_year']))
     player_id=c.execute('select id from players where club_id=? and name=?',(cid,player)).fetchone()[0]
     research.protect(c,player_id,x['position'],x['source'],'Prominent position cross-checked against Transfermarkt profile')
     evidence['verified_game_facts']=x;missing=[];status='approved';added+=1
     c.execute('insert or replace into efl_player_research values(?,?,?,?,?,?,?,?)',(cid,player,pid,'approved',x['reason'],x['source'],json.dumps(x,ensure_ascii=False),now))
   c.execute('insert into transfermarkt_research values(?,?,?,?,?,?,?) on conflict(club_id,profile_id) do update set player_name=excluded.player_name,status=excluded.status,evidence_json=excluded.evidence_json,missing_json=excluded.missing_json,checked_at=excluded.checked_at',(cid,pid,player,status,json.dumps(evidence,ensure_ascii=False),json.dumps([] if old else missing),now))
   c.execute('insert into player_candidates(club_id,name,discovered_at,source_url,status) values(?,?,?,?,?) on conflict(club_id,name) do update set source_url=excluded.source_url,status=CASE WHEN player_candidates.status="approved" THEN "approved" ELSE excluded.status END',(cid,player,now,url,'approved' if status in ('approved','existing') else 'review'))
   if status=='review':c.execute('insert into enrichment_queue(club_id,player_name,status) values(?,?,"pending") on conflict(club_id,player_name) do nothing',(cid,player))
   checked+=1
  total=c.execute('select count(*) from players where club_id=?',(cid,)).fetchone()[0]
  summary[slug]={'league':league,'target':TARGET,'eligible_candidates':len(eligible[slug]),'transfermarkt_records':len(selected[slug]),'playable_players':total,'shortfall':max(0,TARGET-total)}
  c.commit()
 c.execute('insert into agent_runs(ran_at,status,details) values(?,?,?)',(now,'transfermarkt-research',f'Clubs={len(clubs)}; researched={checked}; new verified players={added}; target={TARGET} per club; unverified clues held for review'))
 c.commit();assert not c.execute('pragma foreign_key_check').fetchall()
 assert c.execute('pragma integrity_check').fetchone()[0]=='ok'
 (BASE/'player-bank-progress.json').write_text(json.dumps({'updated_at':now,'new_verified_players':added,'research_records':checked,'clubs':summary},indent=2))
 print(json.dumps({'clubs':len(clubs),'research_records':checked,'new_verified_players':added,'clubs_with_100_candidates':sum(v['transfermarkt_records']>=100 for v in summary.values()),'progress':summary}),flush=True)
if __name__=='__main__':main()
