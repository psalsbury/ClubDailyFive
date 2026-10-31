"""Matchday questions: the day after a club plays, ask about that match.

Source: ESPN's public scoreboard and match summary (scorers, minutes, lineups).
Every question is checked before use:
- the match is finished (full time, after extra time or after penalties),
- the goal events credited to each side add up to the final score,
- a named scorer is in their team's matchday squad,
- wrong answers are teammates from the same matchday squad who did not score.
"""
from __future__ import annotations
import datetime as dt, hashlib, json, os, re, time, urllib.request
from zoneinfo import ZoneInfo

UK = ZoneInfo('Europe/London')
CACHE = os.getenv('MATCHDAY_CACHE', '/var/lib/clubdailyfive/matchday-cache')
BASE = 'https://site.api.espn.com/apis/site/v2/sports/soccer'
# League first, then cups and Europe (competition name used in the question).
COMPETITIONS = [('eng.1', None), ('eng.2', None), ('eng.fa', 'FA Cup'), ('eng.league_cup', 'League Cup'),
                ('uefa.champions', 'Champions League'), ('uefa.europa', 'Europa League'), ('uefa.europa.conf', 'Conference League')]
ALIASES = {'afc bournemouth': 'bournemouth'}
FINISHED = {'STATUS_FULL_TIME', 'STATUS_FINAL', 'STATUS_FINAL_AET', 'STATUS_FINAL_PEN', 'STATUS_END_OF_EXTRATIME'}
UA = 'ClubDailyFive matchday questions'


def _get(url: str, max_age: int) -> dict:
    os.makedirs(CACHE, exist_ok=True)
    path = os.path.join(CACHE, hashlib.sha256(url.encode()).hexdigest() + '.json')
    if os.path.exists(path) and time.time() - os.path.getmtime(path) < max_age:
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    last = None
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept': 'application/json'})
            data = json.load(urllib.request.urlopen(req, timeout=30))
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f)
            return data
        except Exception as e:  # network blip: retry, then give up quietly
            last = e; time.sleep(3 * (attempt + 1))
    raise RuntimeError(f'ESPN unavailable: {last}')


def _norm(name: str) -> str:
    n = re.sub(r'[^a-z& ]', '', name.lower()).strip()
    return ALIASES.get(n, n)


def _uk_date(iso: str) -> str:
    return dt.datetime.fromisoformat(iso.replace('Z', '+00:00')).astimezone(UK).date().isoformat()


def _display_team(name: str, ours: dict) -> str:
    slug = ours.get(_norm(name))
    if slug:
        return slug[1]
    return re.sub(r'^(AFC|FC) |\s(AFC|FC)$', '', name).strip()


def load(target: str, clubs) -> dict:
    """{club slug: match} for clubs whose finished match kicked off (UK time) the day before `target`."""
    match_day = (dt.date.fromisoformat(target) - dt.timedelta(days=1)).isoformat()
    ours = {_norm(c['name']): (c['slug'], c['name']) for c in clubs}
    found = {}
    errors = []
    for league, cup in COMPETITIONS:
        events = []
        for d in {match_day, target}:  # ESPN groups by US date; late UK kickoffs can sit on the next date
            try:
                events += _get(f"{BASE}/{league}/scoreboard?dates={d.replace('-', '')}", 1800)['events']
            except Exception as e:
                errors.append(f'{league}: {e}')
        for e in events:
            comp = e['competitions'][0]
            if _uk_date(e['date']) != match_day or comp['status']['type']['name'] not in FINISHED:
                continue
            sides = comp['competitors']
            for side in sides:
                slug = ours.get(_norm(side['team']['displayName']))
                if not slug or slug[0] in found:
                    continue
                other = next(s for s in sides if s is not side)
                found[slug[0]] = {'event': e['id'], 'league': league, 'cup': cup, 'date': match_day, 'status': comp['status']['type']['name'],
                                  'club': slug[1], 'club_id': side['team']['id'], 'home': side.get('homeAway') == 'home',
                                  'opp': _display_team(other['team']['displayName'], ours), 'opp_id': other['team']['id'],
                                  'gf': int(side['score']), 'ga': int(other['score']), 'details': comp.get('details', [])}
    if errors and not found:
        raise RuntimeError('; '.join(errors))
    return found


def _goals(m: dict) -> list[dict]:
    out = []
    for x in m['details']:
        kind = x.get('type', {}).get('text', '')
        if not (x.get('scoringPlay') or re.search(r'goal|penalty - scored', kind, re.I)) or re.search(r'missed|saved|shootout', kind, re.I):
            continue
        who = [a.get('displayName') for a in x.get('athletesInvolved', [])]
        out.append({'team': x.get('team', {}).get('id'), 'own_goal': 'own goal' in kind.lower(), 'penalty': 'penalty' in kind.lower(),
                    'player': who[0] if who else None, 'clock': x.get('clock', {}).get('displayValue', ''), 'shootout': bool(x.get('shootout'))})
    return [g for g in out if not g['shootout']]


def _minute(clock: str) -> str:
    m = re.match(r"(\d+)'(?:\+(\d+)')?", clock or '')
    if not m:
        return ''
    base = int(m.group(1))
    if m.group(2):
        return 'in first-half stoppage time' if base == 45 else 'in stoppage time' if base == 90 else f"in the {_ord(base)} minute"
    return f'in the {_ord(base)} minute'


def _ord(n: int) -> str:
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def _squad(m: dict, team_id: str) -> list[tuple[str, bool, str]]:
    """[(name, starter, position)] for one side, from the match summary."""
    data = _get(f"{BASE}/{m['league']}/summary?event={m['event']}", 6 * 3600)
    for r in data.get('rosters', []):
        if str(r.get('team', {}).get('id')) == str(team_id):
            return [(p['athlete']['displayName'], bool(p.get('starter')), (p.get('position') or {}).get('abbreviation', ''))
                    for p in r.get('roster', []) if p.get('athlete', {}).get('displayName')]
    return []


def _pick(names: list[str], k: int, seed: str) -> list[str]:
    return sorted(names, key=lambda n: hashlib.sha256(f'{seed}|{n}'.encode()).hexdigest())[:k]


def _poss(name: str) -> str:
    return name + ("'" if name.endswith('s') else "'s")


def _venue(m: dict) -> str:
    return 'at home to' if m['home'] else 'away to'


def _result_phrase(m: dict) -> str:
    gf, ga = m['gf'], m['ga']
    if m['status'] == 'STATUS_FINAL_PEN':
        return f"{m['cup'] or 'cup'} tie {_venue(m)} {m['opp']}"  # level after extra time: not a "draw"
    word = 'win' if gf > ga else 'draw' if gf == ga else 'defeat'
    comp = f" in the {m['cup']}" if m['cup'] else ''
    return f"{gf}-{ga} {word} {_venue(m)} {m['opp']}{comp}"


def question(m: dict, seed: str) -> dict | None:
    """One verified question about this match, or None when nothing safe can be asked."""
    goals = _goals(m)
    mine = [g for g in goals if str(g['team']) == str(m['club_id'])]
    theirs = [g for g in goals if str(g['team']) == str(m['opp_id'])]
    if len(mine) != m['gf'] or len(theirs) != m['ga'] or any(not g['player'] for g in goals):
        return None  # incomplete or inconsistent event data: don't guess
    date = m['date']
    nice = dt.date.fromisoformat(date).strftime('%-d %B %Y')
    src = f"https://www.espn.co.uk/football/match/_/gameId/{m['event']}"
    pens = m['status'] == 'STATUS_FINAL_PEN'
    full = f"{m['club']} {m['gf']}-{m['ga']} {m['opp']}" + (' (after extra time)' if m['status'] == 'STATUS_FINAL_AET' else '') + (', decided on penalties' if pens else '')

    def scorer_q(side_goals, team_id, team, kind):
        scorers = [g['player'] for g in side_goals if not g['own_goal']]
        squad = _squad(m, team_id)
        names = {n for n, _, _ in squad}
        if not scorers or not squad or any(s not in names for s in scorers):
            return None
        counts = {s: scorers.count(s) for s in scorers}
        multi = [s for s, c in counts.items() if c >= 2]
        outfield = [n for n, st, pos in squad if pos != 'G' and n not in counts]
        starters = [n for n, st, pos in squad if st and pos != 'G' and n not in counts]
        pool = starters if len(starters) >= 3 else outfield
        if len(pool) < 3:
            return None
        if kind == 'mine' and len(multi) == 1:
            ans = multi[0]; c = counts[ans]
            text = f"Which {team} player scored {'a hat-trick' if c >= 3 else 'twice'} in the {_result_phrase(m)} on {nice}?"
            slot = 'brace'
            how = f"{ans} scored {c} goals."
        else:
            first = side_goals[0]
            if first['own_goal']:
                return None
            ans = first['player']
            if kind == 'mine':
                text = (f"Who scored {_poss(team)} goal in the {_result_phrase(m)} on {nice}?" if m['gf'] == 1
                        else f"Who scored {_poss(team)} first goal in the {_result_phrase(m)} on {nice}?")
            else:
                comp = f" in the {m['cup']}" if m['cup'] else ''
                text = f"Who scored first for {team} against {m['club']}{comp} on {nice}?"
            slot = 'first-scorer' if kind == 'mine' else 'opp-first-scorer'
            how = f"{ans} scored {_minute(first['clock'])}{' from the penalty spot' if first['penalty'] else ''}."
        wrong = _pick(pool, 3, f'{seed}|{slot}')
        opts = _pick([ans, *wrong], 4, f'{seed}|{slot}|order')
        return dict(text=text, options=opts, answer=opts.index(ans), explanation=f"{how} Full time: {full}.", source_url=src,
                    source_label='ESPN match report', key=f"matchday|{seed}|{date}|{slot}", fact_date=date)

    if m['gf'] > 0:
        q = scorer_q(mine, m['club_id'], m['club'], 'mine')
        if q:
            return q
    if m['ga'] > 0 and m['gf'] == 0:
        q = scorer_q(theirs, m['opp_id'], m['opp'], 'theirs')
        if q:
            return q
    if pens:
        return None  # a shoot-out makes "the score" ambiguous
    kind = f"{m['cup']} match" if m['cup'] else 'league match'
    return dict(text=f"What was the score for {m['club']} in their {kind} {_venue(m)} {m['opp']} on {nice}?",
                options=None, gf=m['gf'], ga=m['ga'], explanation=f"The score for {m['club']} was {m['gf']}-{m['ga']}. Full time: {full}.", source_url=src, source_label='ESPN match report',
                key=f"matchday|{seed}|{date}|score", fact_date=date)
