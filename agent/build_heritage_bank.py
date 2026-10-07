#!/usr/bin/env python3
"""Heritage questions: trophies, cup finals, managers and club legends.

Every fact must agree across two independent records before it becomes a question:
  * trophies/finals: Wikipedia's finals or champions list  +  Wikidata's winner for that season/final
                     (+ the list's own per-club summary for counts, + the final's article naming both clubs)
  * managers:        Wikidata head-coach spells  +  the manager's Wikipedia infobox
  * legends:         Wikidata appearances/goals for the club  +  the player's Wikipedia infobox
Anything missing or contradictory is skipped, never guessed.

    build_heritage_bank.py [--install] [--club SLUG] [--only honours|managers|legends]
"""
from __future__ import annotations

import argparse
import collections
import datetime as dt
import hashlib
import json
import os
import random
import re
import sqlite3
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from question_quality import numeric_options, lint_question  # noqa: E402
import wiki_tables as wt  # noqa: E402

DB = os.getenv('QUIZ_DB', '/var/lib/clubdailyfive/clubquiz.sqlite')
CACHE = Path(os.getenv('HERITAGE_CACHE', '/var/lib/clubdailyfive/heritage-cache'))
PROFILES = Path('/var/www/clubdailyfive.com/public_html/club_profiles.json')
UA = 'ClubDailyFive/3.0 (admin@clubdailyfive.com; quiz fact checking)'
LAST_COMPLETE = 2025  # questions are anchored to "up to the end of the 2025-26 season"
_last_call = {'wp': 0.0, 'wd': 0.0}


# ------------------------------------------------------------------ sources

def _get(url, kind, ttl_days=14):
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / hashlib.sha256(url.encode()).hexdigest()
    if path.exists() and time.time() - path.stat().st_mtime < ttl_days * 86400:
        return json.loads(path.read_text())
    wait = (1.0 if kind == 'wp' else 2.0) - (time.monotonic() - _last_call[kind])
    if wait > 0:
        time.sleep(wait)
    for attempt in range(4):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept': 'application/json'})
            data = json.load(urllib.request.urlopen(req, timeout=120))
            break
        except Exception:
            if attempt == 3:
                raise
            time.sleep(10 * (attempt + 1))
    _last_call[kind] = time.monotonic()
    path.write_text(json.dumps(data))
    return data


def wp_api(**params):
    params.update(format='json', formatversion=2)
    return _get('https://en.wikipedia.org/w/api.php?' + urllib.parse.urlencode(params), 'wp')


def wp_html(title):
    return wp_api(action='parse', page=title, prop='text', redirects=1)['parse']['text']


def wp_wikitext(titles):
    """{requested title: wikitext} following redirects, 50 titles per call."""
    out = {}
    titles = list(dict.fromkeys(titles))
    for i in range(0, len(titles), 50):
        chunk = titles[i:i + 50]
        data = wp_api(action='query', prop='revisions', rvprop='content', rvslots='main', titles='|'.join(chunk), redirects=1)['query']
        back = {t: t for t in chunk}
        for n in data.get('normalized', []): back[n['to']] = back.get(n['from'], n['from'])
        for r in data.get('redirects', []): back[r['to']] = back.get(r['from'], r['from'])
        for page in data.get('pages', []):
            revs = page.get('revisions')
            if revs:
                out[back.get(page['title'], page['title'])] = revs[0]['slots']['main']['content']
    return out


def wp_intros(titles):
    out = {}
    titles = list(dict.fromkeys(titles))
    for i in range(0, len(titles), 20):
        chunk = titles[i:i + 20]
        data = wp_api(action='query', prop='extracts', exintro=1, explaintext=1, exlimit=20, titles='|'.join(chunk), redirects=1)['query']
        back = {t: t for t in chunk}
        for n in data.get('normalized', []): back[n['to']] = back.get(n['from'], n['from'])
        for r in data.get('redirects', []): back[r['to']] = back.get(r['from'], r['from'])
        for page in data.get('pages', []):
            if page.get('extract'):
                out[back.get(page['title'], page['title'])] = page['extract']
    return out


def sparql(query):
    url = 'https://query.wikidata.org/sparql?' + urllib.parse.urlencode({'query': query, 'format': 'json'})
    return _get(url, 'wd')['results']['bindings']


def wd_winners(article_titles):
    """Wikidata P1346 winners (rank 1 or unranked) for items behind these enwiki articles -> {article: {winner article}}."""
    out = collections.defaultdict(set)
    titles = list(dict.fromkeys(article_titles))
    for i in range(0, len(titles), 80):
        values = ' '.join(json.dumps(t, ensure_ascii=False) + '@en' for t in titles[i:i + 80])
        rows = sparql(f'''SELECT ?title ?wtitle WHERE {{
          VALUES ?title {{ {values} }}
          ?art schema:about ?s; schema:isPartOf <https://en.wikipedia.org/>; schema:name ?title.
          ?s p:P1346 ?st. ?st ps:P1346 ?w. OPTIONAL {{ ?st pq:P1352 ?rank }}
          FILTER(!BOUND(?rank) || ?rank = 1)
          ?wart schema:about ?w; schema:isPartOf <https://en.wikipedia.org/>; schema:name ?wtitle. }}''')
        for r in rows:
            out[r['title']['value']].add(r['wtitle']['value'])
    return out


# ------------------------------------------------------------------ clubs

def load_clubs(con):
    profiles = json.loads(PROFILES.read_text())
    clubs = {}
    for cid, slug, name in con.execute('select id,slug,name from clubs where active=1'):
        url = profiles.get(slug, {}).get('source_url', '')
        if 'en.wikipedia.org/wiki/' in url:
            clubs[slug] = {'id': cid, 'slug': slug, 'name': name,
                           'wiki': urllib.parse.unquote(url.rsplit('/wiki/', 1)[1]).replace('_', ' ')}
    return clubs


def short_name(title):
    """Article title -> the name supporters use ("FC Barcelona" -> "Barcelona", "Arsenal F.C." -> "Arsenal")."""
    from question_quality import team
    name = re.sub(r'\s*\(.*?\)\s*$', '', title)
    name = re.sub(r'\s+(?:F\.C\.|A\.F\.C\.|FC|CF|SC|AFC|F\.C|C\.F\.|KV)$', '', re.sub(r'^AFC ', '', name)).strip()
    name = team(name)
    return re.sub(r'^(?:FC|S\.L\.|A\.S\.|S\.S\.C\.|SSC|SL|SV) (?=\S)', '', name) if name not in ('FC Twente', 'FC Halifax Town') else name


# ------------------------------------------------------------------ honours

COMPS = {
    'fa-cup': dict(page='List of FA Cup finals', cols=('season', 'winners', 'score', 'runners'), final_col='score', season_col='season',
                   summary=('club', 'wins', 'runners'), title=lambda y: 'FA Cup', short='FA Cup'),
    'league-cup': dict(page='List of EFL Cup finals', cols=('final', 'winners', 'score', 'runners'), final_col='final', season_col=None,
                       summary=('club', 'winners', 'runners'), title=lambda y: 'League Cup', short='League Cup'),
    'league-title': dict(page='List of English football champions', cols=('season', 'champions', 'runners'), final_col=None, season_col='season',
                         summary=('club', 'winners', 'runners'), title=lambda y: 'English top-flight title', short='league title'),
    'european-cup': dict(page='List of European Cup and UEFA Champions League finals', cols=('season', 'winners', 'score', 'runners'), final_col='score', season_col='season',
                         summary=('club', 'title', 'runners'), title=lambda y: 'Champions League' if y >= 1993 else 'European Cup', short='European Cup/Champions League'),
    'uefa-cup': dict(page='List of UEFA Cup and Europa League finals', cols=('season', 'winners', 'score', 'runners'), final_col='score', season_col='season',
                     summary=('club', 'winners', 'runners'), title=lambda y: 'Europa League' if y >= 2010 else 'UEFA Cup', short='UEFA Cup/Europa League'),
    'cup-winners-cup': dict(page="List of UEFA Cup Winners' Cup finals", cols=('season', 'winners', 'score', 'runners'), final_col='score', season_col='season',
                            summary=('club', 'titles', 'runners'), title=lambda y: "European Cup Winners' Cup", short="Cup Winners' Cup"),
}


def season_label(end_year):
    return f'{end_year - 1}-{str(end_year)[-2:]}'


def parse_finals(key):
    cfg = COMPS[key]
    grids = wt.tables(wp_html(cfg['page']))
    finals, summary = {}, {}
    for g in grids:
        hi, idx = wt.header_index(g, *cfg['cols'])
        if hi is not None:
            col = dict(zip(cfg['cols'], idx))
            for row in g[hi + 1:]:
                if len(row) <= max(idx):
                    continue
                first = row[idx[0]]['text']
                m = re.match(r'^(\d{4})(?:[–-](\d{2,4}))?', first)
                if not m:
                    continue
                end = int(m.group(1)) if not m.group(2) else int(m.group(1)) + 1
                wcell, rcell = row[col[cfg['cols'][1]]], row[col['runners']]
                win, run = club_link(wcell), club_link(rcell)
                if not win or not run:
                    continue
                final_article = None
                if cfg['final_col']:
                    final_article = next((l for l in row[col[cfg['final_col']]]['links'] if re.search(r'final', l, re.I)), None)
                season_article = row[col['season']]['links'][0] if cfg['season_col'] and row[col['season']]['links'] else None
                rec = finals.setdefault(end, {'end': end, 'winners': set(), 'runners': set(), 'final': final_article, 'season': season_article})
                rec['winners'].add(win); rec['runners'].add(run)
                rec['final'] = rec['final'] or final_article
            continue
        hi, idx = wt.header_index(g, *cfg['summary'])
        if hi is not None:
            for row in g[hi + 1:]:
                if len(row) <= max(idx):
                    continue
                link = club_link(row[idx[0]])
                try:
                    wins, runs = int(row[idx[1]]['text']), int(row[idx[2]]['text'])
                except ValueError:
                    continue
                won_col = next((j for j, c in enumerate(g[hi]) if re.match(r'(years|seasons|winning seasons)', c['text'].strip(), re.I) and 'runner' not in c['text'].lower()), None)
                years = set()
                if won_col is not None and won_col < len(row):
                    for m in re.finditer(r'(\d{4})(?:[–-](\d{2}))?', row[won_col]['text']):
                        years.add(int(m.group(1)) + (1 if m.group(2) else 0))
                if link:
                    summary[link] = (wins, runs, years if won_col is not None else None)
    # Drop seasons whose winner is ambiguous in the table itself (e.g. a shared trophy).
    finals = {y: r for y, r in finals.items() if len(r['winners']) == 1 and len(r['runners']) == 1 and y <= LAST_COMPLETE + 1}
    for r in finals.values():
        r['winner'], r['runner'] = next(iter(r['winners'])), next(iter(r['runners']))
    return finals, summary


def club_link(cell):
    """The club article in a table cell (not the flag or federation link that often precedes it)."""
    links = [l for l in cell['links'] if not re.search(r'Football Association|Federation|Association$|^Wales$|^England$|^Scotland$', l)]
    text = norm(cell['text'])
    return next((l for l in links if norm(short_name(l)) and norm(short_name(l)) in text), links[0] if links else None)


def norm(value):
    return re.sub(r'[^a-z]', '', re.sub(r'\(.*?\)', '', (value or '').lower()))


def same_club(a, b):
    x, y = norm(short_name(a)), norm(short_name(b))
    return bool(x and y) and (x == y or x in y or y in x)


def verify_honours(key, finals, summary):
    """Season level: Wikidata names the same winner (or, where Wikidata is silent, the list's per-club summary does).
    Club level (needed for 'which season' and 'how many'): the per-club summary counts match the season table and
    every one of the club's wins is verified with no contradicting Wikidata claim."""
    titles = [t for r in finals.values() for t in (r['season'], r['final']) if t]
    wd = wd_winners(titles)
    covered = disputed = 0
    claims = collections.defaultdict(set)  # club article -> seasons Wikidata says it won
    for y, r in finals.items():
        found = set().union(*(wd.get(t, set()) for t in (r['season'], r['final']) if t)) if (r['season'] or r['final']) else set()
        r['wikidata'] = found
        for f in found:
            claims[f].add(y)
        if found:
            covered += 1
            r['verified'] = len(found) == 1 and same_club(next(iter(found)), r['winner'])
            disputed += not r['verified']
        else:
            years = (summary.get(r['winner']) or (0, 0, None))[2]
            r['verified'] = bool(years) and y in years
    counts = collections.Counter(r['winner'] for r in finals.values())
    runs = collections.Counter(r['runner'] for r in finals.values())
    reliable = set()
    for club, (w, ru, years) in summary.items():
        wins = {y for y, r in finals.items() if r['winner'] == club}
        if counts.get(club, 0) != w or runs.get(club, 0) != ru:
            continue
        if not all(finals[y]['verified'] for y in wins):
            continue
        if years is not None and years != wins:
            continue
        wd_claims = {y for f, ys in claims.items() if same_club(f, club) for y in ys}
        if wd_claims - wins:
            continue
        reliable.add(club)
    return {'covered_by_wikidata': covered, 'disputed': disputed, 'reliable_clubs': reliable, 'seasons': len(finals)}


def pick(seq, n, seed):
    seq = list(seq)
    random.Random(hashlib.sha256(seed.encode()).digest()).shuffle(seq)
    return seq[:n]


def ranked_years(answer, pool, seed, label):
    """Four seasons/years with the answer's position uniformly random among them."""
    pool = sorted(set(pool) - {answer})
    below = [y for y in pool if answer - 16 <= y < answer]
    above = [y for y in pool if answer < y <= answer + 16]
    r = random.Random(hashlib.sha256((seed + '|rank').encode()).digest())
    ranks = [k for k in range(4) if len(below) >= k and len(above) >= 3 - k]
    if not ranks:
        return None
    k = r.choice(ranks)
    years = sorted(r.sample(below, k)) + [answer] + sorted(r.sample(above, 3 - k))
    labels = [label(y) for y in years]
    random.Random(hashlib.sha256(seed.encode()).digest()).shuffle(labels)
    return labels, labels.index(label(answer))


def honours_questions(clubs):
    out = []
    by_title = {c['wiki']: c for c in clubs.values()}
    report = {}
    wins_by_club = collections.defaultdict(list)
    for key, cfg in COMPS.items():
        finals, summary = parse_finals(key)
        check = verify_honours(key, finals, summary)
        check['consistent'] = check['reliable_clubs']
        report[key] = {k: (len(v) if isinstance(v, set) else v) for k, v in check.items()}
        held = sorted(finals)
        intro_titles = [r['final'] for r in finals.values() if r['final'] and (r['winner'] in by_title or r['runner'] in by_title)]
        intros = wp_intros(intro_titles) if intro_titles else {}
        for title, club in by_title.items():
            wins = sorted(y for y, r in finals.items() if r['winner'] == title)
            lost = sorted(y for y, r in finals.items() if r['runner'] == title)
            can_count = title in check['consistent']
            label = (lambda y: season_label(y)) if cfg['season_col'] else (lambda y: str(y))
            src = 'https://en.wikipedia.org/wiki/' + urllib.parse.quote(cfg['page'].replace(' ', '_'))
            name = club['name']
            for y in wins:
                r = finals[y]
                comp = cfg['title'](y)
                if r['verified']:
                    trophy = f"{y} {comp} final" if cfg['final_col'] else f"{season_label(y)} league title"
                    wins_by_club[club['slug']].append((key, trophy.replace(' final', '') if not cfg['final_col'] else f"{y} {comp}", y))
                if not r['verified'] or not can_count:
                    continue
                # Which season: distractors are seasons the competition was held but this club did not win it.
                opts = ranked_years(y, [s for s in held if s not in wins], f'{key}|{club["slug"]}|{y}|season', label)
                if opts:
                    when = 'season' if cfg['season_col'] else 'year'
                    out.append(dict(club=club, family='honours', key=f'{key}|{y}|won', fact_date=None, src=src,
                                    text=f"In which {when} did {name} win the {comp}?", options=opts,
                                    explanation=f"{name} won the {comp} in {label(y)}, beating {short_name(r['runner'])}" + (' in the final.' if cfg['final_col'] else ' to the title.')))
            for y in wins + lost:
                r = finals[y]
                comp = cfg['title'](y)
                won = r['winner'] == title
                other = r['runner'] if won else r['winner']
                if not r['verified']:
                    continue
                if cfg['final_col']:
                    intro = intros.get(r['final'], '')
                    if not (short_name(other) in intro and short_name(title) in intro):
                        continue  # the final's own article must name both clubs
                    peers = {f[k2] for yy, f in finals.items() if abs(yy - y) <= 12 for k2 in ('winner', 'runner')} - {title, other}
                    if len(peers) < 3:
                        continue
                    opts = [short_name(other)] + [short_name(p) for p in pick(sorted(peers), 3, f'{key}|{club["slug"]}|{y}|opp')]
                    if len(set(opts)) < 4:
                        continue
                    opts = pick(opts, 4, f'{key}|{club["slug"]}|{y}|opp-order')
                    final_name = f"{y} {comp} final" if key != 'european-cup' or y < 1993 else f"{y} Champions League final"
                    text = f"Who did {name} beat in the {final_name}?" if won else f"Who beat {name} in the {final_name}?"
                    exp = (f"{name} beat {short_name(other)} in the {final_name}." if won else f"{short_name(other)} beat {name} in the {final_name}.")
                    out.append(dict(club=club, family='honours', key=f'{key}|{y}|final', fact_date=None,
                                    src='https://en.wikipedia.org/wiki/' + urllib.parse.quote(r['final'].replace(' ', '_')),
                                    text=text, options=(opts, opts.index(short_name(other))), explanation=exp))
                elif False:  # league runners-up have no independent second record; not asked
                    peers = {f[k2] for yy, f in finals.items() if abs(yy - y) <= 10 for k2 in ('winner', 'runner')} - {title, other}
                    if len(peers) < 3:
                        continue
                    opts = pick([short_name(other)] + [short_name(p) for p in pick(sorted(peers), 3, f'{key}|{club["slug"]}|{y}|ru')], 4, f'{key}|{club["slug"]}|{y}|ru-order')
                    out.append(dict(club=club, family='honours', key=f'{key}|{y}|runner-up', fact_date=None, src=src,
                                    text=f"Which club finished runners-up when {name} won the {season_label(y)} league title?",
                                    options=(opts, opts.index(short_name(other))),
                                    explanation=f"{short_name(other)} were runners-up when {name} won the {season_label(y)} title."))
            if can_count and wins:
                comp = cfg['short']
                n = len(wins)
                opts = numeric_options(n, f'{key}|{club["slug"]}|count', 0, None)
                out.append(dict(club=club, family='honours', key=f'{key}|count-{LAST_COMPLETE}', fact_date=None, src=src,
                                text=f"Up to the end of the {LAST_COMPLETE}-{str(LAST_COMPLETE + 1)[-2:]} season, how many times had {name} won the {comp if key != 'league-title' else 'English top-flight title'}?",
                                options=opts, explanation=f"{name} had won it {n} time{'s' if n != 1 else ''}, most recently in {label(wins[-1])}."))
                if n >= 2:
                    first = ranked_years(wins[0], [s for s in held if s not in wins], f'{key}|{club["slug"]}|first', label)
                    if first:
                        out.append(dict(club=club, family='honours', key=f'{key}|first', fact_date=None, src=src,
                                        text=f"When did {name} win the {cfg['title'](wins[0])} for the first time?", options=first,
                                        explanation=f"{name}'s first {cfg['short']} win came in {label(wins[0])}."))
    return out, report, wins_by_club


# ------------------------------------------------------------------ install

def to_rows(items):
    rows = []
    for q in items:
        opts, idx = q['options']
        sem = f"heritage|{q['club']['slug']}|{q['family']}|{q['key']}"
        rows.append(dict(club_id=q['club']['id'], question_text=q['text'], options_json=json.dumps(opts, ensure_ascii=False),
                         correct_index=idx, explanation=q['explanation'], source_url=q['src'],
                         source_label='Wikipedia and Wikidata (cross-checked)', semantic_key=sem,
                         content_hash=hashlib.sha256((sem + '|' + q['text']).encode()).hexdigest(), fact_date=q['fact_date']))
    return rows


def install(con, rows):
    added = updated = 0
    for r in rows:
        old = con.execute('select id,status from questions where semantic_key=?', (r['semantic_key'],)).fetchone()
        if old:
            con.execute('update questions set question_text=?,options_json=?,correct_index=?,explanation=?,source_url=?,content_hash=? where id=?',
                        (r['question_text'], r['options_json'], r['correct_index'], r['explanation'], r['source_url'], r['content_hash'], old[0]))
            updated += 1
        else:
            con.execute('''insert into questions(club_id,question_text,options_json,correct_index,explanation,source_url,source_label,content_hash,
                           semantic_key,status,question_kind,fact_date,use_count,last_used_date) values(?,?,?,?,?,?,?,?,?,'reviewed','history',?,0,NULL)''',
                        (r['club_id'], r['question_text'], r['options_json'], r['correct_index'], r['explanation'], r['source_url'],
                         r['source_label'], r['content_hash'], r['semantic_key'], r['fact_date']))
            added += 1
    # Facts that no longer pass verification are withdrawn rather than left in rotation.
    current = {r['semantic_key'] for r in rows}
    families = {r['semantic_key'].split('|')[2] for r in rows}
    retired = 0
    for qid, sem in con.execute("select id,semantic_key from questions where semantic_key like 'heritage|%' and status='reviewed'").fetchall():
        if sem.split('|')[2] in families and sem not in current:
            con.execute("update questions set status='retired' where id=?", (qid,)); retired += 1
    return added, updated, retired


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--install', action='store_true')
    ap.add_argument('--club')
    ap.add_argument('--only', choices=['honours', 'managers', 'legends'])
    ap.add_argument('--show', type=int, default=0)
    ap.add_argument('--if-stale-days', type=int, help='nightly use: refresh only when the last refresh is older than this; never fail the job')
    a = ap.parse_args()
    if a.if_stale_days:
        stamp = CACHE / 'last-install'
        if stamp.exists() and time.time() - stamp.stat().st_mtime < a.if_stale_days * 86400:
            print(f'Heritage questions refreshed within the last {a.if_stale_days} days; skipped.')
            return
        try:
            run(a)
            stamp.touch()
        except Exception as e:  # sources unreachable: keep the verified bank, retry next night
            print(f'Heritage refresh incomplete ({type(e).__name__}: {e}); existing verified questions kept.')
        return
    run(a)


def run(a):
    con = sqlite3.connect(DB, timeout=60)
    clubs = load_clubs(con)
    if a.club:
        clubs = {a.club: clubs[a.club]}
    items, report, wins = [], {}, {}
    if a.only in (None, 'honours', 'managers'):
        got, report['honours'], wins = honours_questions(clubs)
        if a.only != 'managers':
            items += got
    if a.only in (None, 'managers'):
        from heritage_people import managers_questions
        got, report['managers'] = managers_questions(clubs, sparql, wp_wikitext, wins); items += got
    if a.only in (None, 'legends'):
        from heritage_people import legends_questions
        got, report['legends'] = legends_questions(clubs, sparql, wp_wikitext); items += got
    rows = to_rows(items)
    bad = [(r['question_text'], lint_question(r)) for r in rows if lint_question(r)]
    rows = [r for r in rows if not lint_question(r)]
    per_club = collections.Counter(r['semantic_key'].split('|')[1] for r in rows)
    per_family = collections.Counter(r['semantic_key'].split('|')[2] for r in rows)
    result = {'questions': len(rows), 'rejected_by_quality_check': len(bad), 'per_family': per_family,
              'per_club': dict(sorted(per_club.items())), 'clubs_without_any': sorted(set(clubs) - set(per_club)), 'sources': report}
    if a.show:
        for r in random.Random(1).sample(rows, min(a.show, len(rows))):
            opts = json.loads(r['options_json'])
            print('-', r['question_text'], '|', ' / '.join(opts), '| ans:', opts[r['correct_index']])
    if a.install:
        con.execute('begin immediate')
        try:
            result['added'], result['updated'], result['retired'] = install(con, rows)
            con.commit()
        except Exception:
            con.rollback(); raise
    print(json.dumps(result, indent=1, ensure_ascii=False, default=list))


if __name__ == '__main__':
    main()
