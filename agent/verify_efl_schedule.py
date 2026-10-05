#!/usr/bin/env python3
"""Frozen-fixture simulation in memory; never writes the source database."""
import sys,sqlite3,datetime as dt,time
from zoneinfo import ZoneInfo
import os
import generate_questions as g
from question_variety import banned_question,validate_round
c=sqlite3.connect(':memory:');src=sqlite3.connect(os.getenv('QUIZ_DB','/var/lib/clubdailyfive/clubquiz.sqlite'));src.backup(c);src.close();c.row_factory=sqlite3.Row
today=dt.datetime.now(ZoneInfo('Europe/London')).date();current=g.load_current(today.isoformat());clubs=c.execute("select id,slug,name from clubs where league!='premier-league'").fetchall();started=time.monotonic()
for day in range(30):
 date=(today+dt.timedelta(days=day)).isoformat()
 for club in clubs:
  bank=g.generic_bank(c,club['id'],date)+[q for q in g.eligible_history_bank(c,club['id'],date) if not banned_question(q)]
  chosen,fresh=g.choose_round(c,club,date,current.get(club['slug'],[]),bank);qs=[*chosen,fresh];validate_round(qs)
  c.execute('delete from daily_questions where club_id=? and quiz_date=?',(club['id'],date))
  for pos,q in enumerate(qs,1):
   c.execute('insert into daily_questions values(?,?,?,?)',(club['id'],date,pos,q['id']))
   c.execute('update questions set use_count=use_count+1,last_used_date=? where id=?',(date,q['id']))
 c.commit();print('DAY',day+1,f'{len(clubs)} rounds valid',round(time.monotonic()-started,1),flush=True)
print(f'PASS {30*len(clubs)} rounds, {150*len(clubs)} slots; no repeated recent facts, distinct topics')