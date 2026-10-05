#!/usr/bin/env python3
"""Expand Derby from the attributed all-competition 100-appearance list."""
import sys,re,json,datetime as dt,sqlite3,pathlib,urllib.parse
sys.path.insert(0,str(pathlib.Path(__file__).parent))
import collect_efl_players as r
from championship_verification import contextual_debut
from source_utils import fetch,clean,infobox,broad_position
from player_country import continent
BASE=r.BASE
URL='https://en.wikipedia.org/wiki/List_of_Derby_County_F.C._players'
POSITIONS={'GK':'Goalkeeper','DF':'Defender','CB':'Defender','FB':'Defender','LB':'Defender','RB':'Defender','SW':'Defender','MF':'Midfielder','CM':'Midfielder','DM':'Midfielder','AM':'Midfielder','LM':'Midfielder','RM':'Midfielder','HB':'Midfielder','LH':'Midfielder','RH':'Midfielder','WH':'Midfielder','FW':'Forward','IF':'Forward','IL':'Forward','IR':'Forward','LW':'Forward','RW':'Forward','OL':'Forward','OR':'Forward','W':'Forward'}
def historical_debut(page,first):
 for paragraph in re.findall(r'<p\b[^>]*>.*?</p>',page,re.S):
  text=clean(paragraph)
  for sentence in re.split(r'(?<=[.!?])\s+',text):
   low=sentence.lower()
   if 'debut' not in low or 'derby' not in low:continue
   if any(word in low for word in ('league debut','international','friendly','second debut','second spell')):continue
   dates=re.findall(r'\b(\d{1,2} (?:January|February|March|April|May|June|July|August|September|October|November|December) (?:18|19|20)\d{2})\b',sentence)
   if len(dates)!=1:continue
   date=dt.datetime.strptime(dates[0],'%d %B %Y').date()
   if date.year in (first,first+1):return date,sentence
 return None,None

def main():
 raw=fetch(URL,BASE/'efl-cache/derby',30)
 table=next(t for t in re.findall(r'<table\b.*?</table>',raw,re.S) if 'Walter Roulstone' in t)
 academy_url='https://www.dcfc.co.uk/page/academy-hall-of-fame'
 academy=fetch(academy_url,BASE/'efl-cache/derby',30)
 official={}
 for heading,body in re.findall(r'<h4\b[^>]*>(.*?)</h4>(.*?)(?=<h4\b|$)',academy,re.S):
  text=clean(body);match=re.search(r'First Team Debut:\s*(\d{1,2})(?:st|nd|rd|th)?\s*(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})',text)
  if match:official[r.normalized(clean(heading))]=(dt.datetime.strptime(' '.join(match.groups()),'%d %B %Y').date(),text)
 manual={
 'Matthew Clarke':('2019-08-05','https://en.wikipedia.org/wiki/Matt_Clarke_(footballer,_born_1996)','Explicit Derby debut three days after 2 August 2019 signing, opening game at Huddersfield.'),
 'Tom Ince':('2015-02-07','https://en.wikipedia.org/wiki/Tom_Ince','Explicit Derby debut five days after 2 February 2015 loan; scored twice against Bolton.'),
 'Gary Teale':('2007-01-13','https://en.wikipedia.org/wiki/Gary_Teale','Derby debut explicitly dated 13 January 2007 in Sheffield Wednesday win.'),
 'Stephen Pearson':('2007-01-13','https://www.skysports.com/football/derby-county-vs-sheffield-wednesday/teams/79802','Career narrative identifies debut in this match; dated lineup independently confirms appearance.'),
 'Jamie Ward':('2011-02-19','https://www.skysports.com/football/scunthorpe-united-vs-derby-county/report/216927','Dated match report explicitly identifies Ward as Derby debutant.'),
 'Richard Keogh':('2012-08-14','https://www.dcfc.co.uk/news/2012/08/derby-county-5-5-scunthorpe-united','Club match report explicitly identifies Keogh debut and goal.'),
 'Kevin Hector':('1966-09-17','https://www.sporting-heroes.net/football/derby-county-fc/kevin-hector-8073/biography-of-his-football-career-at-derby-county_a11551/','Dated Palace debut corroborated as first competitive appearance by Derby County Memories programme article.')
 }
 candidates=[]
 for row in re.findall(r'<tr\b.*?</tr>',table,re.S):
  cells=re.findall(r'<td\b[^>]*>(.*?)</td>',row,re.S)
  if len(cells)<6:continue
  link=re.search(r'<a\b[^>]*href="([^"]+)"[^>]*>(.*?)</a>',cells[0],re.S)
  years=re.findall(r'(?:18|19|20)\d{2}',clean(cells[3]))
  if not link or not years or not clean(cells[4]).isdigit():continue
  candidates.append(dict(name=clean(link[2]),url=urllib.parse.urljoin(URL,link[1]),nationality=clean(cells[1]),position_code=clean(cells[2]),career=clean(cells[3]),first_year=int(years[0]),appearances=int(clean(cells[4])),list_source=URL))
 c=sqlite3.connect(BASE/'player-wordle/game.sqlite3',timeout=60);c.execute('pragma foreign_keys=on');r.protection(c)
 cid=c.execute("select id from clubs where slug='derby-county'").fetchone()[0]
 folder=BASE/'verification-backups';folder.mkdir(exist_ok=True)
 with sqlite3.connect(folder/('derby-wikipedia-'+dt.datetime.now().strftime('%Y%m%d-%H%M%S')+'.sqlite3')) as b:c.backup(b)
 original=list(c.execute('select * from daily_game order by game_date,club_id'))
 before=c.execute('select count(*) from players where club_id=?',(cid,)).fetchone()[0]
 c.execute('CREATE TABLE IF NOT EXISTS wikipedia_player_research(club_id INTEGER,player_name TEXT,status TEXT,evidence_json TEXT,checked_at TEXT,PRIMARY KEY(club_id,player_name))')
 member={'name':'Derby County','team':'Derby County','slug':'derby-county'}
 added=[];report=[]
 for item in sorted(candidates,key=lambda x:-x['first_year']):
  name=item['name'];facts=dict(item);status='review'
  if c.execute('select 1 from players where club_id=? and name=?',(cid,name)).fetchone():continue
  try:
   page=fetch(item['url'],BASE/'efl-cache/players',30);box=infobox(page)
   rows=r.career(page);matches=[i for i,(_,team) in enumerate(rows) if r.normalized(team)=='derbycounty']
   if not matches:raise ValueError('Senior Derby career not confirmed')
   start=matches[0];first=rows[start][0]
   if first!=item['first_year']:raise ValueError('Career start sources disagree')
   pos=POSITIONS.get(item['position_code'])
   if not pos:raise ValueError('Utility role requires prominent-position review')
   bio_pos=broad_position(clean(box.get('Position(s)',box.get('Position',''))))
   if bio_pos and bio_pos!=pos:raise ValueError('Position sources disagree')
   birth=re.search(r'class="bday"[^>]*>(\d{4}-\d{2}-\d{2})',page)
   if not birth:
    born=clean(box.get('Born',''))
    match=re.search(r'\b(\d{1,2} (?:January|February|March|April|May|June|July|August|September|October|November|December) (?:18|19|20)\d{2})\b',born)
    if match:
     value=dt.datetime.strptime(match[1],'%d %B %Y').date().isoformat()
     birth=re.match(r'(.*)',value)
   if not birth:raise ValueError('Date of birth not sourced')
   date,evidence=official.get(r.normalized(name),(None,None))
   if date:facts['debut_source']=academy_url
   elif name in manual:
    date=dt.date.fromisoformat(manual[name][0]);facts['debut_source']=manual[name][1];evidence=manual[name][2]
   else:date,evidence=contextual_debut(page,member,first)
   if not date:date,evidence=historical_debut(page,first)
   if not date:raise ValueError('Exact first competitive debut requires further evidence')
   dob=dt.date.fromisoformat(birth[1]);age=date.year-dob.year-((date.month,date.day)<(dob.month,dob.day))
   if not 14<=age<=45:raise ValueError('Debut age outside valid range')
   nat=item['nationality'];cont=continent(nat)
   if cont=='Other':raise ValueError('Nationality needs review')
   prior=len({r.normalized(team) for year,team in rows[:start] if year<=date.year})
   facts.update(debut_date=date.isoformat(),debut_age=age,debut_year=date.year,birth_date=birth[1],debut_evidence=evidence,position=pos,prior_clubs=prior,continent=cont)
   # Active totals on the source predate today: retain candidates until refreshed.
   if re.search(r'2026|present',item['career'].split('–')[-1]):raise ValueError('Active player total needs current match reconciliation')
   c.execute('insert or ignore into players(club_id,name,debut_age,position,position_rank,nationality,continent,appearances,prior_clubs,source_url,source_updated_at,debut_year) values(?,?,?,?,?,?,?,?,?,?,?,?)',(cid,name,age,pos,r.RANK[pos],nat,cont,item['appearances'],prior,item['url'],r.stamp(),date.year))
   pid=c.execute('select id from players where club_id=? and name=?',(cid,name)).fetchone()[0]
   r.protect(c,pid,pos,URL,'Typical position at Derby explicitly listed; biographical role checked')
   status='approved';added.append(name)
  except Exception as e:facts['reason']=str(e)
  c.execute('insert or replace into wikipedia_player_research values(?,?,?,?,?)',(cid,name,status,json.dumps(facts,ensure_ascii=False),r.stamp()))
  c.execute('insert or replace into efl_player_research values(?,?,?,?,?,?,?,?)',(cid,name,'wiki:'+item['url'].rsplit('/',1)[-1],status,facts.get('reason','Source-backed competitive career, debut and appearance total'),item['url'],json.dumps(facts,ensure_ascii=False),r.stamp()))
  c.commit();report.append(dict(name=name,status=status,reason=facts.get('reason')))
  print(name,status,facts.get('reason',''),flush=True)
  if before+len(added)>=100:break
 assert original==list(c.execute('select * from daily_game order by game_date,club_id'))
 assert c.execute('pragma integrity_check').fetchone()[0]=='ok'
 assert not c.execute('pragma foreign_key_check').fetchall()
 result=dict(candidates=len(candidates),before=before,added=added,total=c.execute('select count(*) from players where club_id=?',(cid,)).fetchone()[0],research=report)
 (BASE/'derby-wikipedia-progress.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
 c.execute('insert into agent_runs(ran_at,status,details) values(?,?,?)',(r.stamp(),'derby-wikipedia-expansion',json.dumps({k:v for k,v in result.items() if k!='research'})))
 c.commit();print(json.dumps({k:v for k,v in result.items() if k!='research'}),flush=True)
if __name__=='__main__':main()
