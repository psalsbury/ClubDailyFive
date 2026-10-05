#!/usr/bin/env python3
"""Championship verification pass over attributed cached player sources."""
import datetime as dt,json,pathlib,re,sqlite3,hashlib
import collect_efl_players as r
BASE=pathlib.Path('/var/lib/clubdailyfive')
MONTH='January|February|March|April|May|June|July|August|September|October|November|December'
original_debut=r.debut
def contextual_debut(raw,member,first_year):
 safe=re.sub(r'<p\b[^>]*>.*?</p>',lambda m: '' if any(t in r.clean(m[0]).lower() for t in ('two days later','three days later','next day','following day','opened the scoring','collected wes thomas')) else m[0],raw,flags=re.S)
 found=original_debut(safe,member,first_year)
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

def football_nationality(raw,citizenship):
 # Require positive senior national-team caps in the player's actual infobox.
 box=re.search(r'<table[^>]*class="[^"]*infobox.*?</table>',raw,re.S)
 if not box or 'International career' not in box[0]:return None
 section=box[0].split('International career',1)[1].split('Managerial career',1)[0]
 allowed={r.normalized(x):x.strip() for x in re.split(r'\s{2,}|\s*/\s*|,',citizenship)}
 found=[]
 for row in re.findall(r'<tr\b[^>]*>(.*?)</tr>',section,re.S):
  h=re.search(r'<th\b[^>]*>(.*?)</th>',row,re.S)
  cells=re.findall(r'<td\b[^>]*>(.*?)</td>',row,re.S)
  if not h or len(cells)<2:continue
  team=r.clean(cells[0]);caps=r.clean(cells[1]);years=re.findall(r'(?:19|20)\d{2}',r.clean(h[1]))
  if not years or not caps.isdigit() or int(caps)<=0:continue
  key=r.normalized(team)
  if key not in allowed:continue # Excludes youth, B and C teams.
  found.append((int(years[0]),allowed[key],r.clean(row)))
 if not found:return None
 latest=max(x[0] for x in found);choices=[x for x in found if x[0]==latest]
 if len({x[1] for x in choices})!=1:return None
 return choices[0][1],choices[0][2]

original_research=r.research
def nationality_research(member,profile,count,history):
 x=original_research(member,profile,count,history)
 if x.get('reason')!='Multiple citizenships require football nationality evidence':return x
 url,raw=r.wiki_player(x['name']);national=football_nationality(raw,profile.get('citizenship',''))
 if not national:return x
 resolved=dict(profile,citizenship=national[0])
 x=original_research(member,resolved,count,history)
 if x['status']=='approved':
  x['nationality_evidence']={'source':url,'senior_international_row':national[1],'original_citizenship':profile['citizenship']}
 return x


# Explicit debut corrections cross-checked against dated match records.
MANUAL_DEBUTS={
 ('birmingham-city','Clayton Donaldson'):('2014-08-09','https://www.sporting-heroes.net/football/birmingham-city-fc/clayton-donaldson-13258/league-appearances_a33570/','Opening-day debut at Middlesbrough; date corroborates career narrative.'),
 ('preston-north-end','Lukas Nmecha'):('2018-08-11','https://www.espn.co.uk/football/match/_/gameId/515664/preston-north-end-swansea-city','Debut two days after the 9 August loan, starting at Swansea on 11 August.'),
 ('charlton-athletic','Joe Aribo'):('2016-10-04','https://www.skysports.com/football/charlton-athletic-vs-crawley-town/teams/367332','First-team debut vs Crawley; dated match lineup corrects erroneous 16 October biography date.')
}
def verified_research(member,profile,count,history):
 name=re.sub(r' \(\d+\)$','',profile['player_name'])
 manual=MANUAL_DEBUTS.get((member['slug'],name))
 if not manual:return nationality_research(member,profile,count,history)
 saved=r.debut
 try:
  r.debut=lambda raw,member,year:(dt.date.fromisoformat(manual[0]),manual[2])
  x=nationality_research(member,profile,count,history)
 finally:r.debut=saved
 if x['status']=='approved':x['debut_source']=manual[1]
 return x

def main():
 c=sqlite3.connect(str(BASE/'player-wordle/game.sqlite3'),timeout=60);c.execute('pragma foreign_keys=on')
 folder=BASE/'verification-backups';folder.mkdir(exist_ok=True)
 c.backup(sqlite3.connect(str(folder/('championship-'+dt.datetime.now().strftime('%Y%m%d-%H%M%S')+'.sqlite3'))))
 members=[m for m in json.load(open(BASE/'efl-clubs.json')) if m['league']=='championship']
 def cached(url,cache,days=7):
  path=pathlib.Path(cache)/hashlib.sha256(url.encode()).hexdigest()
  if path.exists():return path.read_text()
  raise ValueError('No saved independent source')
 r.fetch=cached;r.debut=contextual_debut;r.research=verified_research
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
