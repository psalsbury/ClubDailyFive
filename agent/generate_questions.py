#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,datetime as dt,hashlib,io,json,os,random,sqlite3,sys,urllib.request
from zoneinfo import ZoneInfo
from question_variety import select_varied, validate_round
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
def insert_fresh(con,club,target,rows,selector_override=None):
  rows=sorted(rows,key=lambda r:r['_date'],reverse=True)
  if not rows: raise RuntimeError(f'No current-season completed matches for {club["name"]}')
  latest=rows[0]; gf,ga,opp,yellow,red=persp(latest); home=latest['HomeTeam']==latest['_alias']; venue=('at home to' if home else 'away to'); age=(dt.date.fromisoformat(target)-latest['_date']).days
  selector=int(hashlib.sha256(f'{target}|{club["slug"]}|fresh'.encode()).hexdigest(),16)%4
  if selector_override is not None: selector=selector_override
  if 0<=age<=7 or selector in (0,1):
    if selector==0:
      val=yellow; opts,idx=numopts(val,f'{target}|{club["slug"]}|yellow'); text=f"How many yellow cards did {club['name']} receive in their most recent league match against {opp}?"; exp=f"{club['name']} received {val} yellow cards in that match."; slot='recent-yellow'
    elif selector==1:
      val=red; opts,idx=numopts(val,f'{target}|{club["slug"]}|red'); text=f"How many red cards did {club['name']} receive in their most recent league match against {opp}?"; exp=f"{club['name']} received {val} red cards in that match."; slot='recent-red'
    else:
      opts,idx=scoreopts(gf,ga,f'{target}|{club["slug"]}|score'); val=f'{gf}-{ga}'; text=f"What was the score for {club['name']} in their most recent league match {venue} {opp}?"; exp=f"{club['name']} played {venue} {opp}; the score for {club['name']} was {val}."; slot='recent-score'
  else:
    opts,idx=scoreopts(gf,ga,f'{target}|{club["slug"]}|season-score'); val=f'{gf}-{ga}'; text=f"What was the score for {club['name']} in their latest completed league match this season, played {venue} {opp}?"; exp=f"{club['name']} played {venue} {opp}; the score for {club['name']} was {val}."; slot='season-score'
  if age>7:
    text=text.replace('most recent league match', 'latest completed league match this season')
  key=f'dailyfresh|{target}|{club["slug"]}|{slot}'; payload=json.dumps(opts,ensure_ascii=False); ch=hashlib.sha256((text+'|'+key).encode()).hexdigest()
  con.execute('delete from daily_questions where question_id in (select id from questions where semantic_key=?)',(key,)); con.execute('delete from questions where semantic_key=?',(key,))
  con.execute('insert into questions(club_id,question_text,options_json,correct_index,explanation,source_url,source_label,content_hash,semantic_key,status,question_kind,fact_date,use_count,last_used_date) values(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(club['id'],text,payload,idx,exp,latest['_url'],'Football-Data.co.uk current-season records',ch,key,'reviewed','recent',latest['_date'].isoformat(),0,None))
  return con.execute('select id from questions where semantic_key=?',(key,)).fetchone()[0]
def main():
  ap=argparse.ArgumentParser(); ap.add_argument('--date'); ap.add_argument('--self-test',action='store_true'); a=ap.parse_args(); target=a.date or (dt.datetime.now(UK).date()+dt.timedelta(days=1)).isoformat()
  con=sqlite3.connect(DB,timeout=60); con.row_factory=sqlite3.Row; con.execute('pragma foreign_keys=on'); clubs=con.execute('select id,slug,name from clubs where active=1 order by name').fetchall()
  if a.self_test:
    counts=dict(con.execute("select c.slug,count(q.id) from clubs c left join questions q on q.club_id=c.id and q.semantic_key like 'v4bank|%' group by c.id")); print(json.dumps({'database':con.execute('pragma integrity_check').fetchone()[0],'clubs':len(clubs),'bank_counts':counts,'bank_per_club_required':300,'daily_mix':'4 V4 bank + 1 fresh','recent_cutoff_days':7,'openai_api_required':False})); return
  from sterling import assert_sterling
  for question in con.execute("select question_text,options_json,explanation from questions where status='reviewed'"):
    assert_sterling(dict(question))
  current=load_current(target); os.makedirs(BACKUPS,exist_ok=True); backup=f"{BACKUPS}/clubquiz-before-daily-{dt.datetime.now().strftime('%Y%m%d-%H%M%S')}.sqlite"
  with sqlite3.connect(backup) as dest: con.backup(dest)
  try:
    con.execute('begin immediate'); con.execute('delete from daily_questions where quiz_date=?',(target,)); rounds=[]
    for club in clubs:
      bank=ranked(con.execute("select id,use_count,last_used_date,semantic_key,question_text from questions where club_id=? and status='reviewed' and semantic_key like 'v4bank|%'",(club['id'],)).fetchall(),target)
      if len(bank)!=300: raise RuntimeError(f"{club['slug']} has {len(bank)} V4 bank questions, expected 300")
      for choice in (None,0,1,2):
        con.execute("savepoint fresh_choice")
        fresh_id=insert_fresh(con,club,target,current.get(club['slug'],[]),choice)
        fresh=con.execute("select * from questions where id=?",(fresh_id,)).fetchone()
        try:
          selected=select_varied(bank,fresh)
        except RuntimeError:
          con.execute("rollback to fresh_choice")
          con.execute("release fresh_choice")
          continue
        con.execute("release fresh_choice")
        break
      else: raise RuntimeError(f"{club['slug']}: cannot build five different question types")
      validate_round([*selected,fresh])
      ids=[r['id'] for r in selected]+[fresh_id]
      random.Random(hashlib.sha256(f'{target}|{club["slug"]}|shuffle'.encode()).digest()).shuffle(ids); rounds.append((club,ids))
    for club,ids in rounds:
      for pos,qid in enumerate(ids,1):
        con.execute('insert into daily_questions(club_id,quiz_date,position,question_id) values(?,?,?,?)',(club['id'],target,pos,qid)); con.execute('update questions set use_count=use_count+1,last_used_date=? where id=?',(target,qid))
    con.execute("insert into generation_runs(run_date,finished_at,status,notes) values(?,CURRENT_TIMESTAMP,'complete',?)",(target,f'V4: 4/300 least-recently-used bank + 1 fresh/current-season question; 7-day recent cutoff; backup={backup}')); con.commit()
  except Exception: con.rollback(); raise
  print(f'published {len(clubs)*5} questions for {target}')
if __name__=='__main__':
  try: main()
  except Exception as e: print(f'quiz publication failed: {e}',file=sys.stderr); raise SystemExit(1)
