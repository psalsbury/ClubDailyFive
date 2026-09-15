#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,datetime as dt,hashlib,io,json,os,random,sqlite3,sys,urllib.request
from zoneinfo import ZoneInfo
from question_variety import select_varied, validate_round, banned_question
DB=os.getenv('QUIZ_DB','/var/lib/clubdailyfive/clubquiz.sqlite'); BACKUPS='/var/backups/predictioncomp-question-db'; UK=ZoneInfo('Europe/London')
DIVS=('E0','E1','E2','E3')
ALIASES={'Arsenal':'arsenal','Aston Villa':'aston-villa','Bournemouth':'bournemouth','Brentford':'brentford','Brighton':'brighton','Chelsea':'chelsea','Coventry':'coventry-city','Crystal Palace':'crystal-palace','Everton':'everton','Fulham':'fulham','Hull':'hull-city','Ipswich':'ipswich-town','Leeds':'leeds-united','Liverpool':'liverpool','Man City':'manchester-city','Man United':'manchester-united','Newcastle':'newcastle-united',"Nott'm Forest":'nottingham-forest','Sunderland':'sunderland','Tottenham':'tottenham-hotspur'}
def season_start(d): return d.year if d.month>=7 else d.year-1
def scode(y): return f'{str(y)[-2:]}{str(y+1)[-2:]}'
def pdate(v):
  for f in ('%d/%m/%Y','%d/%m/%y'):
    try:return dt.datetime.strptime(v.strip(),f).date()
    except ValueError: pass
  return None
def load_current(target):
  y=season_start(dt.date.fromisoformat(target)); out={s:[] for s in ALIASES.values()}
  for div in DIVS:
    url=f'https://www.football-data.co.uk/mmz4281/{scode(y)}/{div}.csv'
    try:
      req=urllib.request.Request(url,headers={'User-Agent':'ClubDailyFive/2.0'}); raw=urllib.request.urlopen(req,timeout=30).read().decode('utf-8-sig','replace')
    except Exception as e:
      print(f'skip {url}: {e}',file=sys.stderr); continue
    for r in csv.DictReader(io.StringIO(raw)):
      if not all((r.get(k) or '').strip() for k in ('Date','HomeTeam','AwayTeam','FTHG','FTAG')): continue
      d=pdate(r['Date'])
      if not d or d>dt.date.fromisoformat(target): continue
      for team in (r['HomeTeam'],r['AwayTeam']):
        slug=ALIASES.get(team)
        if slug:
          x=dict(r); x['_date']=d; x['_alias']=team; x['_url']=url; out[slug].append(x)
  return out
def persp(r):
  home=r['HomeTeam']==r['_alias']; gf=int(r['FTHG'] if home else r['FTAG']); ga=int(r['FTAG'] if home else r['FTHG']); opp=r['AwayTeam'] if home else r['HomeTeam']
  yellow=int((r.get('HY') if home else r.get('AY')) or 0); red=int((r.get('HR') if home else r.get('AR')) or 0); return gf,ga,opp,yellow,red
def ranked(rows,target):
  return sorted(rows,key=lambda r:(int(r['use_count'] or 0),r['last_used_date'] or '',hashlib.sha256(f'{target}|{r["id"]}'.encode()).hexdigest()))
def numopts(v,seed):
  vals=list(dict.fromkeys([str(v),str(max(0,v-1)),str(v+1),str(v+2),str(v+3)])); random.Random(hashlib.sha256(seed.encode()).digest()).shuffle(vals); vals=vals[:4]
  if str(v) not in vals: vals[-1]=str(v)
  return vals,vals.index(str(v))
def scoreopts(a,b,seed):
  correct=f'{a}-{b}'; cand=list(dict.fromkeys([correct,f'{a+1}-{b}',f'{a}-{b+1}',f'{max(0,a-1)}-{b}',f'{a}-{max(0,b-1)}']))
  random.Random(hashlib.sha256(seed.encode()).digest()).shuffle(cand); vals=cand[:4]
  if correct not in vals: vals[-1]=correct
  return vals,vals.index(correct)
class FreshUnavailable(RuntimeError):
  pass

def used_match_fact(con,club_id,match_date,slot):
  # Older IDs included the publication date. Recognise those too.
  aliases=('score','season-score','recent-score') if slot=='score' else ('recent-'+slot,slot)
  for row in con.execute("select semantic_key from questions where club_id=? and fact_date=? and use_count>0 and (semantic_key like 'dailyfresh|%' or semantic_key like 'matchfact|%')",(club_id,match_date)):
    if row[0].split('|')[-1] in aliases:return True
  return False

def insert_fresh(con,club,target,rows,selector_override=None):
  rows=sorted(rows,key=lambda r:r['_date'],reverse=True)
  if not rows:raise FreshUnavailable('No completed matches available')
  latest=rows[0]; age=(dt.date.fromisoformat(target)-latest['_date']).days
  if not 0<=age<=10:raise FreshUnavailable('Latest match is outside the 10-day window')
  gf,ga,opp,yellow,red=persp(latest)
  selector=int(hashlib.sha256(f'{target}|{club["slug"]}|fresh'.encode()).hexdigest(),16)%3 if selector_override is None else selector_override
  slot=('yellow','red','score')[selector%3]
  date=latest['_date'].isoformat()
  if used_match_fact(con,club['id'],date,slot):raise FreshUnavailable('Match fact already asked')
  home=latest['HomeTeam']==latest['_alias']; venue='at home to' if home else 'away to'
  if slot in ('yellow','red'):
    field=('HY' if home else 'AY') if slot=='yellow' else ('HR' if home else 'AR')
    if not (latest.get(field) or '').strip():raise FreshUnavailable('Card statistic unavailable')
    val=int(latest[field]);opts,idx=numopts(val,f'{date}|{club["slug"]}|{slot}')
    text=f"How many {slot} cards did {club['name']} receive in their league match against {opp} on {date}?"
    exp=f"{club['name']} received {val} {slot} cards against {opp} on {date}."
  else:
    opts,idx=scoreopts(gf,ga,f'{date}|{club["slug"]}|score')
    text=f"What was the score for {club['name']} in their league match {venue} {opp} on {date}?"
    exp=f"{club['name']} played {venue} {opp} on {date}; the score for {club['name']} was {gf}-{ga}."
  key=f'matchfact|{club["slug"]}|{date}|{slot}'
  existing=con.execute('select id from questions where semantic_key=?',(key,)).fetchone()
  if existing:return existing[0]
  payload=json.dumps(opts,ensure_ascii=False);ch=hashlib.sha256((text+'|'+key).encode()).hexdigest()
  con.execute('insert into questions(club_id,question_text,options_json,correct_index,explanation,source_url,source_label,content_hash,semantic_key,status,question_kind,fact_date,use_count,last_used_date) values(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(club['id'],text,payload,idx,exp,latest['_url'],'Football-Data.co.uk current-season records',ch,key,'reviewed','recent',date,0,None))
  return con.execute('select id from questions where semantic_key=?',(key,)).fetchone()[0]

def insert_season_fact(con,club,target,rows,slot):
  if not rows:raise FreshUnavailable('No season data')
  stats=[persp(r) for r in rows]
  values={'wins':sum(a>b for a,b,*_ in stats),'draws':sum(a==b for a,b,*_ in stats),'losses':sum(a<b for a,b,*_ in stats),'goals-scored':sum(r[0] for r in stats),'goals-conceded':sum(r[1] for r in stats),'yellow':sum(r[3] for r in stats),'red':sum(r[4] for r in stats)}
  if slot in ('yellow','red'):
    fields=('HY','AY') if slot=='yellow' else ('HR','AR')
    if any(not (r.get(fields[0] if r['HomeTeam']==r['_alias'] else fields[1]) or '').strip() for r in rows):raise FreshUnavailable('Missing season card statistics')
  y=season_start(dt.date.fromisoformat(target));season=f'{y}-{str(y+1)[-2:]}'
  val=values[slot];date=max(r['_date'] for r in rows).isoformat()
  key=f'seasonfact|{club["slug"]}|{season}|{slot}|{val}'
  existing=con.execute('select id,use_count from questions where semantic_key=?',(key,)).fetchone()
  if existing:
    if existing['use_count']:raise FreshUnavailable('Season fact already asked')
    return existing['id']
  wording={'wins':'league wins','draws':'league draws','losses':'league losses','goals-scored':'goals scored in the league','goals-conceded':'goals conceded in the league','yellow':'yellow cards in the league','red':'red cards in the league'}[slot]
  text=f"How many {wording} had {club['name']} recorded in {season}, through {date}?"
  exp=f"Across their {len(rows)} completed league matches through {date}, {club['name']} recorded {val} {wording}."
  opts,answer=numopts(val,key);payload=json.dumps(opts)
  con.execute('insert into questions(club_id,question_text,options_json,correct_index,explanation,source_url,source_label,content_hash,semantic_key,status,question_kind,fact_date,use_count,last_used_date) values(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(club['id'],text,payload,answer,exp,rows[0]['_url'],'Football-Data.co.uk season records',hashlib.sha256(key.encode()).hexdigest(),key,'reviewed','recent',date,0,None))
  return con.execute('select id from questions where semantic_key=?',(key,)).fetchone()[0]

def choose_round(con,club,target,rows,bank,fixed=None):
  for choice in (None,0,1,2):
    con.execute('savepoint fresh_choice')
    try:
      qid=insert_fresh(con,club,target,rows,choice)
      fresh=con.execute('select * from questions where id=?',(qid,)).fetchone()
      selected=list(fixed) if fixed is not None else select_varied(bank,fresh)
      validate_round([*selected,fresh])
    except (FreshUnavailable,RuntimeError,ValueError):
      con.execute('rollback to fresh_choice');con.execute('release fresh_choice');continue
    con.execute('release fresh_choice')
    return selected,fresh
  for slot in ('wins','draws','losses','goals-scored','goals-conceded','yellow','red'):
    con.execute('savepoint season_choice')
    try:
      qid=insert_season_fact(con,club,target,rows,slot)
      fresh=con.execute('select * from questions where id=?',(qid,)).fetchone()
      selected=list(fixed) if fixed is not None else select_varied(bank,fresh)
      validate_round([*selected,fresh])
    except (FreshUnavailable,RuntimeError,ValueError):
      con.execute('rollback to season_choice');con.execute('release season_choice');continue
    con.execute('release season_choice')
    return selected,fresh
  # When match facts are exhausted or stale, use an unused recent-season fact.
  y=season_start(dt.date.fromisoformat(target))
  seasons=(f'{y}-{str(y+1)[-2:]}',f'{y-1}-{str(y)[-2:]}')
  for candidate in bank:
    if candidate['use_count'] or not any(season in candidate['question_text'] for season in seasons):continue
    try:
      selected=list(fixed) if fixed is not None else select_varied(bank,candidate)
      validate_round([*selected,candidate])
    except (RuntimeError,ValueError):continue
    return selected,candidate
  raise RuntimeError(f'{club["slug"]}: no unused match or recent-season fact fits this round')

def main():
  ap=argparse.ArgumentParser(); ap.add_argument('--date'); ap.add_argument('--self-test',action='store_true'); a=ap.parse_args(); target=a.date or (dt.datetime.now(UK).date()+dt.timedelta(days=1)).isoformat()
  con=sqlite3.connect(DB,timeout=60); con.row_factory=sqlite3.Row; con.execute('pragma foreign_keys=on'); clubs=con.execute('select id,slug,name from clubs where active=1 order by name').fetchall()
  if a.self_test:
    counts=dict(con.execute("select c.slug,count(q.id) from clubs c left join questions q on q.club_id=c.id and q.semantic_key like 'v4bank|%' group by c.id")); print(json.dumps({'database':con.execute('pragma integrity_check').fetchone()[0],'clubs':len(clubs),'bank_counts':counts,'bank_per_club_required':300,'daily_mix':'4 bank + 1 unused match fact or recent-season fallback','recent_cutoff_days':10,'openai_api_required':False})); return
  if con.execute('select count(*) from daily_questions where quiz_date=?',(target,)).fetchone()[0]:
    print(f'Round already published for {target}; preserving player questions'); return
  from sterling import assert_sterling
  for question in con.execute("select question_text,options_json,explanation from questions where status='reviewed'"):
    assert_sterling(dict(question))
  current=load_current(target); os.makedirs(BACKUPS,exist_ok=True); backup=f"{BACKUPS}/clubquiz-before-daily-{dt.datetime.now().strftime('%Y%m%d-%H%M%S')}.sqlite"
  with sqlite3.connect(backup) as dest: con.backup(dest)
  try:
    con.execute('begin immediate'); con.execute('delete from daily_questions where quiz_date=?',(target,)); rounds=[]
    for club in clubs:
      bank=ranked(con.execute("select * from questions where club_id=? and status='reviewed' and semantic_key like 'v4bank|%'",(club['id'],)).fetchall(),target)
      bank = [q for q in bank if not banned_question(q)]
      if len(bank)<4: raise RuntimeError(f"{club['slug']}: insufficient eligible bank questions")
      selected,fresh=choose_round(con,club,target,current.get(club['slug'],[]),bank)
      fresh_id=fresh['id']
      validate_round([*selected,fresh])
      ids=[r['id'] for r in selected]+[fresh_id]
      random.Random(hashlib.sha256(f'{target}|{club["slug"]}|shuffle'.encode()).digest()).shuffle(ids); rounds.append((club,ids))
    for club,ids in rounds:
      for pos,qid in enumerate(ids,1):
        con.execute('insert into daily_questions(club_id,quiz_date,position,question_id) values(?,?,?,?)',(club['id'],target,pos,qid))
    con.execute("insert into generation_runs(run_date,finished_at,status,notes) values(?,CURRENT_TIMESTAMP,'complete',?)",(target,f'V4: 4/300 least-recently-used bank + 1 unused match fact/recent-season fallback; 10-day recent cutoff; backup={backup}')); con.commit()
  except Exception: con.rollback(); raise
  print(f'published {len(clubs)*5} questions for {target}')
if __name__=='__main__':
  try: main()
  except Exception as e: print(f'quiz publication failed: {e}',file=sys.stderr); raise SystemExit(1)
