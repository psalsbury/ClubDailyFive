#!/usr/bin/env python3
"""Phase 3 (read-only): work out the five clues for each candidate and choose up to ~100 players per club.

Debut (gives debut year and debut age):
  exact  - a Wikipedia sentence gives the exact date of the first competitive game for the club
           (the collector's own debut reader), the article's subject is confirmed by Transfermarkt ID
           via Wikidata and matching date of birth, and the date falls in the player's first season
           with appearances for the club in the Transfermarkt season data.
  season - otherwise, the first season with appearances for the club in the Transfermarkt season data.
           Debut year is the season's first year, or its second year when the player arrived mid-season
           (Wikipedia career start year, or appearances for another senior club earlier that season).
           Debut age is the age on 15 August (or 1 February for a mid-season arrival). This is an estimate.
Position: Transfermarkt main position; skipped if Wikipedia gives a single, different broad position.
Nationality: the single citizenship; with several, the national team the player has caps for (Wikipedia),
  else Transfermarkt's first-listed nationality (the collector's existing convention).
Previous senior clubs: Wikipedia senior career table before the club when the article matches the club,
  else distinct senior clubs with appearances in earlier seasons in the season data.
Writes proposals.json and prints a per-club summary.
"""
import sys, json, re, pathlib, hashlib, datetime as dt, collections, unicodedata
sys.path.insert(0, '/opt/clubdailyfive/bin')
import collect_efl_players as r, championship_verification as cv
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import debut_finder as df, nationality as nat
from player_country import continent, first_country
from source_utils import infobox, clean, broad_position
WORK = pathlib.Path('/var/lib/clubdailyfive/championship-expansion')
CACHE = pathlib.Path('/var/lib/clubdailyfive/efl-cache/wiki-api')
SPELLS = json.load(open(WORK/'wikidata_spells.json'))
TARGET = 100
POS = {'goalkeeper': 'Goalkeeper', 'defender': 'Defender', 'midfield': 'Midfielder', 'attack': 'Forward'}
RANK = {'Goalkeeper': 0, 'Defender': 1, 'Midfielder': 2, 'Forward': 3}

def norm(s):
    s = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode().lower()
    s = re.sub(r'\b(?:afc|fc|football club)\b', '', s)
    return re.sub('[^a-z0-9]', '', s)

def age_on(dob, day):
    return day.year - dob.year - ((day.month, day.day) < (dob.month, dob.day))

def load_article(links, pid, dob):
    link = links.get(pid)
    if not link or len(link['titles']) != 1: return None, None
    if link['dobs'] and dob.isoformat() not in link['dobs']: return None, None
    path = CACHE/(hashlib.sha256(link['titles'][0].encode()).hexdigest() + '.html')
    if not path.exists(): return None, None
    raw = path.read_text()
    bday = re.search(r'class="bday"[^>]*>(\d{4}-\d{2}-\d{2})<', raw)
    if bday and bday[1] != dob.isoformat(): return None, None
    return 'https://en.wikipedia.org/wiki/' + link['titles'][0].replace(' ', '_'), raw

def signing_date(raw, member, window):
    """Latest stated date the player joined the club (signing or loan) within, or shortly before, the first season."""
    aliases = {a for a in {member['name'].lower(), member['team'].lower()} if len(a) > 3}
    dates = []
    for para in re.findall(r'<p\b[^>]*>.*?</p>', raw, re.S):
        for sentence in re.split(r'(?<=[.!?])\s+(?=[A-Z])', clean(para)):
            low = sentence.lower()
            if not re.search(r'\b(signed|joined|completed (?:a|his) move|loan (?:move )?to)\b', low) or not any(a in low for a in aliases): continue
            if 'debut' in low or 'contract extension' in low or 'new contract' in low: continue
            found = re.findall(r'\b(\d{1,2} (?:' + df.MONTHS + r') (?:19|20)\d{2})\b', sentence)
            if len(found) != 1: continue
            d = dt.datetime.strptime(found[0], '%d %B %Y').date()
            if window[0] - dt.timedelta(days=90) <= d <= window[1]: dates.append(d)
    return max(dates) if dates else None

def facts(c, member, club_norms, links):
    p = c['profile']; dob = dt.date.fromisoformat(p['date_of_birth'])
    club_seasons = [h for h in c['history'] if norm(h['team']) in club_norms]
    if not club_seasons: return None, 'no appearances for the club in the season data'
    S = min(h['start'] for h in club_seasons)
    window = (dt.date(S, 7, 1), dt.date(S + 1, 8, 31) if S == 2019 else dt.date(S + 1, 6, 30))  # 2019/20 finished in August 2020
    url, raw = load_article(links, p['player_id'], dob)
    rows = r.career(raw) if raw else []
    names = {norm(member['name']), norm(member['team'].removesuffix(' FC').removesuffix(' AFC'))}
    match = [i for i, (_, team) in enumerate(rows) if norm(team) in names]
    # Debut
    method = 'season'; evidence = None; debut = None
    first_comps = sorted({h['competition'] for h in club_seasons if h['start'] == S})
    club_names = [member['name'], member['team'], member.get('alias', '')]
    games = df.club_games([n for n in club_names if n], window)
    if raw:
        date, precision, evidence = df.find_debut(raw, member, window, first_comps, games)
        if date and precision == 'day': debut, method = date, 'exact'
        elif date:
            # Month and year are sourced; the day is unknown, so the age is exact unless the birthday falls in that month.
            debut, method = date.replace(day=15), 'month'
    if not debut:
        other_same_season = any(h['season'] == club_seasons[0]['season'] and norm(h['team']) not in club_norms and '/' in h['season'] for h in c['history'])
        mid_season = (rows[match[0]][0] == S + 1) if match else other_same_season
        signed = signing_date(raw, member, window) if raw else None
        signed_source = 'Wikipedia'
        if not signed:
            starts = [dt.date.fromisoformat(x) for x in SPELLS.get(member['slug'], {}).get(p['player_id'], [])]
            starts = [x for x in starts if window[0] - dt.timedelta(days=90) <= x <= window[1]]
            if starts: signed, signed_source = max(starts), 'Wikidata'
        if signed:
            debut = max(signed + dt.timedelta(days=3), dt.date(S, 8, 15)); mid_season = debut.year == S + 1
        else:
            debut = dt.date(S + 1, 2, 1) if mid_season else dt.date(S, 8, 15)
        evidence = f"First season with appearances for the club: {club_seasons[0]['season']} (Transfermarkt season data)" + (f'; joined {signed.isoformat()} ({signed_source})' if signed else '; arrived mid-season' if mid_season else '')
    age = age_on(dob, debut)
    if not 15 <= age <= 45: return None, f'debut age {age} out of range'
    # Position
    main = (p.get('main_position') or p.get('position', '').split(' - ')[0]).strip().lower()
    position = POS.get(main)
    wiki_pos = broad_position(clean(infobox(raw).get('Position(s)', infobox(raw).get('Position', '')))) if raw else None
    if not position: position = wiki_pos
    if not position: return None, 'no position'
    if wiki_pos and wiki_pos != position: return None, f'position disagrees (Transfermarkt {position}, Wikipedia {wiki_pos})'
    # Nationality
    citizenships = [x.strip() for x in re.split(r'\s{2,}|\s*/\s*|,', p.get('citizenship', '')) if x.strip()]
    if not citizenships: return None, 'no nationality'
    nationality = first_country(citizenships[0]); nat_source = 'single citizenship' if len(citizenships) == 1 else 'Transfermarkt first-listed nationality'
    if len(citizenships) > 1 and raw:
        capped = cv.football_nationality(raw, p['citizenship'])
        if capped: nationality, nat_source = first_country(capped[0]), 'senior caps (Wikipedia): ' + capped[1]
    if len(citizenships) > 1 and raw and nat_source.startswith('Transfermarkt'):
        found = nat.from_article(raw, [first_country(x) for x in citizenships])
        if found: nationality, nat_source = found
    nationality = nat.canonical(nationality)
    cont = continent(nationality)
    if cont == 'Other': cont = {'Gibraltar': 'Europe', 'Bangladesh': 'Asia', 'Andorra': 'Europe', 'San Marino': 'Europe', 'Liechtenstein': 'Europe', 'Moldova': 'Europe', 'Azerbaijan': 'Europe'}.get(nationality, 'Other')
    if cont == 'Other': return None, f'unmapped nationality {nationality}'
    # Previous senior clubs
    if match:
        prior = len({norm(team) for y, team in rows[:match[0]] if y <= debut.year and norm(team) not in names}); prior_source = 'Wikipedia senior career'
    else:
        before = {norm(h['team']) for h in c['history'] if norm(h['team']) not in club_norms and (h['start'] < S or (h['season'] == club_seasons[0]['season'] and debut.year == S + 1))}
        prior = len(before); prior_source = 'Transfermarkt season data'
    name = c['name'].strip()
    if not name and url:  # names with apostrophes (O'Brien, N'Doye) are blank in the source file
        name = re.sub(r' \(.*\)$', '', links[p['player_id']]['titles'][0])
    if not name: return None, 'no name'
    return {'name': name, 'debut_age': age, 'debut_year': debut.year, 'position': position, 'position_rank': RANK[position],
            'nationality': nationality, 'continent': cont, 'prior_clubs': prior, 'appearances': c['apps_total'],
            'source_url': url if method in ('exact', 'month') else f"https://www.transfermarkt.co.uk/{p['player_slug']}/profil/spieler/{p['player_id']}",
            'method': method, 'profile_id': p['player_id'], 'criteria': c['criteria'],
            'evidence': {'debut': evidence, 'debut_date' if method == 'exact' else 'debut_month' if method == 'month' else 'assumed_debut_date': debut.isoformat(),
                         'nationality_source': nat_source, 'prior_clubs_source': prior_source, 'wikipedia': url,
                         'national_teams': c.get('national_teams', []), 'apps_last10': c['apps_last10'], 'apps_recent': c['apps_recent']}}, None

def main():
    cands = json.load(open(WORK/'candidates.json')); links = json.load(open(WORK/'wikidata_links.json'))
    proposals = {}; reasons = collections.Counter()
    import sqlite3
    db = sqlite3.connect('file:/var/lib/clubdailyfive/player-wordle/game.sqlite3?mode=ro', uri=True)
    existing_names = {slug: {norm(n) for (n,) in db.execute('select name from players where club_id=?', (club['club_id'],))} for slug, club in cands.items()}
    for slug, club in cands.items():
        m = club['member']; club_norms = {norm(v) for v in (m['name'], m['team'], m.get('alias', '')) if v}
        need = max(0, TARGET - club['existing']); picked = []; seen = set()
        for c in club['candidates']:
            if len(picked) >= need: break
            if c['existing'] or (c['name'] and norm(c['name']) in seen): continue
            f, why = facts(c, m, club_norms, links)
            if not f: reasons[re.sub(r'\d+|\(.*', '', why).strip()] += 1; continue
            if norm(f['name']) in seen or norm(f['name']) in existing_names[slug]: continue
            seen.add(norm(f['name'])); picked.append(f)
        proposals[slug] = {'club_id': club['club_id'], 'existing': club['existing'], 'players': picked}
        print(f"{slug:26} existing {club['existing']:3} + new {len(picked):3} = {club['existing']+len(picked):3}   exact {sum(p['method']=='exact' for p in picked):3}  month {sum(p['method']=='month' for p in picked):3}  season {sum(p['method']=='season' for p in picked):3}")
    print('skipped:', dict(reasons))
    (WORK/'proposals.json').write_text(json.dumps(proposals, indent=1))

if __name__ == '__main__': main()
