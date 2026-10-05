#!/usr/bin/env python3
"""Nightly maintenance. Runtime has no ChatGPT/OpenAI dependency.
Imports validated player rows from /etc/clubdailyfive/player-wordle-players.csv when present.
The collector boundary is intentionally separate so a permitted football-data source can be swapped without changing the game.
"""
import csv, sqlite3, os, datetime, random
from zoneinfo import ZoneInfo
DB="/var/lib/clubdailyfive/player-wordle/game.sqlite3"
CSV="/etc/clubdailyfive/player-wordle-players.csv"
TZ=ZoneInfo("Europe/London")
RANK={"Goalkeeper":0,"Defender":1,"Midfielder":2,"Forward":3,"Striker":3}
CONT={"England":"Europe","Scotland":"Europe","Wales":"Europe","Northern Ireland":"Europe","Republic of Ireland":"Europe",
"France":"Europe","Spain":"Europe","Germany":"Europe","Italy":"Europe","Portugal":"Europe","Netherlands":"Europe","Belgium":"Europe",
"Norway":"Europe","Sweden":"Europe","Denmark":"Europe","Poland":"Europe","Croatia":"Europe","Serbia":"Europe","Switzerland":"Europe",
"Brazil":"South America","Argentina":"South America","Uruguay":"South America","Colombia":"South America","Ecuador":"South America",
"USA":"North America","United States":"North America","Canada":"North America","Mexico":"North America",
"Japan":"Asia","South Korea":"Asia","Australia":"Oceania","New Zealand":"Oceania","Ghana":"Africa","Nigeria":"Africa","Senegal":"Africa",
"Morocco":"Africa","Algeria":"Africa","Egypt":"Africa","Cameroon":"Africa","Ivory Coast":"Africa","Côte d'Ivoire":"Africa"}
def main():
    con=sqlite3.connect(DB); now=datetime.datetime.now(TZ)
    added=0; updated=0
    if os.path.exists(CSV):
      clubs={s:i for i,s in con.execute("SELECT id,slug FROM clubs")}
      with open(CSV,encoding="utf-8-sig",newline="") as f:
       for r in csv.DictReader(f):
        cid=clubs.get(r["club_slug"].strip())
        if not cid: continue
        pos=r["position"].strip(); nat=r["nationality"].strip()
        if pos not in RANK: continue
        vals=(cid,r["name"].strip(),int(r["debut_age"]),int(r["debut_year"]),pos,RANK[pos],nat,r.get("continent","").strip() or CONT.get(nat,"Other"),
              int(r["appearances"]),int(r["prior_clubs"]),r.get("source_url",""),now.isoformat())
        before=con.total_changes
        con.execute("""INSERT INTO players(club_id,name,debut_age,debut_year,position,position_rank,nationality,continent,appearances,prior_clubs,source_url,source_updated_at)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(club_id,name) DO UPDATE SET debut_age=excluded.debut_age,debut_year=excluded.debut_year,position=excluded.position,
        position_rank=excluded.position_rank,nationality=excluded.nationality,continent=excluded.continent,appearances=excluded.appearances,
        prior_clubs=excluded.prior_clubs,source_url=excluded.source_url,source_updated_at=excluded.source_updated_at""",vals)
        added += con.total_changes-before
    # Fill missing games per club while preserving every already selected player.
    today=now.date().isoformat()
    tomorrow=(now.date()+datetime.timedelta(days=1)).isoformat()
    for cid,slug in con.execute("SELECT id,slug FROM clubs WHERE active=1").fetchall():
      ids=[x[0] for x in con.execute("SELECT id FROM players WHERE club_id=?",(cid,))]
      # New clubs need enough verified players to avoid an immediate repeat loop.
      new_club=con.execute("SELECT count(*) FROM efl_player_research WHERE club_id=?",(cid,)).fetchone()[0] if con.execute("SELECT count(*) FROM sqlite_master WHERE name='efl_player_research'").fetchone()[0] else 0
      if not ids or (new_club and len(ids)<10): continue
      for day in (today,tomorrow):
        if con.execute("SELECT 1 FROM daily_game WHERE game_date=? AND club_id=?",(day,cid)).fetchone():continue
        used=dict(con.execute("SELECT player_id,max(game_date) FROM daily_game WHERE club_id=? AND game_date<? GROUP BY player_id",(cid,day)))
        oldest=min(used.get(pid,"") for pid in ids)
        pool=[pid for pid in ids if used.get(pid,"")==oldest]
        con.execute("INSERT OR IGNORE INTO daily_game(game_date,club_id,player_id) VALUES(?,?,?)",(day,cid,random.choice(pool)))
    day=tomorrow
    con.execute("INSERT INTO agent_runs(ran_at,status,details) VALUES(?,?,?)",(now.isoformat(),"ok",f"player rows processed={added}"))
    con.commit(); print("nightly complete",day,"rows",added)
if __name__=="__main__": main()

