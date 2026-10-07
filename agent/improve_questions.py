#!/usr/bin/env python3
"""Normalise the stored question bank: fair options, consistent wording, retire unfair or wrong questions.

Run nightly from generate_questions.py (idempotent). Rows in today's or future published rounds are left
untouched so nobody sees a question change mid-quiz; they are normalised the following night.

    improve_questions.py [--dry-run] [--refresh-shootouts]
"""
from __future__ import annotations

import argparse
import collections
import csv
import datetime as dt
import gzip
import hashlib
import io
import json
import os
import re
import sqlite3
from pathlib import Path
from zoneinfo import ZoneInfo

from question_quality import (SCORE_OPTION, RETIRED_FAMILIES, attendance_options, clean_option, clean_text, cup_round,
                              fee_options, lint_question, numeric_options, parse_fee, round_options, score_options, team)

DB = os.getenv('QUIZ_DB', '/var/lib/clubdailyfive/clubquiz.sqlite')
TM = Path('/var/lib/clubdailyfive/transfermarkt-data')
SHOOTOUTS = Path('/var/lib/clubdailyfive/tm-shootout-games.json')
UK = ZoneInfo('Europe/London')
MACHINE = ('v4bank|', 'matchfact|', 'seasonfact|', 'dailyfresh|')


def shootout_games(refresh=False) -> set[str]:
    """Transfermarkt game ids decided on penalties (their goal totals include the shoot-out)."""
    if SHOOTOUTS.exists() and not refresh:
        return set(json.loads(SHOOTOUTS.read_text()))
    ids = set()
    with gzip.open(TM / 'game_events.csv.gz', 'rt', encoding='utf-8') as f:
        for e in csv.DictReader(f):
            if e['type'] == 'Shootout':
                ids.add(e['game_id'])
    SHOOTOUTS.write_text(json.dumps(sorted(ids)))
    return ids


def family(key: str) -> str:
    return key.rsplit('|', 1)[0] if re.search(r'\|v\d+$', key) else key


def variant(key: str) -> int:
    m = re.search(r'\|v(\d+)$', key)
    return int(m.group(1)) if m else 0


def int_bounds(text: str, explanation: str):
    """Bounds that keep every distractor possible, so none can be ruled out without knowing the answer."""
    t = text.lower()
    season_games = 38 if 'premier league' in t else 46
    if 'yellow cards' in t and ('against' in t or 'league match' in t) and 'season' not in t and 'through' not in t:
        return 0, 8
    m = re.search(r'across their (\d+) completed league matches', explanation.lower())
    if m and re.search(r'league (wins|draws|losses)|cards', t):
        return 0, int(m.group(1))
    if 'appearances did' in t:
        return 1, season_games
    if 'longest continuous' in t:
        return 1, season_games
    if re.search(r'how many league (wins|draws|losses) did', t):
        return 0, 46
    if 'goals in total' in t and 'high-scoring' in t:
        return 6, None
    if re.search(r'how many goals did .* score in their', t):
        return 0, None
    if 'how many' in t:
        return 0, None
    return None


def rebuild_options(row: dict, club: str):
    """Return (options, index) for machine-made questions, or None to keep the stored options."""
    text, key = row['question_text'], row['semantic_key']
    opts = json.loads(row['options_json'])
    answer = str(opts[int(row['correct_index'])])
    seed = 'fair|' + key
    m = SCORE_OPTION.match(answer)
    if m and re.search(r'\d+-\d+', answer) and all(SCORE_OPTION.match(str(o)) for o in opts):
        home_name, away_name = m.group(1), m.group(4)
        h, a = int(m.group(2)), int(m.group(3))
        outcome, min_total = None, 0
        if 'high-scoring' in text:
            min_total = 6
        if re.search(r'knocked out', text):
            # The named club lost; keep every option a defeat for them.
            outcome = 'A' if home_name and team(home_name) == team(club) else 'H'
        pts, idx = score_options(h, a, seed, outcome, min_total)
        if home_name or away_name:
            labels = [f"{home_name} {x}-{y} {away_name}".strip() for x, y in pts]
        else:
            labels = [f"{x}-{y}" for x, y in pts]
        return labels, idx
    if parse_fee(answer) is not None and re.search(r'transfer fee', text):
        return fee_options(parse_fee(answer), seed)
    cup = re.search(r'^(?:How far did .+ get in|At which round were .+ knocked out of) the (FA Cup|EFL Cup|UEFA .+?) in ', text)
    if cup:
        comp = 'fa' if cup.group(1) == 'FA Cup' else 'league' if cup.group(1) == 'EFL Cup' else 'europe'
        lowest = None if key.startswith('v4bank|efl|') or comp != 'fa' else 'Third round'
        if comp == 'league' and not key.startswith('v4bank|efl|'): lowest = 'Second round'
        opts, idx = round_options(answer, comp, seed, lowest)
        season = re.search(r'in (\d{4})-\d{2}', text)
        if comp == 'europe' and season and int(season.group(1)) >= 2024:
            opts = ['League phase' if o == 'Group stage' else o for o in opts]
        return opts, idx
    plain = answer.replace(',', '')
    if plain.isdigit() and all(str(o).replace(',', '').isdigit() for o in opts):
        value = int(plain)
        if re.search(r'attendance', text, re.I):
            return attendance_options(value, seed, highest=bool(re.search(r'highest', text, re.I)))
        if 1850 <= value <= 2100 and re.search(r'\byear\b|born|founded', text, re.I):
            if re.search(r'\bborn\b', text):
                return numeric_options(value, seed, value - 8, value + 8, spread=6)
            return None  # other year questions keep their curated options
        bounds = int_bounds(text, row.get('explanation') or '')
        if bounds is None:
            return None
        lo, hi = bounds
        return numeric_options(value, seed, lo, hi)
    return None


def game_id(url: str) -> str | None:
    m = re.search(r'/spielbericht/(?:index/spielbericht/)?(\d+)', url or '')
    return m.group(1) if m else None


def normalise(con: sqlite3.Connection, today: str | None = None, dry_run=False, shootouts: set[str] | None = None) -> dict:
    today = today or dt.datetime.now(UK).date().isoformat()
    shootouts = shootout_games() if shootouts is None else shootouts
    clubs = dict(con.execute('select id,name from clubs'))
    protected = {r[0] for r in con.execute('select question_id from daily_questions where quiz_date>=?', (today,))}
    rows = [dict(r) for r in con.execute("select * from questions where status='reviewed' order by id")]
    stats = collections.Counter()
    keep_family = {}
    # One row per underlying fact: prefer the unprefixed wording (v0), then the lowest variant number.
    for r in rows:
        if r['semantic_key'].startswith('v4bank|') and not r['semantic_key'].startswith('v4bank|efl|'):
            f = (r['club_id'], family(r['semantic_key']))
            best = keep_family.get(f)
            if best is None or variant(r['semantic_key']) < variant(best['semantic_key']):
                keep_family[f] = r
    seen_text = {}
    for r in rows:
        if r['id'] in protected:
            stats['protected (live round)'] += 1
            continue
        club = clubs.get(r['club_id'], '')
        retire = None
        f = (r['club_id'], family(r['semantic_key']))
        if f in keep_family and keep_family[f]['id'] != r['id']:
            retire = 'padding variant of the same fact'
        elif any(p.search(r['question_text']) for p in RETIRED_FAMILIES):
            retire = 'retired question family'
        elif game_id(r['source_url']) in shootouts and re.search(r'\d+-\d+', r['options_json'] + r['explanation']):
            retire = 'score includes a penalty shoot-out'
        new = dict(r)
        if not retire:
            new['question_text'] = clean_text(r['question_text'], club)
            new['explanation'] = clean_text(r['explanation'], club)
            opts = [clean_option(o) for o in json.loads(r['options_json'])]
            if len({o.casefold() for o in opts}) == 4:
                new['options_json'] = json.dumps(opts, ensure_ascii=False)
            if r['semantic_key'].startswith(MACHINE):
                try:
                    rebuilt = rebuild_options(new, club)
                except ValueError as e:
                    rebuilt = None
                    stats['options kept (no fair alternative): ' + str(e)[:40]] += 1
                if rebuilt:
                    new['options_json'] = json.dumps(rebuilt[0], ensure_ascii=False)
                    new['correct_index'] = rebuilt[1]
            norm = (r['club_id'], re.sub(r'\W+', ' ', new['question_text'].lower()).strip(),
                    json.loads(new['options_json'])[int(new['correct_index'])])
            if norm in seen_text:
                retire = 'duplicate wording of another question'
            else:
                seen_text[norm] = r['id']
        if retire:
            stats['retired: ' + retire] += 1
            if not dry_run:
                con.execute("update questions set status='retired' where id=?", (r['id'],))
            continue
        changed = any(new[k] != r[k] for k in ('question_text', 'explanation', 'options_json', 'correct_index'))
        if changed:
            stats['updated'] += 1
            new['content_hash'] = hashlib.sha256((new['semantic_key'] + '|' + new['question_text']).encode()).hexdigest()
            if not dry_run:
                con.execute('update questions set question_text=?,explanation=?,options_json=?,correct_index=?,content_hash=? where id=?',
                            (new['question_text'], new['explanation'], new['options_json'], new['correct_index'], new['content_hash'], r['id']))
    lint = collections.Counter()
    for r in con.execute("select * from questions where status='reviewed'"):
        for p in lint_question(r):
            lint[p.split(':')[0]] += 1
    stats_out = dict(stats)
    stats_out['still failing quality check (excluded from rounds)'] = dict(lint)
    return stats_out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--refresh-shootouts', action='store_true')
    ap.add_argument('--today')
    a = ap.parse_args()
    con = sqlite3.connect(DB, timeout=60)
    con.row_factory = sqlite3.Row
    shoot = shootout_games(a.refresh_shootouts)
    con.execute('begin immediate')
    try:
        result = normalise(con, a.today, a.dry_run, shoot)
        if a.dry_run:
            con.rollback()
        else:
            con.commit()
    except Exception:
        con.rollback()
        raise
    print(json.dumps(result, indent=1, ensure_ascii=False))


if __name__ == '__main__':
    main()
