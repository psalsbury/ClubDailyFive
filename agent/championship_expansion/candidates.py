#!/usr/bin/env python3
"""Phase 1 (read-only): eligible Championship Player Wordle candidates from the Transfermarkt season data.

Eligibility (as published on the game's info panel) that this data can show:
  1. appeared for the club in 2025/26 or 2026/27, or
  2. made 25+ appearances for the club, all competitions, in the last 10 seasons (2016/17-2025/26; the data has no 2026/27 rows yet), or
  3. played for the club in the last 20 seasons (2006/07 on) and has played for a European senior men's national team
     (from Wikidata, matched on the Transfermarkt player ID).
Writes candidates.json: per club, eligible players with their full senior season history.
"""
import csv, json, pathlib, re, unicodedata, collections, sqlite3, time, urllib.parse, urllib.request
BASE = pathlib.Path('/var/lib/clubdailyfive')
OUT = pathlib.Path('/var/lib/clubdailyfive/championship-expansion/candidates.json')
RECENT = {'25/26', '26/27'}
LAST10 = {f"{y%100:02d}/{(y+1)%100:02d}" for y in range(2016, 2027)}  # data ends 2025/26, so this is the last 10 completed seasons
LAST20 = {f"{y%100:02d}/{(y+1)%100:02d}" for y in range(2006, 2027)}
UA = 'ClubDailyFive/1.0 (https://clubdailyfive.com; admin@clubdailyfive.com)'
# Youth, reserve and B teams are not senior club appearances.
YOUTH = re.compile(r'\b(U\d{2}|Reserves?|Reserve|Youth|Academy|II|B|Jong|Primavera|Juniors?)\b', re.I)

def norm(s):
    s = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode().lower()
    s = re.sub(r'\b(?:afc|fc|football club)\b', '', s)
    return re.sub('[^a-z0-9]', '', s)

def season_start(name):
    """'08/09' -> 2008, '95/96' -> 1995, '2019' -> 2019 (calendar-year leagues)."""
    if '/' in name:
        y = int(name.split('/')[0]); return 2000 + y if y < 50 else 1900 + y
    return int(name)

def european_internationals(tm_ids):
    """Transfermarkt IDs (of those given) whose Wikidata item played for a European senior men's national team."""
    found = {}
    ids = sorted(tm_ids)
    for i in range(0, len(ids), 250):
        values = ' '.join('"%s"' % x for x in ids[i:i+250])
        q = '''SELECT ?tm ?teamLabel WHERE { VALUES ?tm { %s } ?p wdt:P2446 ?tm; wdt:P54 ?team.
          ?team wdt:P31 wd:Q6979593. { ?team wdt:P17/wdt:P30 wd:Q46 } UNION { ?team wdt:P463 wd:Q35572 }
          SERVICE wikibase:label { bd:serviceParam wikibase:language "en". } }''' % values
        req = urllib.request.Request('https://query.wikidata.org/sparql?' + urllib.parse.urlencode({'query': q}),
                                    headers={'User-Agent': UA, 'Accept': 'application/sparql-results+json'})
        for b in json.load(urllib.request.urlopen(req, timeout=90))['results']['bindings']:
            found.setdefault(b['tm']['value'], set()).add(b['teamLabel']['value'])
        time.sleep(1)
    return {k: sorted(v) for k, v in found.items()}

def main():
    members = [m for m in json.load(open(BASE/'efl-clubs.json')) if m['league'] == 'championship']
    lookup = {}
    for m in members:
        for v in {m['name'], m['team'], m.get('alias', '')}:
            if v: lookup[norm(v)] = m['slug']
    club_rows = collections.defaultdict(lambda: collections.defaultdict(list))  # slug -> pid -> rows
    with open(BASE/'player-sources/performances.csv', encoding='utf-8-sig') as f:
        for r in csv.DictReader(f):
            slug = lookup.get(norm(r['team_name']))
            if slug: club_rows[slug][r['player_id']].append(r)
    # Criterion 3 candidates: anyone with an appearance for the club since 2006/07.
    last20 = {pid for players in club_rows.values() for pid, rows in players.items() if any(x['season_name'] in LAST20 and int(float(x['nb_on_pitch'] or 0)) > 0 for x in rows)}
    caps = european_internationals(last20)
    print('European internationals among last-20-season players:', len(caps))
    eligible = {}
    for slug, players in club_rows.items():
        out = {}
        for pid, rows in players.items():
            apps = lambda keep: sum(int(float(x['nb_on_pitch'] or 0)) for x in rows if keep(x['season_name']))
            total, last10, recent = apps(lambda s: True), apps(lambda s: s in LAST10), apps(lambda s: s in RECENT)
            last20 = apps(lambda s: s in LAST20)
            intl = caps.get(pid) if last20 > 0 else None
            if total <= 0 or not (last10 >= 25 or recent > 0 or intl): continue
            out[pid] = {'apps_total': total, 'apps_last10': last10, 'apps_recent': recent, 'national_teams': intl or [],
                        'criteria': [c for c, ok in (('recent', recent > 0), ('25_in_10', last10 >= 25), ('european_international', bool(intl))) if ok]}
        eligible[slug] = out
    wanted = {pid for e in eligible.values() for pid in e}
    history = collections.defaultdict(list)  # every senior club season for candidates (for debut season and prior clubs)
    with open(BASE/'player-sources/performances.csv', encoding='utf-8-sig') as f:
        for r in csv.DictReader(f):
            if r['player_id'] in wanted and not YOUTH.search(r['team_name']):
                n = int(float(r['nb_on_pitch'] or 0))
                if n > 0: history[r['player_id']].append({'season': r['season_name'], 'start': season_start(r['season_name']), 'team': r['team_name'], 'team_id': r['team_id'], 'competition': r['competition_name'], 'apps': n})
    profiles = {}
    with open(BASE/'player-sources/profiles.csv', encoding='utf-8-sig') as f:
        for p in csv.DictReader(f):
            if p['player_id'] in wanted: profiles[p['player_id']] = {k: p[k] for k in ('player_id', 'player_slug', 'player_name', 'date_of_birth', 'citizenship', 'country_of_birth', 'position', 'main_position')}
    db = sqlite3.connect('file:'+str(BASE/'player-wordle/game.sqlite3')+'?mode=ro', uri=True)
    result = {}
    for m in members:
        cid = db.execute('select id from clubs where slug=?', (m['slug'],)).fetchone()[0]
        have = {norm(n) for (n,) in db.execute('select name from players where club_id=?', (cid,))}
        rows = []
        for pid, e in eligible.get(m['slug'], {}).items():
            p = profiles.get(pid)
            if not p or not p['date_of_birth']: continue
            name = re.sub(r' \(\d+\)$', '', p['player_name'])
            rows.append({**e, 'profile': p, 'name': name, 'existing': norm(name) in have, 'history': sorted(history[pid], key=lambda h: h['start'])})
        rows.sort(key=lambda r: (-r['apps_last10'], -r['apps_recent'], -r['apps_total']))
        result[m['slug']] = {'member': m, 'club_id': cid, 'existing': len(have), 'candidates': rows}
        print(f"{m['slug']:26} existing {len(have):3}  eligible {len(rows):3}  new {sum(not r['existing'] for r in rows):3}")
    OUT.write_text(json.dumps(result))

if __name__ == '__main__': main()
