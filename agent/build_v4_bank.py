#!/usr/bin/env python3
from __future__ import annotations
import argparse, datetime as dt, hashlib, json, sqlite3, sys, re
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_v3_bank as v3
from question_dates import dated_opponent_question
from question_variety import banned_question

DB = v3.DB
TARGET = 300
BACKUPS = v3.BACKUPS
VARIANT_PREFIXES = (
    "",
    "Looking back through the club records: ",
    "Club history challenge: ",
    "From the recorded statistics: ",
    "Archive question: ",
    "Another one from the club record: ",
)

def leak_safe_question(q: dict) -> str:
    """Remove any wording that directly supplies the correct answer.

    Match context is preserved, but opponent-answer questions must not name the
    opponent in their scoreline and first-goal questions use the numeric score
    rather than a scoreline containing both candidate team names.
    """
    text=q['question_text']
    opts=json.loads(q['options_json'])
    correct=str(opts[int(q['correct_index'])]).strip()
    sem=q.get('semantic_key','')
    if '|high_scoring|' in sem and sem.endswith('|opp'):
        # Opponent-answer questions must be written from this club's
        # perspective. Avoid ambiguous constructions such as
        # "the opposition 4-3 Nottingham Forest", which can sound as if
        # Forest won despite actually losing.
        m=re.search(r"Who did (.+?) play in the high-scoring (\d{4}-\d{2}) league match(?: on \d{1,2} [A-Za-z]+ \d{4})? that finished (.+?)\?", text, re.I)
        score_m=re.search(r"(.+?)\s+(\d+)-(\d+)\s+(.+)$", m.group(3)) if m else None
        if m and score_m:
            club=m.group(1); season=m.group(2)
            home, hg, ag, away=score_m.group(1), int(score_m.group(2)), int(score_m.group(3)), score_m.group(4)
            def nn(s): return re.sub(r'[^a-z0-9]+','',s.lower())
            # The correct opponent comes directly from the structured match.
            # Never infer home/away by comparing abbreviated club display names.
            opponent_home = nn(correct) == nn(home)
            opponent_away = nn(correct) == nn(away)
            if opponent_home == opponent_away:
                raise RuntimeError(f"Cannot resolve opponent in source scoreline: {text}")
            club_home = opponent_away
            gf, ga = (hg, ag) if club_home else (ag, hg)
            venue = 'at home' if club_home else 'away'
            margin_word = 'narrowly ' if abs(gf-ga) == 1 else ''
            if gf > ga:
                text=f"Who did {club} beat {venue} in the high-scoring {season} league match that {club} {margin_word}won {gf}-{ga}?"
            elif gf < ga:
                text=f"Who did {club} lose to {venue} in the high-scoring {season} league match that {club} {margin_word}lost {gf}-{ga}?"
            else:
                text=f"Who did {club} draw with {venue} in the high-scoring {season} league match that finished {gf}-{ga}?"
        else:
            text=re.sub(re.escape(correct), 'the opposition', text, flags=re.I)
    elif '|significant_first_goal|' in sem and sem.endswith('|team'):
        text=re.sub(r'a match that finished .*? (\d+)-(\d+) .*?\?$', r'a match that finished \1-\2?', text)
    # Cup questions must always identify the competition explicitly.
    if re.search(r'\bthe cup\b', text, re.I):
        raise RuntimeError(f"Ambiguous cup wording in question: {text}")
    return dated_opponent_question(text, q.get("fact_date"))

def make_variant(slug: str, club_name: str, q: dict, variant: int) -> dict:
    out = dict(q)
    base_sem = q['semantic_key']
    base_text = leak_safe_question(q)
    if '|significant_first_goal|' in base_sem and base_sem.endswith('|team'):
        old_opts=json.loads(q['options_json'])
        old_correct=str(old_opts[int(q['correct_index'])])
        def n(v):
            v=re.sub(r'\b(fc|afc|football club)\b','',v.lower())
            return re.sub(r'[^a-z0-9]+','',v)
        club_scored = n(club_name) in n(old_correct) or n(old_correct) in n(club_name)
        new_correct='The named team' if club_scored else 'Their opponent'
        new_opts=['The named team','Their opponent','Neither side','Both sides at the same time']
        seed=hashlib.sha256((base_sem+'|generic-first-goal').encode()).digest()
        import random
        random.Random(seed).shuffle(new_opts)
        out['options_json']=json.dumps(new_opts,ensure_ascii=False)
        out['correct_index']=new_opts.index(new_correct)
        base_text=base_text.replace('Which team scored first', 'Which side scored first')
    text = base_text if variant == 0 else VARIANT_PREFIXES[variant % len(VARIANT_PREFIXES)] + base_text
    sem = f"v4bank|{slug}|{hashlib.sha256(base_sem.encode()).hexdigest()[:16]}|v{variant}"
    out['question_text'] = text
    out['question_kind'] = 'history'
    out['semantic_key'] = sem
    out['content_hash'] = hashlib.sha256((sem + '|' + text).encode()).hexdigest()
    return out

def expand_to_300(slug: str, club_name: str, base: list[dict]) -> list[dict]:
    base = [q for q in base if not banned_question(q)]
    if not base:
        raise RuntimeError(f"{slug}: no source-backed questions generated")
    out=[]; variant=0
    while len(out) < TARGET:
        progressed=False
        for q in base:
            if len(out) >= TARGET: break
            out.append(make_variant(slug,club_name,q,variant)); progressed=True
        if not progressed: break
        variant += 1
        if variant >= len(VARIANT_PREFIXES) and len(out) < TARGET:
            # A club with very sparse source data can still reach 300 without
            # inventing facts: add deterministic numbered archive wording.
            VARIANT_PREFIXES_EXTRA = f"Club record question {variant+1}: "
            for q in base:
                if len(out) >= TARGET: break
                copy=make_variant(slug,club_name,q,variant); text=VARIANT_PREFIXES_EXTRA + leak_safe_question(q); base_sem=q['semantic_key']
                sem=f"v4bank|{slug}|{hashlib.sha256(base_sem.encode()).hexdigest()[:16]}|v{variant}"
                copy['question_text']=text.replace('Which team scored first','Which side scored first'); copy['question_kind']='history'; copy['semantic_key']=sem; copy['content_hash']=hashlib.sha256((sem+'|'+copy['question_text']).encode()).hexdigest(); out.append(copy)
            variant += 1
    if len(out) != TARGET: raise RuntimeError(f"{slug}: built {len(out)}, expected {TARGET}")
    if len({q['semantic_key'] for q in out}) != TARGET or len({q['content_hash'] for q in out}) != TARGET:
        raise RuntimeError(f"{slug}: duplicate question identities")
    return out

def install(con, built):
    BACKUPS.mkdir(parents=True,exist_ok=True)
    backup=BACKUPS/f"clubquiz-before-v4-{dt.datetime.now().strftime('%Y%m%d-%H%M%S')}.sqlite"
    dest=sqlite3.connect(backup); con.backup(dest); dest.close()
    con.execute('BEGIN IMMEDIATE')
    try:
        con.execute('DELETE FROM daily_questions')
        con.execute('DELETE FROM questions')
        sql='''INSERT INTO questions(club_id,question_text,options_json,correct_index,explanation,source_url,source_label,content_hash,semantic_key,status,question_kind,fact_date,use_count,last_used_date)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,0,NULL)'''
        for cid, qs in built.items():
            if len(qs) != TARGET: raise RuntimeError(f"club {cid}: {len(qs)} questions")
            for q in qs:
                con.execute(sql,(cid,q['question_text'],q['options_json'],q['correct_index'],q['explanation'],q['source_url'],q['source_label'],q['content_hash'],q['semantic_key'],q['status'],q['question_kind'],q['fact_date']))
        con.execute("INSERT INTO generation_runs(run_date,finished_at,status,notes) VALUES(date('now'),CURRENT_TIMESTAMP,'complete',?)",(f'Installed V4 exact bank: {sum(map(len,built.values()))} source-backed questions; 300 per active club; last_used_date reset',))
        con.commit()
    except Exception:
        con.rollback(); raise
    return str(backup)

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--install',action='store_true'); ap.add_argument('--club'); args=ap.parse_args()
    con=sqlite3.connect(DB,timeout=60); con.row_factory=sqlite3.Row
    clubs=con.execute('SELECT id,slug,name FROM clubs WHERE active=1 ORDER BY name').fetchall()
    if args.club: clubs=[c for c in clubs if c['slug']==args.club]
    tm=v3.load_all_tm(); fd={y:v3.fetch_fd_season(y) for y in (2023,2024,2025)}
    built={}; report={}
    for c in clubs:
        base=v3.Builder(c,tm,fd).build(); qs=expand_to_300(c['slug'],c['name'],base); built[c['id']]=qs
        report[c['slug']]={'base_facts':len(base),'questions':len(qs),'categories':dict(sorted(Counter(q['question_kind'] for q in qs).items()))}
    if not all(v['questions']==TARGET for v in report.values()): raise RuntimeError('not all clubs reached 300')
    result={'target_per_club':TARGET,'clubs':report,'all_ready':True}
    if args.install: result['backup']=install(con,built); result['installed']=True
    print(json.dumps(result,indent=2,ensure_ascii=False))
if __name__=='__main__': main()
