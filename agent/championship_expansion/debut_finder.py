"""Find a player's first competitive game for a club from Wikipedia prose, cross-checked with fixture lists.

Fixture lists are football-data.co.uk league CSVs (Premier League to National League, 1993/94 on), cached in
efl-cache/football-data. Every result must fall inside the player's first season with appearances for the
club in the Transfermarkt season data (the "window"); anything ambiguous returns nothing.
"""
import csv, datetime as dt, pathlib, re, unicodedata
from source_utils import clean

FD = pathlib.Path('/var/lib/clubdailyfive/efl-cache/football-data')
MONTHS = 'January|February|March|April|May|June|July|August|September|October|November|December'
NUM = {'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10}
# football-data short names -> how Wikipedia writes them
ALIASES = {'Wolves': ['Wolverhampton Wanderers', 'Wolves'], 'QPR': ['Queens Park Rangers', 'QPR'], 'Man United': ['Manchester United'],
           'Man City': ['Manchester City'], "Nott'm Forest": ['Nottingham Forest'], 'Sheffield Weds': ['Sheffield Wednesday'],
           'West Brom': ['West Bromwich Albion', 'West Brom'], 'MK Dons': ['Milton Keynes Dons', 'MK Dons'], 'Bristol Rvs': ['Bristol Rovers'],
           'Peterboro': ['Peterborough United', 'Peterborough'], 'AFC Wimbledon': ['AFC Wimbledon'], 'Wimbledon': ['Wimbledon'],
           'Tottenham': ['Tottenham Hotspur', 'Tottenham', 'Spurs'], 'Brighton': ['Brighton & Hove Albion', 'Brighton and Hove Albion', 'Brighton'],
           'Dag and Red': ['Dagenham & Redbridge', 'Dagenham and Redbridge'], 'Accrington': ['Accrington Stanley'], 'Scunthorpe': ['Scunthorpe United'],
           'Sutton': ['Sutton United'], 'Yeovil': ['Yeovil Town'], 'Forest Green': ['Forest Green Rovers'], 'Leyton Orient': ['Leyton Orient', 'Orient']}
LEAGUE = re.compile(r'^(Premier League|Championship|League One|League Two|First Division|Second Division|Third Division|Division (One|Two|Three)|National League|Conference( National| Premier)?|Football League.*)$')

def norm(s):
    s = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode().lower()
    s = re.sub(r'\b(?:afc|fc|football club)\b', '', s)
    return re.sub('[^a-z0-9]', '', s)

def _date(s):
    for f in ('%d/%m/%Y', '%d/%m/%y'):
        try: return dt.datetime.strptime(s, f).date()
        except ValueError: pass

_fixtures = None
def fixtures():
    global _fixtures
    if _fixtures is None:
        _fixtures = []
        for p in sorted(FD.glob('*.csv')):
            with open(p, encoding='latin-1') as f:
                for r in csv.DictReader(f):
                    try:
                        d = _date(r.get('Date', '')); hg, ag = int(r['FTHG']), int(r['FTAG'])
                    except (KeyError, ValueError, TypeError): continue
                    if d and r.get('HomeTeam') and r.get('AwayTeam'): _fixtures.append((d, r['HomeTeam'].strip(), r['AwayTeam'].strip(), hg, ag))
    return _fixtures

def forms(fd_name):
    return ALIASES.get(fd_name, [fd_name])

def is_club(fd_name, club_names):
    return any(norm(club).startswith(norm(f)) or norm(f) == norm(club) for f in forms(fd_name) for club in club_names)

def club_games(club_names, window):
    """League games for the club in the window: (date, opponent, home, goals_for, goals_against)."""
    out = []
    for d, h, a, hg, ag in fixtures():
        if not window[0] <= d <= window[1]: continue
        if is_club(h, club_names): out.append((d, a, True, hg, ag))
        elif is_club(a, club_names): out.append((d, h, False, ag, hg))
    return sorted(out)

def mentions(sentence, fd_name):
    return any(re.search(r'(?<![\w-])' + re.escape(f) + r'(?![\w-])', sentence) for f in forms(fd_name))

def resolve_match(sentence, games):
    """A league game identified by opponent, score, result and venue, if exactly one fits."""
    pool = [g for g in games if mentions(sentence, g[1])]
    low = sentence.lower()
    score = re.search(r'\b(\d{1,2})\s*[–-]\s*(\d{1,2})\b', sentence)
    if score:
        a, b = int(score[1]), int(score[2])
        pool = [g for g in pool if {g[3], g[4]} == {a, b} or (g[3], g[4]) in ((a, b), (b, a))]
        if re.search(r'\b(win|won|victory|beat|beating|triumph)\b', low): pool = [g for g in pool if g[3] > g[4]]
        elif re.search(r'\b(defeat|loss|lost|losing|beaten)\b', low): pool = [g for g in pool if g[3] < g[4]]
        elif re.search(r'\b(draw|drew|drawn|stalemate)\b', low): pool = [g for g in pool if g[3] == g[4]]
    if re.search(r'\b(at home|home (?:win|defeat|draw|game|match|loss|victory)|home to)\b', low): pool = [g for g in pool if g[2]]
    elif re.search(r'\b(away (?:at|to|win|defeat|draw|game|match|loss|victory)|away from home)\b', low): pool = [g for g in pool if not g[2]]
    return pool[0][0] if len(pool) == 1 else None

COMPETITION_WORDS = re.compile(r'^(premier league|football league|efl|english football league|championship|league|league one|league two|fa cup|efl cup|league cup|professional|senior|first[- ]team|competitive|full|home|away|club)$', re.I)
OPPONENT_BEFORE = re.compile(r'(against|to|over|v|vs|versus|draw with|drew with|by|at|from|beat|beating|hosted|hosting|visit(?:ing)?)\W+(?:the\W+)?$', re.I)

def club_terms(member):
    terms = {member['name'], member['team'], member.get('alias', ''), member['name'].removesuffix(' City').removesuffix(' Town').removesuffix(' United').removesuffix(' Rovers').removesuffix(' Athletic').removesuffix(' Wanderers').removesuffix(' Albion')}
    nick = (member.get('facts') or {}).get('nickname', '')
    terms |= {n.strip().removeprefix('The ').removeprefix('the ') for n in re.split(r',|/|\bor\b|\band\b|;', nick)}
    return {t for t in terms if len(t) > 3}

def owner_ok(sentence, heading, terms):
    """True when the debut described is for our club: any club the sentence names as the debut club must be ours,
    and our club must not appear only as the opponent."""
    ours = lambda x: any(norm(x) == norm(t) or norm(x).startswith(norm(t)) or norm(t).startswith(norm(x)) for t in terms)
    named = re.findall(r"debut (?:for|with) (?:the )?([A-Z][\w'’.&-]*(?: (?:&|and|[A-Z][\w'’.&-]*)){0,4})", sentence)
    named += re.findall(r"(?:his|her|a) ([A-Z][\w'’.&-]*(?: [A-Z][\w'’.&-]*){0,3}) debut", sentence)
    named = [n for n in named if not COMPETITION_WORDS.match(n.strip()) and not COMPETITION_WORDS.match(n.split()[-1])]
    if named: return all(ours(n) for n in named)
    for t in terms:
        for m in re.finditer(re.escape(t), sentence, re.I):
            if not OPPONENT_BEFORE.search(sentence[max(0, m.start() - 30):m.start()]): return True
    deepest = heading.rsplit(' > ', 1)[-1]
    if re.search(r'\bloan', sentence + ' ' + deepest, re.I): return False
    # The nearest heading naming a club must be ours (e.g. "West Ham United > 2015–2020", not "West Ham United > Aston Villa").
    return any(t.lower() in heading for t in terms) and not (re.search(r'[a-z]{4,}', deepest) and not any(t.lower() in deepest for t in terms) and not re.search(r'^(?:\d{4}.\d{2,4}(?:: .*)?|\d{4}.*season.*|early (life|career)|club career|career|youth career|senior career|professional career|first spell|return.*|later career|.*season)$', deepest))

BOUNDARY = re.compile(r';\s|,? and (?=(?:he |she |then |later |went |scored|netted|got|was |kept|made his first|registered|claimed))|,? (?:before|but|while|whereas) (?=\w)|\. ')

def debut_clause(sentence):
    """The part of a sentence that describes the debut, so a goal or transfer date elsewhere in it is ignored."""
    parts = BOUNDARY.split(sentence)
    for i, part in enumerate(parts):
        if 'debut' in part.lower():
            # Keep a leading "On 2 August 2025," clause attached to the debut.
            lead = parts[i - 1] if i and re.match(r'^(on|in) ', parts[i - 1].strip(), re.I) and 'debut' not in parts[i - 1].lower() else ''
            return (lead + ' ' + part).strip()
    return sentence

def find_debut(raw, member, window, first_season_comps, games):
    """Returns (date, precision, evidence) with precision 'day' or 'month', or (None, None, None)."""
    aliases = {member['name'].lower(), member['team'].lower(), member['name'].lower().removesuffix(' city').removesuffix(' town').removesuffix(' united').removesuffix(' rovers').removesuffix(' athletic').removesuffix(' wanderers').removesuffix(' albion')}
    aliases = {a for a in aliases if len(a) > 3}
    league_only = bool(first_season_comps) and all(LEAGUE.match(c) or 'Play-Off' in c or 'Playoff' in c for c in first_season_comps)
    S = window[0].year
    terms = club_terms(member)
    found = []
    heading = ''; levels = {}
    for chunk in re.findall(r'<h[234]\b[^>]*>.*?</h[234]>|<p\b[^>]*>.*?</p>', raw, re.S):
        text = clean(chunk)
        if chunk.startswith('<h'):
            # Keep the chain of section headings ("West Ham United" > "2015–2020") as context.
            level = int(chunk[2]); levels[level] = text.lower()
            for deeper in [l for l in levels if l > level]: del levels[deeper]
            heading = ' > '.join(levels[l] for l in sorted(levels)); continue
        sentences = re.split(r'(?<=[.!?])\s+(?=[A-Z])', text)
        for i, sentence in enumerate(sentences):
            low = sentence.lower()
            if 'debut' not in low: continue
            if not owner_ok(sentence, heading, terms): continue
            full_sentence, sentence = sentence, debut_clause(sentence); low = sentence.lower()
            at = low.find('debut'); near = low[max(0, at - 25):at + 45]
            if re.search(r'international|national team|under-?\d\d|\bu-?\d\d|youth|reserve|academy|development|\bb team|friendly|testimonial|pre-?season|second debut|second spell|season debut', near): continue
            league_debut = bool(re.search(r'\b(league|premier league|championship|football league|efl) debut', low))
            if league_debut and not league_only and not re.search(r'(first|opening) (match|game|league game|fixture) of the (\d{4}.\d{2,4} )?season|opening day', low): continue
            full = re.findall(r'\b(\d{1,2} (?:' + MONTHS + r') (?:19|20)\d{2})\b', sentence) + [f'{d} {m} {y}' for m, d, y in re.findall(r'\b(' + MONTHS + r') (\d{1,2}), ((?:19|20)\d{2})\b', sentence)]
            daymonth = re.findall(r'\b(\d{1,2}) (' + MONTHS + r')\b(?! (?:19|20)\d{2})', sentence) + [(d, m) for m, d in re.findall(r'\b(' + MONTHS + r') (\d{1,2})\b(?!,? (?:19|20)\d{2})', sentence)]
            monthyear = re.findall(r'\b(?:in|during) (' + MONTHS + r') ((?:19|20)\d{2})\b', sentence, re.I)
            full += [dt.date(int(y), int(mo), int(d)).strftime('%-d %B %Y') for d, mo, y in re.findall(r'\b(\d{1,2})/(\d{1,2})/((?:19|20)\d{2})\b', sentence) if 1 <= int(mo) <= 12 and 1 <= int(d) <= 31]
            cand = None
            # A season named in the clause ("the 2012–13 season") must be the player's first season at the club.
            named_seasons = {int(y) for y in re.findall(r'\b((?:19|20)\d{2})[–-](?:\d{2}|\d{4})\b', sentence)}
            season_ok = not named_seasons or named_seasons == {S}
            if len(full) == 1 and not daymonth:
                cand = (dt.datetime.strptime(full[0], '%d %B %Y').date(), 'day', 'stated date')
            elif len(daymonth) == 1 and not full:
                d, m = daymonth[0]; month = dt.datetime.strptime(m, '%B').month
                cand = (dt.date(S if month >= 7 else S + 1, month, int(d)), 'day', 'stated day and month; year from first season at the club')
            elif not full and not daymonth:
                later = re.search(r'\b(' + '|'.join(NUM) + r') days? later\b|\b(next|following) day\b', low)
                prev = re.findall(r'\b(\d{1,2} (?:' + MONTHS + r') (?:19|20)\d{2})\b', ' '.join(sentences[:i])) if later else []
                if later and len(prev) >= 1:
                    base = dt.datetime.strptime(prev[-1], '%d %B %Y').date()
                    cand = (base + dt.timedelta(days=NUM.get(later[1], 1) if later[1] else 1), 'day', 'counted from the previous stated date')
                elif season_ok and re.search(r'opening (day|game|match|fixture)|first (game|match|league game|league match|fixture) of the (?:\d{4}\S* )?(?:[a-z][\w ]*? )?season|season opener', low) and games:
                    cand = (games[0][0], 'day', 'opening league game of the season (football-data.co.uk)')
                elif season_ok and re.search(r'(final|last) (day|game|match|league game|round of matches) of the (?:\d{4}\S* )?(?:[a-z][\w ]*? )?season', low) and games:
                    cand = (games[-1][0], 'day', 'final league game of the season (football-data.co.uk)')
                elif games and (d := resolve_match(sentence, games)):
                    cand = (d, 'day', 'league game identified by opponent/score (football-data.co.uk)')
                elif len(monthyear) == 1:
                    m, y = monthyear[0]
                    cand = (dt.date(int(y), dt.datetime.strptime(m, '%B').month, 1), 'month', 'stated month and year')
            if not cand: continue
            date, precision, how = cand
            # The opponent and score named in the debut clause must not point to a different league game.
            named_game = resolve_match(sentence, games) if games and 'football-data' not in how else None
            if named_game and precision == 'day' and abs((named_game - date).days) > 1: continue
            # "signed on 9 August and made his debut the following day" / "... debut two days later"
            later = re.search(r'\b(' + '|'.join(NUM) + r') days? later\b|\b(next|following) day\b', low)
            date_at = re.search(r'\d{1,2} (?:' + MONTHS + r')|(?:' + MONTHS + r') \d{1,2}', sentence)
            if later and precision == 'day' and how.startswith('stated') and date_at and later.start() > date_at.start():
                date = date + dt.timedelta(days=NUM.get(later[1], 1) if later[1] else 1); how += ' plus the stated gap'
            if precision == 'day' and not window[0] <= date <= window[1]: continue
            if precision == 'month' and not (window[0].replace(day=1) <= date <= window[1]): continue
            # A league-only first season means the debut was a league game: the date must be one of the club's fixtures.
            if precision == 'day' and league_only and games and not any(abs((g[0] - date).days) <= 1 for g in games): continue
            confirmed = any(g[0] == date for g in games)
            found.append((date, precision, how + ('; matches a league fixture' if confirmed and 'football-data' not in how else '') + ': ' + full_sentence))
    if not found: return None, None, None
    days = [f for f in found if f[1] == 'day']
    best = min(days or found, key=lambda f: f[0])
    return best
