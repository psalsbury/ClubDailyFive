"""Keep Daily Five rounds focused on recent football.

A question is "old" when the most recent year it is about is more than
ERA_YEARS before the round date. Old questions stay in the bank but are not
picked, unless they are about something really significant:

- a trophy the club won (league titles, cups, European trophies, finals won),
- an all-time club record (most appearances, goals or matches managed),
- timeless club identity facts (founded, ground, nickname, origins, crest...).

This is a selection filter, not a retirement, so weekly bank rebuilds cannot
undo it and the cut-off moves forward every year on its own.
"""
from __future__ import annotations
import csv, os, re
from functools import lru_cache

ERA_YEARS = 15
PERFORMANCES = '/var/lib/clubdailyfive/player-sources/performances.csv'
YEAR = re.compile(r'(?<![\d£$€.,])(18[5-9]\d|19\d\d|20[0-4]\d)(?:[-–/](\d{2,4}))?(?![\d])')
TROPHY = re.compile(r'\b(title|champions|championship|cup|trophy|shield|final|european|league one|league two|division)\b', re.I)
WON = re.compile(r'\b(won|win|wins|winning|beat|lifted)\b', re.I)
TIMELESS_GENERIC = {'founded', 'ground', 'nickname', 'full_name', 'identity', 'origins', 'grounds'}
AMBIGUOUS_FIRST = {'sheffield', 'manchester', 'bristol', 'west', 'queens', 'aston', 'crystal', 'nottingham', 'preston', 'wolverhampton'}


def _years(text: str) -> list[int]:
    out = []
    for m in YEAR.finditer(text or ''):
        y = int(m.group(1)); out.append(y)
        tail = m.group(2)
        if tail:
            end = int(tail) if len(tail) == 4 else (y // 100) * 100 + int(tail)
            if len(tail) == 2 and end < y: end += 100
            if 0 <= end - y <= 2: out.append(end)
    return out


def _club_words(name: str) -> list[str]:
    words = [w for w in re.sub(r'[^a-z ]', ' ', name.lower()).split() if w not in {'fc', 'afc', 'and'}]
    return words[:2] if words and words[0] in AMBIGUOUS_FIRST else words[:1]


@lru_cache(maxsize=1)
def _player_seasons() -> dict[str, dict[str, int]]:
    """player_id -> {team name lower: last season start year} from Transfermarkt performance data."""
    out: dict[str, dict[str, int]] = {}
    if not os.path.exists(PERFORMANCES):
        return out
    with open(PERFORMANCES, encoding='utf-8', newline='') as f:
        reader = csv.reader(f)
        head = next(reader)
        pi, si, ti = head.index('player_id'), head.index('season_name'), head.index('team_name')
        for r in reader:
            season = r[si]
            if len(season) != 5 or season[2] != '/':
                continue
            yy = int(season[:2]); year = 2000 + yy if yy < 50 else 1900 + yy
            teams = out.setdefault(r[pi], {}); team = r[ti].lower()
            if teams.get(team, 0) < year:
                teams[team] = year
    return out


def _player_last_year(player_id: str, club_name: str) -> int | None:
    words = _club_words(club_name)
    years = [y for team, y in _player_seasons().get(player_id, {}).items() if all(w in team for w in words)]
    return max(years) + 1 if years else None


def latest_year(q, club_name: str = '') -> int | None:
    """The most recent calendar year a question is about (None when it is timeless or unknown)."""
    key = q['semantic_key'] or ''
    parts = key.split('|')
    if key.startswith('generic|') and len(parts) > 3 and parts[2] == 'player-birth':
        return _player_last_year(parts[3], club_name)
    if '|player_biography|' in key and parts[-1].startswith('birth-'):
        # A birth year says nothing about when the player was at the club.
        return _player_last_year(parts[-1][6:], club_name)
    years = _years(q['question_text']) + _years(q['explanation'] or '')
    if q['fact_date']:
        years += _years(q['fact_date'][:4])
    if key.startswith('heritage|'):
        years += [int(p) for p in parts if re.fullmatch(r'(18|19|20)\d\d', p)]
    return max(years) if years else None


def significant(q) -> bool:
    """Trophies won and all-time club records stay in whatever their age."""
    key = q['semantic_key'] or ''
    parts = key.split('|')
    text = q['question_text'] or ''
    if key.startswith('generic|'):
        return len(parts) > 2 and parts[2] in TIMELESS_GENERIC
    if key.startswith('heritage|'):
        if len(parts) > 3 and ((parts[2] == 'legends' and parts[3] in ('most-apps', 'most-goals')) or (parts[2] == 'managers' and parts[3] == 'most-matches')):
            return True
        if len(parts) > 2 and parts[2] == 'honours':
            tail = parts[-1]
            if tail in ('won', 'first') or tail.startswith('count'):
                return True
            if tail == 'final':
                # "Who did X beat in the final?" is a trophy; "Who beat X in the final?" is a defeat.
                return not re.match(r'\s*who beat\b', text, re.I)
            return bool(WON.search(text) and TROPHY.search(text)) and not re.match(r'\s*who beat\b', text, re.I)
        if 'manager' in text.lower() and re.search(r'\bwhen they won\b', text, re.I):
            return True
        return False
    return bool(re.search(r'\bwhen they won\b|\bwon the\b|\bwin the\b', text, re.I) and TROPHY.search(text))


def cutoff_year(target: str) -> int:
    return int(target[:4]) - ERA_YEARS


def recent_enough(q, target: str, club_name: str = '') -> bool:
    """True when a question may be used in a round for `target` (YYYY-MM-DD)."""
    year = latest_year(q, club_name)
    if year is None or year >= cutoff_year(target):
        return True
    return significant(q)


def is_old(q, target: str, club_name: str = '') -> bool:
    year = latest_year(q, club_name)
    return year is not None and year < cutoff_year(target)


def one_old_at_most(bank, target: str, club_name: str = ''):
    """Keep bank order but allow only the first older (pre-cut-off) question, so a round has at most one."""
    out, seen = [], False
    for q in bank:
        if is_old(q, target, club_name):
            if seen:
                continue
            seen = True
        out.append(q)
    return out
