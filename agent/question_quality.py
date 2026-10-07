"""Question quality: fair answer options, consistent wording and a publish-time lint.

Everything here is deterministic (seeded) so the nightly normaliser is idempotent.
"""
from __future__ import annotations

import hashlib
import json
import random
import re

MONTHS = ('January', 'February', 'March', 'April', 'May', 'June', 'July', 'August',
          'September', 'October', 'November', 'December')
SHORT_MONTHS = {m[:3]: i + 1 for i, m in enumerate(MONTHS)}

# Filler that the old bank builder prepended to pad 300 questions per club.
PREFIX_RE = re.compile(r"^(?:Looking back through the club records|Club history challenge|From the recorded "
                       r"statistics|Archive question|Another one from the club record|Club record question \d+): ")

# Data-feed abbreviations and dataset suffixes -> the name supporters use.
TEAM_NAMES = {
    "Arsenal FC": "Arsenal", "AFC Bournemouth": "Bournemouth", "Barnsley FC": "Barnsley", "Blackpool FC": "Blackpool",
    "Brentford FC": "Brentford", "Burnley FC": "Burnley", "Chelsea FC": "Chelsea", "Everton FC": "Everton",
    "Fulham FC": "Fulham", "Liverpool FC": "Liverpool", "Middlesbrough FC": "Middlesbrough", "Millwall FC": "Millwall",
    "Port Vale FC": "Port Vale", "Portsmouth FC": "Portsmouth", "Reading FC": "Reading", "Southampton FC": "Southampton",
    "Stevenage FC": "Stevenage", "Sunderland AFC": "Sunderland", "Watford FC": "Watford", "Wrexham AFC": "Wrexham",
    "Buxton FC": "Buxton", "Macclesfield FC": "Macclesfield", "Rangers FC": "Rangers",
    "Man City": "Manchester City", "Man United": "Manchester United", "Nott'm Forest": "Nottingham Forest",
    "Sheffield Weds": "Sheffield Wednesday", "Wolves": "Wolverhampton Wanderers", "West Brom": "West Bromwich Albion",
    "West Ham": "West Ham United", "Tottenham": "Tottenham Hotspur", "Newcastle": "Newcastle United",
    "Leeds": "Leeds United", "Leicester": "Leicester City", "Luton": "Luton Town", "Norwich": "Norwich City",
    "Ipswich": "Ipswich Town", "Hull": "Hull City", "Coventry": "Coventry City", "Cardiff": "Cardiff City",
    "Birmingham": "Birmingham City", "Blackburn": "Blackburn Rovers", "Bolton": "Bolton Wanderers",
    "Brighton": "Brighton & Hove Albion", "Bristol Rvs": "Bristol Rovers", "Derby": "Derby County",
    "Doncaster": "Doncaster Rovers", "Exeter": "Exeter City", "Huddersfield": "Huddersfield Town",
    "Mansfield": "Mansfield Town", "Oxford": "Oxford United", "Peterboro": "Peterborough United",
    "Plymouth": "Plymouth Argyle", "Preston": "Preston North End", "QPR": "Queens Park Rangers",
    "Rotherham": "Rotherham United", "Stoke": "Stoke City", "Swansea": "Swansea City", "Wigan": "Wigan Athletic",
    "Accrington": "Accrington Stanley", "Bradford": "Bradford City", "Burton": "Burton Albion",
    "Cambridge": "Cambridge United", "Carlisle": "Carlisle United", "Cheltenham": "Cheltenham Town",
    "Colchester": "Colchester United", "Crewe": "Crewe Alexandra", "Forest Green": "Forest Green Rovers",
    "Grimsby": "Grimsby Town", "Harrogate": "Harrogate Town", "Hartlepool": "Hartlepool United",
    "Lincoln": "Lincoln City", "Northampton": "Northampton Town", "Oldham": "Oldham Athletic",
    "Salford": "Salford City", "Scunthorpe": "Scunthorpe United", "Shrewsbury": "Shrewsbury Town",
    "Southend": "Southend United", "Stockport": "Stockport County", "Sutton": "Sutton United",
    "Swindon": "Swindon Town", "Torquay": "Torquay United", "Tranmere": "Tranmere Rovers",
    "Wycombe": "Wycombe Wanderers", "Yeovil": "Yeovil Town", "York": "York City", "Halifax": "FC Halifax Town",
    "Maidstone": "Maidstone United", "Dorking": "Dorking Wanderers", "Solihull": "Solihull Moors",
    "Maidenhead": "Maidenhead United", "Milton Keynes Dons": "MK Dons",
    "Bologna Football Club 1909": "Bologna", "Olympiakos Syndesmos Filathlon Peiraios": "Olympiacos",
    "Fotballklubben Bodø/Glimt": "Bodø/Glimt", "Ajax Amsterdam": "Ajax", "FC Twente Enschede": "FC Twente",
    "Juventus FC": "Juventus", "Sevilla FC": "Sevilla", "Villarreal CF": "Villarreal", "Girona FC": "Girona",
    "FC Barcelona": "Barcelona", "Atlético de Madrid": "Atlético Madrid", "Real Betis Balompié": "Real Betis",
    "GNK Dinamo Zagreb": "Dinamo Zagreb", "Ferencvárosi TC": "Ferencváros", "LOSC Lille": "Lille",
    "Club Brugge KV": "Club Brugge", "FC Shakhtar Donetsk": "Shakhtar Donetsk", "SSC Napoli": "Napoli",
    "Qarabağ FK": "Qarabağ", "Legia Warszawa": "Legia Warsaw", "AC Sparta Prague": "Sparta Prague",
    "SL Benfica": "Benfica", "Olympique Lyon": "Lyon", "Olympique Marseille": "Marseille",
    "S.L. Benfica": "Benfica", "A.S. Roma": "Roma", "Olympique de Marseille": "Marseille", "FC Dnipro": "Dnipro",
    "CSA Steaua București": "Steaua București", "FC Porto": "Porto", "FC Bayern Munich": "Bayern Munich",
    "Borussia Mönchengladbach": "Borussia Mönchengladbach", "Hamburger SV": "Hamburg", "Juventus F.C.": "Juventus",
}
# Abbreviations that can never be part of a person's name: safe to rewrite anywhere in question text.
UNAMBIGUOUS = [k for k in TEAM_NAMES if re.search(r"\b(?:FC|AFC|CF|KV|TC|FK)\b|'|Man |Weds|Rvs|Peterboro|QPR|West Brom|Wolves|Nott|Milton Keynes|1909|Syndesmos|Fotballklubben|Balompié|Warszawa|Enschede", k)]
CANONICAL = set(TEAM_NAMES.values())
# Longest-first so "Newcastle United" is consumed whole and never becomes "Newcastle United United".
_TEAM_ALT = '|'.join(sorted(map(re.escape, set(TEAM_NAMES) | CANONICAL), key=len, reverse=True))
TEAM_TOKEN = re.compile(r"(?<![\w'])(" + _TEAM_ALT + r")(?![\w'])")
UNAMBIGUOUS_TOKEN = re.compile(r"(?<![\w'])(" + '|'.join(sorted(map(re.escape, set(UNAMBIGUOUS) | CANONICAL), key=len, reverse=True)) + r")(?![\w'])")
SCORE_OPTION = re.compile(r"^(?:(.+?) )?(\d+)-(\d+)(?: (.+))?$")


def team(name: str) -> str:
    return TEAM_NAMES.get(name.strip(), name.strip())


def teams_in(text: str, pattern=TEAM_TOKEN) -> str:
    return pattern.sub(lambda m: TEAM_NAMES.get(m.group(1), m.group(1)), text)


def long_date(day: int, month: int, year: int) -> str:
    return f"{day} {MONTHS[month - 1]} {year}"


def clean_text(text: str, club: str | None = None) -> str:
    """Presentation clean-up; never changes a fact."""
    text = PREFIX_RE.sub('', text)
    # 19-Sep-2026 / 2026-09-19 -> 19 September 2026
    text = re.sub(r"\b(\d{1,2})-(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)-(\d{4})\b",
                  lambda m: long_date(int(m.group(1)), SHORT_MONTHS[m.group(2)], int(m.group(3))), text)
    text = re.sub(r"(?<![\w/:.-])(\d{4})-(\d{2})-(\d{2})(?![\w-])",
                  lambda m: long_date(int(m.group(3)), int(m.group(2)), int(m.group(1))), text)
    # 24/25 -> 2024-25 (only consecutive two-digit seasons)
    text = re.sub(r"(?<![\d/])(\d{2})/(\d{2})(?![\d/])",
                  lambda m: f"20{m.group(1)}-{m.group(2)}" if (int(m.group(1)) + 1) % 100 == int(m.group(2)) else m.group(0), text)
    # Attendance-sized numbers get thousands separators.
    if re.search(r'attendance', text, re.I):
        text = re.sub(r"(?<![\d,.£-])(\d{4,6})(?![\d,-]|\.\d)", lambda m: f"{int(m.group(1)):,}" if int(m.group(1)) >= 1000 and not 1850 <= int(m.group(1)) <= 2100 else m.group(1), text)
    text = teams_in(text, UNAMBIGUOUS_TOKEN)
    text = re.sub(r"(\d+-\d+) ((?:[A-Z][\w'&.-]*(?: (?:&|[A-Z][\w'.-]*))*))", lambda m: f"{m.group(1)} {teams_in(m.group(2))}", text)
    # Team names that follow match wording ("away to Luton", "knocked out by Hull") are safe to expand.
    text = re.sub(r"\b(against|away to|at home to|by|play|beat|lose to|lost to|draw with|drew with|finished) ((?:[A-Z][\w'&.-]*(?: (?:&|[A-Z][\w'.-]*))*))",
                  lambda m: f"{m.group(1)} {teams_in(m.group(2))}", text)
    if club:
        text = text.replace(f"former {club} player ", f"{club} player ")
        prefix = f"{club}: "
        if text.startswith(prefix) and re.search(r"\bthe club\b", text):
            body = text[len(prefix):]
            body = re.sub(r"\bthe club's\b", f"{club}'s", body)
            body = re.sub(r"\bthe club\b", club, body)
            text = body[0].upper() + body[1:]
    return re.sub(r'\s{2,}', ' ', text).strip()


def clean_option(value: str) -> str:
    value = clean_text(str(value))
    m = SCORE_OPTION.match(value)
    if m and (m.group(1) or m.group(4)):
        return f"{team(m.group(1) or '')} {m.group(2)}-{m.group(3)} {team(m.group(4) or '')}".strip()
    return team(value)


def _rng(seed: str) -> random.Random:
    return random.Random(hashlib.sha256(seed.encode('utf-8')).digest())


def _rank_choice(seed: str, ranks: list[int], weights=(1, 1, 1, 1)) -> int:
    return _rng(seed + '|rank').choices(ranks, [weights[r] for r in ranks])[0]


# Small counts often sit on their lower bound (0 yellow cards, a 1-match run), which forces the answer to be the
# lowest option. Favouring higher positions when there is a choice keeps the bank-wide position close to uniform
# (measured on the live bank: 25/23/27/25%).
NUMERIC_RANK_WEIGHTS = (1, 1.5, 3, 4)


def numeric_options(answer: int, seed: str, lo: int = 0, hi: int | None = None, spread: int | None = None):
    """Four integers where the answer's position among them is uniformly random.

    ``lo``/``hi`` keep every distractor possible (e.g. never more league games than a season has),
    so nothing can be ruled out by common sense alone.
    """
    answer = int(answer)
    spread = spread or max(3, round(abs(answer) * 0.15))
    below = [v for v in range(answer - spread, answer) if v >= lo]
    above = [v for v in range(answer + 1, answer + spread + 1) if hi is None or v <= hi]
    ranks = [r for r in range(4) if len(below) >= r and len(above) >= 3 - r]
    if not ranks:
        raise ValueError(f'No fair options for {answer} in [{lo}, {hi}]')
    rank = _rank_choice(seed, ranks, NUMERIC_RANK_WEIGHTS)
    r = _rng(seed)
    chosen = sorted(r.sample(below, rank)) + [answer] + sorted(r.sample(above, 3 - rank))
    r.shuffle(chosen)
    return [str(v) for v in chosen], chosen.index(answer)


def _score_dist(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def score_options(home: int, away: int, seed: str, outcome: str | None = None, min_total: int = 0):
    """Scorelines near the real one with no positional giveaway.

    ``outcome`` keeps the result type the question already reveals ('H', 'A' or 'D' = home win, away win, draw)
    and ``min_total`` keeps "high-scoring" honest. The answer is never the unique option that sits closest to
    all the others, which was how the old options could be solved without knowing the match.
    """
    ans = (int(home), int(away))
    def ok(s):
        if s == ans or min(s) < 0 or sum(s) < min_total:
            return False
        if outcome == 'H': return s[0] > s[1]
        if outcome == 'A': return s[1] > s[0]
        if outcome == 'D': return s[0] == s[1]
        return True
    pool = [(h, a) for h in range(0, ans[0] + 4) for a in range(0, ans[1] + 4) if ok((h, a)) and 1 <= _score_dist((h, a), ans) <= 3]
    r = _rng(seed)
    for _ in range(400):
        if len(pool) < 3:
            break
        picks = r.sample(pool, 3)
        opts = [ans, *picks]
        totals = [sum(_score_dist(o, p) for p in opts) for o in opts]
        if totals.count(min(totals)) == 1 and totals[0] == min(totals):
            continue  # answer would be the unique "middle" scoreline
        r.shuffle(opts)
        return opts, opts.index(ans)
    raise ValueError(f'No fair score options for {ans}')


def fee_options(answer_m: float, seed: str):
    """Transfer fees in £m: distractors at least 20% apart so 'approximately' stays fair."""
    factors_below = [0.45, 0.55, 0.66, 0.8]
    factors_above = [1.25, 1.5, 1.8, 2.2]
    ranks = [0, 1, 2, 3]
    rank = _rank_choice(seed, ranks)
    r = _rng(seed)
    below = sorted(r.sample(factors_below, rank), reverse=True)
    above = sorted(r.sample(factors_above, 3 - rank))
    values = [answer_m * f for f in below] + [answer_m] + [answer_m * f for f in above]
    values = sorted(values)
    for a, b in zip(values, values[1:]):
        if b < a * 1.15:
            raise ValueError('fee options too close')
    labels = [fee_label(v) for v in values]
    correct = fee_label(answer_m)
    if len(set(labels)) != 4:
        raise ValueError('fee labels collide')
    r.shuffle(labels)
    return labels, labels.index(correct)


def fee_label(value_m: float) -> str:
    return f"£{value_m * 1000:,.0f}k" if value_m < 1 else f"£{value_m:.1f}m"


def parse_fee(label: str) -> float | None:
    m = re.fullmatch(r'£(\d[\d,]*(?:\.\d+)?)(m|k)', str(label).strip())
    if not m:
        return None
    value = float(m.group(1).replace(',', ''))
    return value if m.group(2) == 'm' else value / 1000


CUP_ROUNDS = {
    'fa': ['First round', 'Second round', 'Third round', 'Fourth round', 'Fifth round', 'Quarter-finals', 'Semi-finals', 'Final'],
    'league': ['First round', 'Second round', 'Third round', 'Fourth round', 'Quarter-finals', 'Semi-finals', 'Final'],
    'europe': ['Group stage', 'Knockout round play-offs', 'Round of 16', 'Quarter-finals', 'Semi-finals', 'Final'],
}
ORDINALS = {'1st': 'First', '2nd': 'Second', '3rd': 'Third', '4th': 'Fourth', '5th': 'Fifth'}


def cup_round(label: str, competition: str = 'europe') -> str:
    """Dataset round labels (legs, replays, group letters) -> one supporter-facing name."""
    t = re.sub(r'\s+(?:1st|2nd)\s+leg$|\s+replay$', '', label.strip(), flags=re.I)
    t = re.sub(r'^(\d(?:st|nd|rd|th)) round deciders$', lambda m: ORDINALS[m.group(1)] + ' round', t, flags=re.I)
    low = t.lower()
    if low.startswith('group'): return 'Group stage'
    if low.startswith('intermediate stage'): return 'Knockout round play-offs'
    if low in ('last 16', 'round of 16'):
        return {'fa': 'Fifth round', 'league': 'Fourth round'}.get(competition, 'Round of 16')
    if low.startswith('quarter'): return 'Quarter-finals'
    if low.startswith('semi'): return 'Semi-finals'
    if low == 'final': return 'Final'
    return t[:1].upper() + t[1:].lower()


def round_options(answer_label: str, competition: str, seed: str, lowest: str | None = None):
    rounds = CUP_ROUNDS[competition]
    answer = cup_round(answer_label, competition)
    if answer not in rounds:
        raise ValueError('unknown round ' + answer_label)
    i = rounds.index(answer)
    lo = min(i, rounds.index(lowest)) if lowest in rounds else 0
    starts = [st for st in range(lo, len(rounds) - 3) if st <= i < st + 4]
    if not starts:
        raise ValueError('not enough rounds')
    st = _rng(seed + '|rank').choice(starts)
    opts = rounds[st:st + 4]
    _rng(seed).shuffle(opts)
    return opts, opts.index(answer)


def attendance_options(answer: int, seed: str, highest: bool | None = None):
    """Attendances with commas and varied digits; the answer's rank is random.

    For a season's *highest* crowd, distractors above it stay within 6% (a ground cannot be much bigger than
    its best crowd); for the *lowest*, distractors below stay within 25%.
    """
    answer = int(answer)
    r = _rng(seed)
    up = 0.06 if highest else 0.2
    down = 0.25 if highest is False else 0.2
    gap = max(400, round(answer * 0.025))
    below = [answer - round(answer * f) for f in (r.uniform(0.02, down * 0.33), r.uniform(down * 0.36, down * 0.66), r.uniform(down * 0.7, down))]
    above = [answer + round(answer * f) for f in (r.uniform(0.012, up * 0.33), r.uniform(up * 0.36, up * 0.66), r.uniform(up * 0.7, up))]
    rank = _rank_choice(seed, [0, 1, 2, 3])
    values = sorted(below[:rank]) + [answer] + above[:3 - rank]
    values = sorted(values)
    if any(b - a < gap for a, b in zip(values, values[1:])) or min(values) <= 0:
        # Fall back to wider fixed spacing that is always distinct.
        values = sorted([answer - gap * 2 * k for k in range(1, rank + 1)] + [answer] + [answer + gap * 2 * k for k in range(1, 4 - rank)])
    labels = [f"{v:,}" for v in values]
    r.shuffle(labels)
    return labels, labels.index(f"{answer:,}")


# ---------------------------------------------------------------- lint

SHORT_DATE = re.compile(r"\b\d{1,2}-(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)-\d{4}\b|\b\d{4}-\d{2}-\d{2}\b")
SLASH_SEASON = re.compile(r"(?<![\d/])\d{2}/\d{2}(?![\d/])")
RETIRED_FAMILIES = (
    re.compile(r"which (?:team|side).*?(?:scored first|first to score|opening goal|first goal)", re.I),
    re.compile(r"^In which half was the first goal scored", re.I),
    re.compile(r"^How many red cards did .+ receive against", re.I),
)


def lint_question(row) -> list[str]:
    """Problems that must keep a question out of a round."""
    row = dict(row)
    problems = []
    text = row['question_text']
    try:
        opts = json.loads(row['options_json'])
        answer = opts[int(row['correct_index'])]
    except (ValueError, IndexError, TypeError, KeyError):
        return ['options unreadable or answer index invalid']
    if len(opts) != 4 or len({str(o).casefold() for o in opts}) != 4:
        problems.append('needs four distinct options')
    if PREFIX_RE.search(text): problems.append('filler prefix')
    if SHORT_DATE.search(text) or any(SHORT_DATE.search(str(o)) for o in opts): problems.append('unformatted date')
    if SLASH_SEASON.search(text): problems.append('slash season')
    for name in UNAMBIGUOUS:
        if re.search(r"(?<![\w'])" + re.escape(name) + r"(?![\w'])", text + ' | ' + ' | '.join(map(str, opts))):
            problems.append(f'abbreviated team name: {name}')
            break
    if any(p.search(text) for p in RETIRED_FAMILIES): problems.append('retired question family')
    if any(re.search(r'deciders|\b(?:1st|2nd) leg\b|replay|^Group [A-H]$', str(o), re.I) for o in opts):
        problems.append('raw cup round label')
    if re.search(r'attendance', text, re.I) and any(re.fullmatch(r'\d{4,6}', str(o)) for o in opts):
        problems.append('attendance without thousands separator')
    if not (row.get('explanation') or '').strip() or not (row.get('source_url') or '').strip():
        problems.append('missing explanation or source')
    scores = [SCORE_OPTION.match(str(o)) for o in opts]
    scores = [m if m and len(m.group(2)) <= 2 and len(m.group(3)) <= 2 else None for m in scores]  # not seasons like 1987-88
    if all(scores) and all(re.search(r'\d+-\d+', str(o)) for o in opts):
        pts = [(int(m.group(2)), int(m.group(3))) for m in scores]
        totals = [sum(_score_dist(a, b) for b in pts) for a in pts]
        ai = int(row['correct_index'])
        if totals.count(min(totals)) == 1 and totals[ai] == min(totals):
            problems.append('answer is the middle scoreline')
        if re.search(r'knocked out|\bcup\b', text, re.I) and 'league match' not in text and min(pts[ai]) >= 4 and abs(pts[ai][0] - pts[ai][1]) == 1:
            problems.append('cup score looks like a penalty shoot-out total')
    fees = [parse_fee(o) for o in opts]
    if any(f is not None for f in fees) and not all(f is not None for f in fees):
        problems.append('transfer fee options in mixed formats')
    if all(f is not None for f in fees):
        vals = sorted(fees)
        if any(b < a * 1.15 for a, b in zip(vals, vals[1:])):
            problems.append('transfer fee options too close together')
    if re.search(r'knocked .* out|were knocked out', text, re.I) and all(scores):
        pts = [(int(m.group(2)), int(m.group(3))) for m in scores]
        if any(a == b for a, b in pts): problems.append('knockout question offers a draw')
    return problems


def numeric_rank_report(rows) -> dict:
    """Across many integer questions, how often is the answer the lowest/highest option?"""
    ranks = [0, 0, 0, 0]
    for row in rows:
        row = dict(row)
        try:
            opts = json.loads(row['options_json'])
            vals = [int(str(o).replace(',', '')) for o in opts]
        except (ValueError, TypeError):
            continue
        if len(set(vals)) != 4:
            continue
        ranks[sorted(vals).index(vals[int(row['correct_index'])])] += 1
    total = sum(ranks) or 1
    return {'questions': sum(ranks), 'answer_rank_share': [round(r / total, 2) for r in ranks]}
