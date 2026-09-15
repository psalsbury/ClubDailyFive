#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import gzip
import hashlib
import io
import json
import os
import random
import re
import sqlite3
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path

DB = os.getenv("QUIZ_DB", "/var/lib/clubdailyfive/clubquiz.sqlite")
TM_DIR = Path(os.getenv("TM_DATA_DIR", "/var/lib/clubdailyfive/transfermarkt-data"))
BACKUPS = Path("/var/backups/predictioncomp-question-db")
TARGET = 300
DATASET_URL = "https://github.com/dcaribou/transfermarkt-datasets"
TM_IDS = {"arsenal":11,"aston-villa":405,"bournemouth":989,"brentford":1148,"brighton":1237,"chelsea":631,"coventry-city":990,"crystal-palace":873,"everton":29,"fulham":931,"hull-city":3008,"ipswich-town":677,"leeds-united":399,"liverpool":31,"manchester-city":281,"manchester-united":985,"newcastle-united":762,"nottingham-forest":703,"sunderland":289,"tottenham-hotspur":148}
FD_ALIASES = {"Arsenal":"arsenal","Aston Villa":"aston-villa","Bournemouth":"bournemouth","Brentford":"brentford","Brighton":"brighton","Chelsea":"chelsea","Coventry":"coventry-city","Crystal Palace":"crystal-palace","Everton":"everton","Fulham":"fulham","Hull":"hull-city","Ipswich":"ipswich-town","Leeds":"leeds-united","Liverpool":"liverpool","Man City":"manchester-city","Man United":"manchester-united","Newcastle":"newcastle-united","Nott'm Forest":"nottingham-forest","Sunderland":"sunderland","Tottenham":"tottenham-hotspur"}
FD_DIVS=("E0","E1","E2","E3")
COMP_NAMES={"FAC":"FA Cup","EFL":"EFL Cup","LC":"EFL Cup","CL":"UEFA Champions League","EL":"UEFA Europa League","UCOL":"UEFA Conference League","GBCS":"Community Shield"}

def norm(s): return " ".join(re.sub(r"[^a-z0-9]+"," ",(s or "").lower()).split())
def hsh(s): return hashlib.sha256(s.encode("utf-8")).hexdigest()
def rng(seed): return random.Random(hashlib.sha256(seed.encode()).digest())
def season_label(y): return f"{y}-{str(y+1)[-2:]}"
def fd_code(y): return f"{str(y)[-2:]}{str(y+1)[-2:]}"
def parse_fd_date(v):
    for fmt in ("%d/%m/%Y","%d/%m/%y"):
        try:return dt.datetime.strptime(v.strip(),fmt).date()
        except ValueError:pass
    return None

def load_gz(name):
    with gzip.open(TM_DIR/f"{name}.csv.gz","rt",encoding="utf-8-sig",errors="replace",newline="") as f:return list(csv.DictReader(f))

def fetch_fd_season(y):
    out={slug:[] for slug in TM_IDS}
    for div in FD_DIVS:
        url=f"https://www.football-data.co.uk/mmz4281/{fd_code(y)}/{div}.csv"
        try:
            req=urllib.request.Request(url,headers={"User-Agent":"ClubDailyFive/3.0"}); raw=urllib.request.urlopen(req,timeout=30).read().decode("utf-8-sig","replace")
        except Exception:continue
        for row in csv.DictReader(io.StringIO(raw)):
            if not all((row.get(k) or "").strip() for k in ("Date","HomeTeam","AwayTeam","FTHG","FTAG")):continue
            d=parse_fd_date(row["Date"])
            if not d:continue
            for team in (row["HomeTeam"],row["AwayTeam"]):
                slug=FD_ALIASES.get(team)
                if slug:
                    r=dict(row); r["_date"]=d.isoformat(); r["_alias"]=team; r["_url"]=url; r["_season"]=season_label(y); out[slug].append(r)
    return out

def fd_view(r):
    home=r["HomeTeam"]==r["_alias"]; hg,ag=int(r["FTHG"]),int(r["FTAG"]); gf,ga=(hg,ag) if home else (ag,hg); opp=r["AwayTeam"] if home else r["HomeTeam"]; result="W" if gf>ga else "D" if gf==ga else "L"
    return {"home":home,"gf":gf,"ga":ga,"hg":hg,"ag":ag,"opp":opp,"result":result}

def unique_options(correct,pool,seed):
    correct=str(correct); vals=[]; seen={correct.casefold()}
    for v in pool:
        s=str(v)
        if s.casefold() not in seen:vals.append(s);seen.add(s.casefold())
    rng(seed).shuffle(vals); opts=[correct]+vals[:3]
    if len(opts)<4:return None
    rng(seed+"|shuffle").shuffle(opts); return opts

def money(v):
    if v>=1_000_000:return f"€{v/1_000_000:.1f}m"
    if v>=1_000:return f"€{v/1_000:.0f}k"
    return f"€{v:.0f}"

class Builder:
    def __init__(self,club,tm,fd):
        self.club=club; self.slug=club["slug"]; self.name=club["name"]; self.cid=TM_IDS[self.slug]; self.tm=tm; self.fd=fd; self.q=[]; self.keys=set()
        self.games=[r for r in tm["games"] if str(self.cid) in (r.get("home_club_id"),r.get("away_club_id"))]; self.games_by_id={r["game_id"]:r for r in self.games}
        self.appearances=[r for r in tm["appearances"] if r.get("player_club_id")==str(self.cid)]; self.events=[r for r in tm["game_events"] if r.get("game_id") in self.games_by_id]
        self.transfers=[r for r in tm["transfers"] if str(self.cid) in (r.get("from_club_id"),r.get("to_club_id"))]
    def add(self,category,key,text,correct,pool,explanation,source_url,fact_date=None):
        semantic=f"v3bank|{self.slug}|{category}|{key}"
        if semantic in self.keys:return
        opts=unique_options(str(correct),pool,semantic)
        if not opts or len(set(x.casefold() for x in opts))!=4:return
        from sterling import sterling_question
        from display_dates import format_question
        self.keys.add(semantic); self.q.append({"question_text":text,"options_json":json.dumps(opts,ensure_ascii=False),"correct_index":opts.index(str(correct)),"explanation":explanation,"source_url":source_url,"source_label":"Transfermarkt open dataset" if "transfermarkt" in source_url.lower() or source_url==DATASET_URL else "Football-Data.co.uk","content_hash":hsh(semantic+"|"+text),"semantic_key":semantic,"status":"reviewed","question_kind":category,"fact_date":fact_date})
        self.q[-1] = format_question(sterling_question(self.q[-1]))
    def fd_last3(self):
        for y in (2023,2024,2025):
            rows=sorted(self.fd[y].get(self.slug,[]),key=lambda r:r["_date"])
            if not rows:continue
            season=season_label(y); highs=[r for r in rows if int(r["FTHG"])+int(r["FTAG"])>=6]; opponents=[fd_view(r)["opp"] for r in rows]; months=[dt.date.fromisoformat(r["_date"]).strftime("%B") for r in rows]
            for r in highs:
                v=fd_view(r); d=dt.date.fromisoformat(r["_date"]); venue="at home to" if v["home"] else "away to"; score=f"{r['HomeTeam']} {r['FTHG']}-{r['FTAG']} {r['AwayTeam']}"; base=f"{season}|{r['_date']}|{norm(str(v['opp']))}"
                self.add("high_scoring",base+"|month",f"In which month was {self.name}'s high-scoring {season} league match {venue} {v['opp']}, which finished {score}?",d.strftime("%B"),months,f"The match was played in {d.strftime('%B')} and finished {score}.",r["_url"],r["_date"])
                total=int(r["FTHG"])+int(r["FTAG"]); self.add("high_scoring",base+"|total",f"How many goals in total were scored in {self.name}'s high-scoring {season} league match {venue} {v['opp']}?",total,[total-1,total+1,total+2,total+3],f"There were {total} goals; the match finished {score}.",r["_url"],r["_date"])
                self.add("high_scoring",base+"|clubgoals",f"How many goals did {self.name} score in their high-scoring {season} league match {venue} {v['opp']}?",v["gf"],[max(0,int(v['gf'])-1),int(v['gf'])+1,int(v['gf'])+2,int(v['ga'])],f"{self.name} scored {v['gf']}; the match finished {score}.",r["_url"],r["_date"])
                hg,ag=int(r['FTHG']),int(r['FTAG']); score_pool=[f"{r['HomeTeam']} {a}-{b} {r['AwayTeam']}" for a,b in ((hg+1,ag),(hg,ag+1),(max(0,hg-1),ag),(hg,max(0,ag-1)),(ag,hg))]
                self.add("high_scoring",base+"|score",f"What was the final score in {self.name}'s high-scoring {season} league match {venue} {v['opp']}?",score,score_pool,f"The match finished {score}.",r["_url"],r["_date"])
                self.add("high_scoring",base+"|opp",f"Who did {self.name} play in the high-scoring {season} league match on {d.day} {d.strftime('%B')} {d.year} that finished {score}?",v["opp"],opponents,f"The opponents were {v['opp']}; the match finished {score}.",r["_url"],r["_date"])
            results=[fd_view(r)["result"] for r in rows]
            for typ,code,label in (("win","W","winning"),("draw","D","drawing"),("loss","L","losing")):
                best_start=best_len=cur_start=cur_len=0
                for i,res in enumerate(results):
                    if res==code:
                        if cur_len==0:cur_start=i
                        cur_len+=1
                        if cur_len>best_len:best_start,best_len=cur_start,cur_len
                    else:cur_len=0
                if best_len<=0 or (typ=="win" and best_len<=3):continue
                self.add(f"{typ}_run",f"{season}|length",f"What was {self.name}'s longest continuous {label} run in league matches during {season}?",best_len,[max(1,best_len-2),max(1,best_len-1),best_len+1,best_len+2],f"Their longest continuous {label} run was {best_len} matches.",rows[best_start]["_url"],rows[best_start+best_len-1]["_date"])
                if typ in ("win","loss") and best_len>3:
                    j=best_start+best_len
                    if j<len(rows):
                        breaker=fd_view(rows[j])["opp"]; self.add(f"{typ}_run",f"{season}|breaker",f"Which team ended {self.name}'s longest continuous {label} league run of {season}, a run of {best_len} matches?",breaker,opponents,f"{breaker} ended that {best_len}-match {label} run.",rows[j]["_url"],rows[j]["_date"])
    def managers(self):
        for y in range(2016,2026):
            gs=[g for g in self.games if g.get("season")==str(y) and g.get("competition_id")=="GB1"]
            if not gs:continue
            g=min(gs,key=lambda x:x["date"]); manager=g["home_club_manager_name"] if g["home_club_id"]==str(self.cid) else g["away_club_manager_name"]
            if not manager:continue
            pool=[]
            for h in self.games:
                if h.get("competition_id")!="GB1":continue
                m=h["home_club_manager_name"] if h["home_club_id"]==str(self.cid) else h["away_club_manager_name"]
                if m:pool.append(m)
            self.add("manager_start",str(y),f"Who was {self.name}'s manager at the start of the {season_label(y)} season?",manager,pool,f"{manager} was in charge for {self.name}'s opening Premier League fixture of {season_label(y)}.",g["url"],g["date"])
    def player_season_stats(self):
        for y in range(2021,2026):
            start,end=dt.date(y,7,1),dt.date(y+1,6,30); apps=[a for a in self.appearances if a.get("date") and start<=dt.date.fromisoformat(a["date"])<=end]; game_ids={a["game_id"] for a in apps}
            if len(game_ids)<20:continue
            goals=Counter(); yellow=Counter(); red=Counter()
            for a in apps:
                p=a["player_name"]; goals[p]+=int(a.get("goals") or 0); yellow[p]+=int(a.get("yellow_cards") or 0); red[p]+=int(a.get("red_cards") or 0)
            scored=sorted([(p,n) for p,n in goals.items() if n>0],key=lambda x:(-x[1],x[0])); season=season_label(y)
            if scored:
                pool=[p for p,_ in scored]; top=scored[0]; self.add("top_scorer",str(y),f"Who was {self.name}'s top goalscorer in {season}?",top[0],pool,f"{top[0]} scored {top[1]} goals in the tracked competitive matches that season.",DATASET_URL,f"{y+1}-06-30")
                if len(scored)>1:
                    second=scored[1]; self.add("second_scorer",str(y),f"Who was {self.name}'s second-highest goalscorer in {season}?",second[0],pool,f"{second[0]} was second with {second[1]} goals in the tracked competitive matches.",DATASET_URL,f"{y+1}-06-30")
            for cat,counter,label in (("yellow_cards",yellow,"yellow-carded"),("red_cards",red,"red-carded")):
                vals=sorted([(p,n) for p,n in counter.items() if n>0],key=lambda x:(-x[1],x[0]))
                if vals:
                    top=vals[0]; self.add(cat,str(y),f"Who was {self.name}'s most {label} player in {season}?",top[0],[p for p,_ in vals],f"{top[0]} had {top[1]} {'yellow cards' if cat=='yellow_cards' else 'red cards'} in the tracked matches.",DATASET_URL,f"{y+1}-06-30")
    def transfer_questions(self):
        for y in range(2021,2026):
            season=f"{str(y)[-2:]}/{str(y+1)[-2:]}"; rows=[r for r in self.transfers if r.get("transfer_season")==season and float(r.get("transfer_fee") or 0)>0]; incoming=[r for r in rows if r.get("to_club_id")==str(self.cid)]; outgoing=[r for r in rows if r.get("from_club_id")==str(self.cid)]; all_players=[r["player_name"] for r in rows]; fee_pool=[money(float(r["transfer_fee"])) for r in rows]
            for direction,arr in (("in",incoming),("out",outgoing)):
                if not arr:continue
                top=max(arr,key=lambda r:float(r.get("transfer_fee") or 0)); fee=float(top["transfer_fee"]); word="incoming" if direction=="in" else "outgoing"
                self.add("largest_transfer",f"{y}|{direction}|player",f"Which player commanded {self.name}'s largest {word} transfer fee in {season}?",top["player_name"],all_players,f"{top['player_name']} was the largest {word} fee in {season}, at {money(fee)}.",DATASET_URL,top["transfer_date"])
                self.add("largest_transfer",f"{y}|{direction}|fee",f"What was the transfer fee for {top['player_name']}, {self.name}'s largest {word} transfer of {season}?",money(fee),fee_pool,f"The recorded fee was {money(fee)}.",DATASET_URL,top["transfer_date"])
    def attendance(self):
        for y in range(2021,2026):
            gs=[g for g in self.games if g.get("season")==str(y) and g.get("competition_id")=="GB1" and g.get("home_club_id")==str(self.cid) and (g.get("attendance") or "").isdigit()]
            if len(gs)<15:continue
            hi=max(gs,key=lambda g:int(g["attendance"])); lo=min(gs,key=lambda g:int(g["attendance"])); season=season_label(y); opp_pool=[g["away_club_name"] for g in gs]; att_pool=[g["attendance"] for g in gs]
            for tag,g,word in (("highest",hi,"highest"),("lowest",lo,"lowest")):
                self.add("attendance",f"{y}|{tag}|number",f"What was {self.name}'s {word} home league attendance in {season}?",g["attendance"],att_pool,f"The {word} home league attendance was {int(g['attendance']):,}, against {g['away_club_name']}.",g["url"],g["date"])
                self.add("attendance",f"{y}|{tag}|opponent",f"Who did {self.name} play when they recorded their {word} home league attendance of {season}?",g["away_club_name"],opp_pool,f"They played {g['away_club_name']}; the attendance was {int(g['attendance']):,}.",g["url"],g["date"])
    def cups(self):
        for y in range(2022,2026):
            for comp_id,comp_name in COMP_NAMES.items():
                gs=[g for g in self.games if g.get("season")==str(y) and g.get("competition_id")==comp_id]
                if not gs:continue
                gs.sort(key=lambda g:g["date"]); last=gs[-1]; rounds=[g["round"] for g in self.games if g.get("competition_id")==comp_id and g.get("season")==str(y) and g.get("round")]
                self.add("cup_progress",f"{y}|{comp_id}|round",f"How far did {self.name} get in the {comp_name} in {season_label(y)}?",last["round"],rounds,f"Their last recorded match in that competition was in the {last['round']}.",last["url"],last["date"])
                home=last["home_club_id"]==str(self.cid); gf=int(last["home_club_goals"] if home else last["away_club_goals"]); ga=int(last["away_club_goals"] if home else last["home_club_goals"]); opp=last["away_club_name"] if home else last["home_club_name"]
                if gf<ga:
                    opp_pool=[g["away_club_name"] if g["home_club_id"]==str(self.cid) else g["home_club_name"] for g in gs]; self.add("cup_knockout",f"{y}|{comp_id}|opponent",f"Which team knocked {self.name} out of the {comp_name} in {season_label(y)}?",opp,opp_pool,f"{opp} knocked {self.name} out; the match finished {last['home_club_name']} {last['home_club_goals']}-{last['away_club_goals']} {last['away_club_name']}.",last["url"],last["date"])
                    correct=f"{last['home_club_name']} {last['home_club_goals']}-{last['away_club_goals']} {last['away_club_name']}"; h,a=int(last['home_club_goals']),int(last['away_club_goals']); score_pool=[f"{last['home_club_name']} {x}-{z} {last['away_club_name']}" for x,z in ((h+1,a),(h,a+1),(max(0,h-1),a),(h,max(0,a-1)))]; venue="at home" if home else "away"
                    self.add("cup_knockout",f"{y}|{comp_id}|score",f"What was the score when {self.name} were knocked out of the {comp_name} by {opp} in {season_label(y)}, with {self.name} playing {venue}?",correct,score_pool,f"The match finished {correct}.",last["url"],last["date"])
    def hattricks_and_reds(self):
        by_game=defaultdict(list)
        for a in self.appearances:by_game[a["game_id"]].append(a)
        for y in (2023,2024,2025):
            for gid,apps in by_game.items():
                g=self.games_by_id.get(gid)
                if not g or g.get("season")!=str(y):continue
                for a in [x for x in apps if int(x.get("goals") or 0)>=3]:
                    score=f"{g['home_club_name']} {g['home_club_goals']}-{g['away_club_goals']} {g['away_club_name']}"; self.add("hattrick",f"{gid}|{a['player_id']}",f"Which {self.name} player scored a hat-trick in the {season_label(y)} match {score}?",a["player_name"],[x["player_name"] for x in apps],f"{a['player_name']} scored at least three goals in that match, which finished {score}.",g["url"],g["date"])
        for y in (2024,2025):
            for gid,apps in by_game.items():
                g=self.games_by_id.get(gid)
                if not g or g.get("season")!=str(y):continue
                for a in [x for x in apps if int(x.get("red_cards") or 0)>0]:
                    home=g["home_club_id"]==str(self.cid); opp=g["away_club_name"] if home else g["home_club_name"]; score=f"{g['home_club_name']} {g['home_club_goals']}-{g['away_club_goals']} {g['away_club_name']}"; self.add("sent_off",f"{gid}|{a['player_id']}",f"Which {self.name} player was sent off in their {season_label(y)} match against {opp}, which finished {score}?",a["player_name"],[x["player_name"] for x in apps],f"{a['player_name']} received a red card in that match.",g["url"],g["date"])
    def significant_match_events(self):
        ev_by_game=defaultdict(list)
        for e in self.events:
            if e.get("type")=="Goals" and (e.get("minute") or "").isdigit():ev_by_game[e["game_id"]].append(e)
        for y in (2023,2024,2025):
            league=sorted([g for g in self.games if g.get("season")==str(y) and g.get("competition_id")=="GB1"],key=lambda g:g["date"]); sig=[]
            if league:sig.extend([("first league game",league[0]),("last league game",league[-1])])
            sig.extend((COMP_NAMES.get(g["competition_id"], g["competition_id"])+" "+g["round"].lower(),g) for g in self.games if g.get("season")==str(y) and g.get("competition_id") in ("FAC","CL","EL","UCOL") and any(x in (g.get("round") or "").lower() for x in ("semi","final")))
            for label,g in sig:
                events=sorted(ev_by_game.get(g["game_id"],[]),key=lambda e:int(e["minute"]))
                if not events:continue
                first=events[0]; scoring=first["club_name"]; minute=int(first["minute"]); half="first half" if minute<=45 else "second half"; teams=[g["home_club_name"],g["away_club_name"],"Neither team","Both teams simultaneously"]; score=f"{g['home_club_name']} {g['home_club_goals']}-{g['away_club_goals']} {g['away_club_name']}"
                self.add("significant_first_goal",f"{g['game_id']}|half",f"In which half was the first goal scored in {self.name}'s {label} of {season_label(y)}, which finished {score}?",half,["first half","second half","extra time","no goals were scored"],f"The first goal was scored in minute {minute}, in the {half}.",g["url"],g["date"])
    def build(self):
        self.fd_last3(); self.managers(); self.player_season_stats(); self.transfer_questions(); self.attendance(); self.cups(); self.hattricks_and_reds(); self.significant_match_events(); self.q.sort(key=lambda q:(q["question_kind"],q["semantic_key"])); return self.q

def load_all_tm():
    active_ids={str(v) for v in TM_IDS.values()}
    games=load_gz("games")
    # Keep only games involving one of the 20 active ClubDailyFive clubs.
    games=[g for g in games if g.get("home_club_id") in active_ids or g.get("away_club_id") in active_ids]
    # Only the five transfer seasons requested by the specification are needed.
    wanted_transfer_seasons={f"{str(y)[-2:]}/{str(y+1)[-2:]}" for y in range(2021,2026)}
    transfers=[]
    with gzip.open(TM_DIR/"transfers.csv.gz","rt",encoding="utf-8-sig",errors="replace",newline="") as f:
        for r in csv.DictReader(f):
            if r.get("transfer_season") in wanted_transfer_seasons and (r.get("from_club_id") in active_ids or r.get("to_club_id") in active_ids):transfers.append(r)
    # Player season categories only need Jul-2021 through Jun-2026.
    appearances=[]
    with gzip.open(TM_DIR/"appearances.csv.gz","rt",encoding="utf-8-sig",errors="replace",newline="") as f:
        for r in csv.DictReader(f):
            if r.get("player_club_id") not in active_ids:continue
            d=r.get("date") or ""
            if "2021-07-01"<=d<="2026-06-30":appearances.append(r)
    # Goal-event questions only need significant matches from the last three seasons.
    sig_game_ids=set()
    for g in games:
        if g.get("season") not in {"2023","2024","2025"}:continue
        if g.get("competition_id")=="GB1":
            sig_game_ids.add(g["game_id"])
        elif g.get("competition_id") in {"FAC","CL","EL","UCOL"} and any(x in (g.get("round") or "").lower() for x in ("semi","final")):
            sig_game_ids.add(g["game_id"])
    events=[]
    with gzip.open(TM_DIR/"game_events.csv.gz","rt",encoding="utf-8-sig",errors="replace",newline="") as f:
        for r in csv.DictReader(f):
            if r.get("game_id") in sig_game_ids and r.get("type")=="Goals":events.append(r)
    return {"games":games,"appearances":appearances,"game_events":events,"transfers":transfers}
def install(con,built,force_underfilled=False):
    under={cid:len(qs) for cid,qs in built.items() if len(qs)<TARGET}
    if under and not force_underfilled:raise RuntimeError(f"Refusing install: clubs under {TARGET}: {under}")
    BACKUPS.mkdir(parents=True,exist_ok=True); backup=BACKUPS/f"clubquiz-before-v3-{dt.datetime.now().strftime('%Y%m%d-%H%M%S')}.sqlite"; dest=sqlite3.connect(backup); con.backup(dest); dest.close(); con.execute("BEGIN IMMEDIATE")
    try:
        con.execute("DELETE FROM daily_questions"); con.execute("DELETE FROM questions"); sql="INSERT INTO questions(club_id,question_text,options_json,correct_index,explanation,source_url,source_label,content_hash,semantic_key,status,question_kind,fact_date,use_count,last_used_date) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,0,NULL)"
        for cid,qs in built.items():
            for q in qs[:TARGET]:con.execute(sql,(cid,q["question_text"],q["options_json"],q["correct_index"],q["explanation"],q["source_url"],q["source_label"],q["content_hash"],q["semantic_key"],q["status"],q["question_kind"],q["fact_date"]))
        con.commit()
    except Exception:con.rollback();raise
    return str(backup)
def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--install",action="store_true"); ap.add_argument("--force-underfilled",action="store_true"); ap.add_argument("--club"); args=ap.parse_args(); con=sqlite3.connect(DB,timeout=60); con.row_factory=sqlite3.Row; clubs=con.execute("SELECT id,slug,name FROM clubs WHERE active=1 ORDER BY name").fetchall()
    if args.club:clubs=[c for c in clubs if c["slug"]==args.club]
    tm=load_all_tm(); fd={y:fetch_fd_season(y) for y in (2023,2024,2025)}; built={}; report={}
    for c in clubs:
        qs=Builder(c,tm,fd).build(); built[c["id"]]=qs; counts=Counter(q["question_kind"] for q in qs); report[c["slug"]]={"total":len(qs),"categories":dict(sorted(counts.items()))}
    result={"target_per_club":TARGET,"clubs":report,"all_ready":all(v["total"]>=TARGET for v in report.values())}
    if args.install:result["backup"]=install(con,built,args.force_underfilled);result["installed"]=True
    print(json.dumps(result,indent=2,ensure_ascii=False))
if __name__=="__main__":main()
