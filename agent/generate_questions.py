#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,datetime as dt,hashlib,io,json,os,random,re,sqlite3,sys,urllib.request
from zoneinfo import ZoneInfo
from display_dates import display_date
from improve_questions import normalise
from question_quality import clean_text, lint_question, numeric_options, score_options, numeric_rank_report
from question_variety import select_varied, validate_round, banned_question
DB=os.getenv('QUIZ_DB','/var/lib/clubdailyfive/clubquiz.sqlite'); BACKUPS='/var/backups/clubdailyfive-question-db'; UK=ZoneInfo('Europe/London')
DIVS=('E0','E1','E2','E3')
ALIASES={'Arsenal':'arsenal','Aston Villa':'aston-villa','Bournemouth':'bournemouth','Brentford':'brentford','Brighton':'brighton','Chelsea':'chelsea','Coventry':'coventry-city','Crystal Palace':'crystal-palace','Everton':'everton','Fulham':'fulham','Hull':'hull-city','Ipswich':'ipswich-town','Leeds':'leeds-united','Liverpool':'liverpool','Man City':'manchester-city','Man United':'manchester-united','Newcastle':'newcastle-united',"Nott'm Forest":'nottingham-forest','Sunderland':'sunderland','Tottenham':'tottenham-hotspur'}
def catalogue_aliases():
  path='/var/lib/clubdailyfive/efl-clubs.json'
  if os.path.exists(path):
    with open(path,encoding='utf-8') as f:
      return {m['alias']:m['slug'] for m in json.load(f)}
  return {}
ALIASES.update(catalogue_aliases())
NO_REPEAT_DAYS=30
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
def semantic_family(row):
  key=row['semantic_key'] or ''
  parts=key.rsplit('|',1)
  return parts[0] if len(parts)==2 and parts[1].startswith('v') and parts[1][1:].isdigit() else key

def ranked(rows,target):
  # The bank stores several wording variants for one underlying fact. Rank
  # by the combined history of the fact family so a rewording is never
  # mistaken for a new question.
  rows=list(rows); history={}
  for row in rows:
    family=semantic_family(row)
    used,last=history.get(family,(0,''))
    history[family]=(used+int(row['use_count'] or 0),max(last,row['last_used_date'] or ''))
  return sorted(rows,key=lambda r:(history[semantic_family(r)][0],history[semantic_family(r)][1],hashlib.sha256(f'{target}|{r["id"]}'.encode()).hexdigest()))
def eligible_history_bank(con,club_id,target,days=None):
  cutoff=(dt.date.fromisoformat(target)-dt.timedelta(days=days or NO_REPEAT_DAYS)).isoformat()
  recent=con.execute("select q.* from daily_questions d join questions q on q.id=d.question_id where d.club_id=? and d.quiz_date>=? and d.quiz_date<?",(club_id,cutoff,target)).fetchall()
  excluded={semantic_family(q) for q in recent}; seen_text={wording(q) for q in recent}
  rows=con.execute("select * from questions where club_id=? and status='reviewed' and semantic_key like 'v4bank|%'",(club_id,)).fetchall()
  excluded.update(semantic_family(q) for q in rows if (q['last_used_date'] or '')>=cutoff)
  return ranked((q for q in rows if semantic_family(q) not in excluded and wording(q) not in seen_text and not lint_question(q)),target)

def wording(q):
  return re.sub(r'\W+',' ',q['question_text'].lower()).strip()

def published_recently(con,club_id,target,pattern):
  cutoff=(dt.date.fromisoformat(target)-dt.timedelta(days=NO_REPEAT_DAYS)).isoformat()
  return con.execute("select 1 from daily_questions d join questions q on q.id=d.question_id where d.club_id=? and d.quiz_date>=? and d.quiz_date<? and q.semantic_key like ? limit 1",(club_id,cutoff,target,pattern)).fetchone() is not None

def generic_bank(con,club_id,target):
  # Track publication as well as play history. Eight facts per club rotate
  # without repeating across the preceding seven calendar days.
  cutoff=(dt.date.fromisoformat(target)-dt.timedelta(days=NO_REPEAT_DAYS)).isoformat()
  published=dict(con.execute("select question_id,max(quiz_date) from daily_questions where club_id=? and quiz_date<? group by question_id",(club_id,target)))
  rows=[q for q in con.execute("select * from questions where club_id=? and status='reviewed' and (semantic_key like 'generic|%' or semantic_key like 'heritage|%')",(club_id,)).fetchall() if not lint_question(q)]
  eligible=[q for q in rows if published.get(q['id'],'') < cutoff and (q['last_used_date'] or '') < cutoff]
  if not eligible:
    # Small trivia pools cannot cover 30 days yet: show the least recently published instead of failing.
    week=(dt.date.fromisoformat(target)-dt.timedelta(days=7)).isoformat()
    eligible=[q for q in rows if published.get(q['id'],'') < week] or rows
  if not eligible:raise RuntimeError('Club trivia pool exhausted for '+str(club_id))
  yesterday=con.execute("select q.semantic_key from daily_questions d join questions q on q.id=d.question_id where d.club_id=? and d.quiz_date=? and q.semantic_key like 'generic|%' limit 1",(club_id,(dt.date.fromisoformat(target)-dt.timedelta(days=1)).isoformat())).fetchone()
  # Fact categories are explicit in the key; alternate origins, identity and grounds.
  previous=yesterday[0].split('|')[2] if yesterday else ''
  return sorted(eligible,key=lambda q:(published.get(q['id'],'')>=cutoff,q['semantic_key'].split('|')[2]==previous,max(published.get(q['id'],''),q['last_used_date'] or ''),hashlib.sha256(f'{target}|{q["id"]}'.encode()).hexdigest()))

def numopts(v,seed,lo=0,hi=None):
  return numeric_options(v,seed,lo,hi)
def scoreopts(a,b,seed):
  pts,idx=score_options(a,b,seed)
  return [f'{x}-{y}' for x,y in pts],idx
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
  selector=int(hashlib.sha256(f'{target}|{club["slug"]}|fresh'.encode()).hexdigest(),16)%2 if selector_override is None else selector_override
  slot=('yellow','score')[selector%2]
  date=latest['_date'].isoformat()
  if used_match_fact(con,club['id'],date,slot):raise FreshUnavailable('Match fact already asked')
  if published_recently(con,club['id'],target,f'matchfact|{club["slug"]}|{date}|%'):raise FreshUnavailable('This match was asked about recently')
  home=latest['HomeTeam']==latest['_alias']; venue='at home to' if home else 'away to'
  if slot in ('yellow','red'):
    field=('HY' if home else 'AY') if slot=='yellow' else ('HR' if home else 'AR')
    if not (latest.get(field) or '').strip():raise FreshUnavailable('Card statistic unavailable')
    val=int(latest[field]);opts,idx=numopts(val,f'{date}|{club["slug"]}|{slot}',0,8)
    text=f"How many {slot} cards did {club['name']} receive in their league match against {opp} on {display_date(date)}?"
    exp=f"{club['name']} received {val} {slot} cards against {opp} on {display_date(date)}."
  else:
    opts,idx=scoreopts(gf,ga,f'{date}|{club["slug"]}|score')
    text=f"What was the score for {club['name']} in their league match {venue} {opp} on {display_date(date)}?"
    exp=f"{club['name']} played {venue} {opp} on {display_date(date)}; the score for {club['name']} was {gf}-{ga}."
  text=clean_text(text,club['name']);exp=clean_text(exp,club['name'])
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
  if published_recently(con,club['id'],target,f'seasonfact|{club["slug"]}|{season}|{slot}|%'):raise FreshUnavailable('Season total asked recently')
  val=values[slot];date=max(r['_date'] for r in rows).isoformat()
  if (dt.date.fromisoformat(target)-dt.date.fromisoformat(date)).days>10:raise FreshUnavailable('No league matches in the last 10 days')
  key=f'seasonfact|{club["slug"]}|{season}|{slot}|{val}'
  existing=con.execute('select id,use_count,fact_date,status from questions where semantic_key=?',(key,)).fetchone()
  if existing:
    # The same aggregate value can recur after later fixtures. Never revive an
    # older snapshot merely because its numeric answer happens to be unchanged.
    if existing['status'] != 'reviewed' or existing['fact_date'] != date or existing['use_count']:
      existing=None
    else:
      return existing['id']
  if existing is None:
    key=f'seasonfact|{club["slug"]}|{season}|{slot}|{val}|through-{date}'
    same=con.execute('select id,use_count from questions where semantic_key=?',(key,)).fetchone()
    if same:
      if same['use_count']:raise FreshUnavailable('Season fact already asked')
      return same['id']
  wording={'wins':'league wins','draws':'league draws','losses':'league losses','goals-scored':'goals scored in the league','goals-conceded':'goals conceded in the league','yellow':'yellow cards in the league','red':'red cards in the league'}[slot]
  text=f"How many {wording} had {club['name']} recorded in {season}, through {display_date(date)}?"
  exp=f"Across their {len(rows)} completed league matches through {display_date(date)}, {club['name']} recorded {val} {wording}."
  opts,answer=numopts(val,key,0,len(rows) if slot in ('wins','draws','losses') else None);payload=json.dumps(opts)
  con.execute('insert into questions(club_id,question_text,options_json,correct_index,explanation,source_url,source_label,content_hash,semantic_key,status,question_kind,fact_date,use_count,last_used_date) values(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(club['id'],text,payload,answer,exp,rows[0]['_url'],'Football-Data.co.uk season records',hashlib.sha256(key.encode()).hexdigest(),key,'reviewed','recent',date,0,None))
  return con.execute('select id from questions where semantic_key=?',(key,)).fetchone()[0]

def choose_round(con,club,target,rows,bank,fixed=None):
  for choice in (None,0,1):
    con.execute('savepoint fresh_choice')
    try:
      qid=insert_fresh(con,club,target,rows,choice)
      fresh=con.execute('select * from questions where id=?',(qid,)).fetchone()
      if lint_question(fresh):raise FreshUnavailable('Fresh question failed quality check: '+', '.join(lint_question(fresh)))
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
      if lint_question(fresh):raise FreshUnavailable('Season question failed quality check')
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
  # New EFL clubs may have sparse current data (or a break in fixtures).
  # Fall back to a sourced, unused bank fact; never invent a current statistic.
  efl_slugs=set()
  if os.path.exists('/var/lib/clubdailyfive/efl-clubs.json'):
    with open('/var/lib/clubdailyfive/efl-clubs.json',encoding='utf-8') as f:
      efl_slugs={m['slug'] for m in json.load(f) if m['league']!='premier-league'}
  if club['slug'] in efl_slugs:
    for candidate in bank:
      if candidate['use_count'] or candidate['semantic_key'].startswith('generic|'):continue
      try:
        selected=list(fixed) if fixed is not None else select_varied(bank,candidate)
        validate_round([*selected,candidate])
      except (RuntimeError,ValueError):continue
      return selected,candidate
  # No new matches (e.g. an international break): a fifth bank question is better than a stale repeat.
  for candidate in bank:
    if candidate['semantic_key'].startswith('generic|') or candidate['semantic_key'].startswith('heritage|'):continue
    try:
      selected=list(fixed) if fixed is not None else select_varied([q for q in bank if q['id']!=candidate['id']],candidate)
      validate_round([*selected,candidate])
    except (RuntimeError,ValueError):continue
    return selected,candidate
  raise RuntimeError(f'{club["slug"]}: no unused match or recent-season fact fits this round')

def main():
  ap=argparse.ArgumentParser(); ap.add_argument('--date'); ap.add_argument('--self-test',action='store_true'); a=ap.parse_args(); target=a.date or (dt.datetime.now(UK).date()+dt.timedelta(days=1)).isoformat()
  con=sqlite3.connect(DB,timeout=60); con.row_factory=sqlite3.Row; con.execute('pragma foreign_keys=on'); clubs=con.execute('select id,slug,name from clubs where active=1 order by name').fetchall()
  if a.self_test:
    counts=dict(con.execute("select c.slug,count(q.id) from clubs c left join questions q on q.club_id=c.id and q.semantic_key like 'v4bank|%' group by c.id")); print(json.dumps({'database':con.execute('pragma integrity_check').fetchone()[0],'clubs':len(clubs),'bank_counts':counts,'bank_per_club_required':300,'daily_mix':'1 club trivia + 3 varied bank + 1 unused match fact or recent-season fallback','recent_cutoff_days':10,'openai_api_required':False})); return
  os.makedirs(BACKUPS,exist_ok=True); backup=f"{BACKUPS}/clubquiz-before-daily-{dt.datetime.now().strftime('%Y%m%d-%H%M%S')}.sqlite"
  with sqlite3.connect(backup) as dest: con.backup(dest)
  con.execute('begin immediate')
  try: tidy=normalise(con,dt.datetime.now(UK).date().isoformat()); con.commit()
  except Exception: con.rollback(); raise
  changed={k:v for k,v in tidy.items() if not k.startswith('still failing') and k!='protected (live round)'}
  print('Bank tidy-up: '+(', '.join(f'{k} {v}' for k,v in changed.items()) or 'nothing to change'))
  if tidy.get('still failing quality check (excluded from rounds)'):print('Questions held back by the quality check: '+', '.join(f'{k} {v}' for k,v in tidy['still failing quality check (excluded from rounds)'].items()))
  complete={r[0] for r in con.execute('select club_id from daily_questions where quiz_date=? group by club_id having count(*)=5',(target,))}
  clubs=[c for c in clubs if c['id'] not in complete]
  if not clubs:
    print(f'Round already published for {target}; preserving player questions'); return
  from sterling import assert_sterling
  for question in con.execute("select question_text,options_json,explanation from questions where status='reviewed'"):
    assert_sterling(dict(question))
  current=load_current(target)
  try:
    con.execute('begin immediate')
    # Season-to-date aggregate questions are snapshots. Retire older snapshots
    # whenever newer completed league data exists for that club.
    for club in clubs:
      rows=current.get(club['slug'],[])
      if not rows: continue
      latest=max(r['_date'] for r in rows).isoformat()
      con.execute("update questions set status='retired' where club_id=? and status='reviewed' and semantic_key like 'seasonfact|%' and (fact_date is null or fact_date < ?)",(club['id'],latest))
    rounds=[]; short_window={}
    for club in clubs:
      con.execute('delete from daily_questions where club_id=? and quiz_date=?',(club['id'],target))
      # Aim for no repeats within 30 days; clubs with small banks fall back to shorter windows (reported).
      for days in (NO_REPEAT_DAYS,21,14,7):
        bank=eligible_history_bank(con,club['id'],target,days)
        bank = generic_bank(con,club['id'],target) + [q for q in bank if not banned_question(q)]
        bank = [q for q in bank if not lint_question(q)]
        if len(bank)<4: continue
        try: selected,fresh=choose_round(con,club,target,current.get(club['slug'],[]),bank); break
        except RuntimeError: continue
      else: raise RuntimeError(f"{club['slug']}: no round fits even with a 7-day repeat window")
      if days<NO_REPEAT_DAYS: short_window[club['slug']]=days
      fresh_id=fresh['id']
      validate_round([*selected,fresh])
      problems=[p for q in [*selected,fresh] for p in lint_question(q)]
      if problems:raise RuntimeError(f"{club['slug']}: round failed quality check: {problems}")
      ids=[r['id'] for r in selected]+[fresh_id]
      random.Random(hashlib.sha256(f'{target}|{club["slug"]}|shuffle'.encode()).digest()).shuffle(ids); rounds.append((club,ids))
    for club,ids in rounds:
      for pos,qid in enumerate(ids,1):
        con.execute('insert into daily_questions(club_id,quiz_date,position,question_id) values(?,?,?,?)',(club['id'],target,pos,qid))
    con.execute("insert into generation_runs(run_date,finished_at,status,notes) values(?,CURRENT_TIMESTAMP,'complete',?)",(target,f'V5: 1 sourced club trivia + 3 varied bank + 1 unused match fact/recent-season fallback; 10-day recent cutoff; backup={backup}')); con.commit()
  except Exception: con.rollback(); raise
  print(f'published {len(clubs)*5} questions for {target}')
  published=[q for q in con.execute('select q.* from daily_questions d join questions q on q.id=d.question_id where d.quiz_date=?',(target,))]
  rep=numeric_rank_report(published); fresh_ages=[]
  for q in published:
    if q['question_kind']=='recent' and q['fact_date']:fresh_ages.append((dt.date.fromisoformat(target)-dt.date.fromisoformat(q['fact_date'])).days)
  print(f"Quality check: {len(published)} questions passed; number-answer positions lowest..highest {rep['answer_rank_share']} across {rep['questions']}; "
        f"{len(fresh_ages)} recent-match questions (oldest {max(fresh_ages) if fresh_ages else 0} days)")
  print(f"Repeat window: {NO_REPEAT_DAYS} days for {len(clubs)-len(short_window)} clubs"+(('; shorter for small banks: '+', '.join(f'{k} {v} days' for k,v in sorted(short_window.items()))) if short_window else ''))
if __name__=='__main__':
  try: main()
  except Exception as e: print(f'quiz publication failed: {e}',file=sys.stderr); raise SystemExit(1)

