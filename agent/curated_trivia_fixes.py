#!/usr/bin/env python3
"""Reviewed rewrite of the hand-written club trivia (generic_trivia.json).

The original wrong answers were other clubs' answers reused across clubs (e.g. "Highbury / Dean Court /
Griffin Park" for every ground question) and year options always sat at -5/+3/+10. Every wrong answer below
was chosen to be the same kind of thing as the answer and checked not to be another true answer
(e.g. Arsenal's other statues, Bournemouth's MacDougall stand, Spurs' Wembley spell).

    curated_trivia_fixes.py [--install]   # rewrites generic_trivia.json and updates the stored questions
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from question_quality import clean_text, lint_question, numeric_options  # noqa: E402
from sterling import assert_sterling  # noqa: E402  (the nightly publisher refuses non-sterling wording)

TRIVIA = Path(__file__).resolve().parent / 'generic_trivia.json'
DB = os.getenv('QUIZ_DB', '/var/lib/clubdailyfive/clubquiz.sqlite')

# index -> new wrong answers (same type as the answer, none of them also true)
WRONG = {
    0: ['Royal Arsenal', 'Woolwich Town', 'Plumstead United'],
    1: ['Shipbuilding', 'Railway engineering', 'Brewing'],
    3: ['White Hart Lane', 'The Valley', 'Loftus Road'],
    5: ['Ian Wright', 'Patrick Vieira', 'Charlie George'],
    6: ['A sword', 'A musket', 'A crossbow'],
    7: ['Strength through unity', 'Forward together', 'Victory through courage'],
    8: ['Rugby', 'Rowing', 'Athletics'],
    10: ['A Catholic church', 'A Quaker meeting house', 'An Anglican cathedral'],
    12: ['Frederick Rinder', 'William McGregor', 'Randy Lerner'],
    13: ['A griffin', 'A stag', 'A bear'],
    16: ['Bournemouth Town', 'Pokesdown Athletic', 'Kings Park Rovers'],
    18: ['Bournemouth Athletic', 'Boscombe United', 'Bournemouth Town'],
    19: ['Kings Park', 'Boscombe Park', 'Victoria Park'],
    21: ['Eddie Howe', 'Brett Pitman', 'Matt Ritchie'],
    22: ['Ted MacDougall', 'Steve Fletcher', 'Eddie Howe'],
    23: ['Inter Milan', 'Genoa', 'Bologna'],
    25: ['Cricket', 'Hockey', 'Lacrosse'],
    27: ['Loftus Road', 'Craven Cottage', 'Brisbane Road'],
    29: ['Vitality', 'American Express', 'MKM'],
    30: ['A wasp', 'A dragonfly', 'A beetle'],
    34: ['Hove Athletic', 'Brighton Wanderers', 'Sussex Rovers'],
    35: ['Goldstone Ground', 'Priestfield Stadium', 'Hove Park'],
    37: ['Withdean Stadium', 'Goldstone Ground', 'Hove Stadium'],
    38: ['The Shrimpers', 'The Mariners', 'The Sharks'],
    40: ['Henry Norris', 'John Houlding', 'Frederick Rinder'],
    41: ['Queens Park Rangers', 'Brentford', 'Tottenham Hotspur'],
    44: ['Ken Bates', 'Brian Mears', 'Joe Mears'],
    45: ['Kerry Dixon', 'Bobby Tambling', 'Jimmy Greaves'],
    46: ['Tommy Docherty', 'Billy Birrell', 'David Calderhead'],
    47: ['A sword', 'A shield', 'A banner'],
    48: ['Filbert Street', 'St Andrew\'s', 'The Butts'],
    49: ['Jaguar Arena', 'Highfield Arena', 'Phoenix Arena'],
    51: ['George Curtis', 'Bobby Gould', 'John Sillett'],
    52: ['A horse', 'An ox', 'A camel'],
    53: ['An eagle', 'A falcon', 'A swan'],
    56: ['Porto', 'Sporting CP', 'Boavista'],
    57: ['Bert Head', 'Terry Venables', 'Steve Coppell'],
    58: ['The Festival of Britain', 'The 1908 Olympic Games', "Queen Victoria's Golden Jubilee"],
    60: ['Charlton Athletic', 'Millwall', 'Fulham'],
    62: ['The Crystals', 'The Exhibitioners', 'The Pensioners'],
    64: ['Everton Rovers', 'Anfield Athletic', "St Mary's"],
    67: ['Anfield', 'Prenton Park', 'Haig Avenue'],
    70: ['The Liver Building', "St George's Hall", 'The Albert Dock clock tower'],
    71: ['Strength through unity', 'Faith and endeavour', 'Onward and upward'],
    72: ["St Mary's", "St Luke's", "St John's"],
    74: ['The Lilywhites', 'The Riversiders', 'The Thames Men'],
    77: ['George Cohen', 'Jimmy Hill', 'Gordon Davies'],
    81: ['A lion', 'A panther', 'A leopard'],
    82: ['Orange and white', 'Yellow and blue', 'Gold and red'],
    86: ['Boothferry Park', 'Hull Arena', 'Humber Stadium'],
    91: ['Feyenoord', 'Anderlecht', '1. FC Köln'],
    93: ['Mick Mills', 'John Wark', 'Terry Butcher'],
    95: ['Christchurch Mansion', 'The Ancient House', 'Ipswich Town Hall'],
    96: ['Hunslet', 'Leeds Athletic', 'Holbeck'],
    98: ['Holbeck', 'Leeds Rugby Club', 'Hunslet'],
    99: ['Trevor Cherry', 'Gordon Strachan', 'Lucas Radebe'],       # Leeds captains without a statue
    100: ['Paul Reaney', 'Paul Madeley', 'Terry Cooper'],           # defenders, like the answer
    103: ['Blue and white', 'Green and gold', 'Red and white'],
    104: ['Liverpool Ramblers', 'Bootle', 'Liverpool Caledonians'],
    105: ['Henry Norris', 'Gus Mears', 'William McGregor'],
    108: ['Graeme Souness', 'Roy Evans', 'Phil Thompson'],          # also played for and managed Liverpool
    109: ['Joe Fagan', 'Kenny Dalglish', 'Tom Watson'],
    110: ['A phoenix', 'A griffin', 'A thunderbird'],
    111: ['An olive branch', 'A fish', 'A ribbon'],
    112: ["St Andrew's, Ancoats", "St Luke's, Cheetham", "St Mary's, Ardwick"],
    113: ['Gorton', 'West Gorton', 'Manchester Athletic'],
    115: ['Hyde Road', 'Belle Vue', 'Gigg Lane'],
    116: ['The 1996 European Championship', 'The 2012 Olympic Games', 'The 1991 World Student Games'],
    120: ['Manchester Central', 'Ardwick', 'Clayton United'],
    124: ['The Cathedral of Football', 'The Cauldron', 'The Fortress'],
    125: ['Duncan Edwards', 'Bryan Robson', 'Eric Cantona'],
    126: ['Wigan', 'Warrington', 'St Helens'],
    131: ['The Toon Temple', 'The Fortress of the North', 'The Castle'],
    132: ['Hughie Gallacher', 'Malcolm Macdonald', 'Bobby Moncur'],
    133: ['Les Ferdinand', 'Kevin Keegan', 'Peter Beardsley'],
    134: ['Griffins', 'Wyverns', 'Unicorns'],
    141: ['Beeston', 'Arnold', 'Carlton'],
    142: ['Brian Clough', 'Peter Taylor', 'Dave Mackay'],
    144: ['Shipbuilders', 'Miners', 'Glassmakers'],
    145: ['Tom Watson', 'Robert Turnbull', 'John Campbell'],
    147: ['Newcastle Road', 'Ayresome Park', 'Feethams'],
    149: ['Alan Brown', 'Lawrie McMenemy', 'Peter Reid'],
    150: ['Sunderland Minster', 'Roker Lighthouse', 'Hylton Castle'],
    151: ['Strength through unity', 'Ever onward', 'Forward with courage'],
    152: ['Henry Bolingbroke', 'Owain Glyndŵr', 'Richard Neville'],
    155: ['Northumberland Park', 'Brisbane Road', 'The Valley'],
    158: ['A pheasant', 'An eagle', 'A falcon'],
}
# Reworded so there is exactly one right answer, or to drop a detail that could not be confirmed.
PROMPTS = {
    29: "Which company's name does the stadium carry for sponsorship?",  # sponsor year not confirmed
    83: 'In which year did the club introduce its current badge?',      # source confirms the badge year only
    155: 'Which ground was the club\'s home for more than a century before its present stadium?',  # Wembley 2017-19 came in between
    17: 'In which year did the club adopt the "AFC" prefix in its name?',
    113: "What was the club's name immediately before it became Manchester City?",
    159: 'In which year was the "Tottenham Hotspur" wording removed from the crest?',
}
RETIRE = {102}  # Leeds shield year: Premier League says 1999, Wikipedia says adopted 1998 and amended 1999
COUNTS = {69: (90, 160)}  # Goodison years: not a calendar year


# The index numbers above refer to this original order; fixes are applied by key so file edits cannot shift them.
ORDER = [
"generic|arsenal|origins|names-0",
"generic|arsenal|origins|industries-1",
"generic|arsenal|origins|years-2",
"generic|arsenal|grounds|grounds-3",
"generic|arsenal|grounds|years-4",
"generic|arsenal|grounds|players-5",
"generic|arsenal|identity|symbols-6",
"generic|arsenal|identity|mottos-7",
"generic|aston-villa|origins|sports-0",
"generic|aston-villa|origins|years-1",
"generic|aston-villa|origins|institutions-2",
"generic|aston-villa|grounds|years-3",
"generic|aston-villa|grounds|people-4",
"generic|aston-villa|identity|animals-5",
"generic|aston-villa|identity|countries-6",
"generic|aston-villa|identity|years-7",
"generic|bournemouth|origins|names-0",
"generic|bournemouth|origins|years-1",
"generic|bournemouth|origins|names-2",
"generic|bournemouth|grounds|grounds-3",
"generic|bournemouth|grounds|years-4",
"generic|bournemouth|grounds|players-5",
"generic|bournemouth|identity|players-6",
"generic|bournemouth|identity|teams-7",
"generic|brentford|origins|years-0",
"generic|brentford|origins|sports-1",
"generic|brentford|origins|votes-2",
"generic|brentford|grounds|grounds-3",
"generic|brentford|grounds|years-4",
"generic|brentford|grounds|sponsors-5",
"generic|brentford|identity|animals-6",
"generic|brentford|identity|colleges-7",
"generic|brighton|origins|years-0",
"generic|brighton|origins|suffixes-1",
"generic|brighton|origins|names-2",
"generic|brighton|grounds|grounds-3",
"generic|brighton|grounds|years-4",
"generic|brighton|grounds|grounds-5",
"generic|brighton|identity|nicknames-6",
"generic|brighton|identity|years-7",
"generic|chelsea|origins|people-0",
"generic|chelsea|origins|teams-1",
"generic|chelsea|origins|venues-2",
"generic|chelsea|grounds|years-3",
"generic|chelsea|grounds|people-4",
"generic|chelsea|grounds|players-5",
"generic|chelsea|identity|managers-6",
"generic|chelsea|identity|symbols-7",
"generic|coventry-city|grounds|grounds-0",
"generic|coventry-city|grounds|grounds-1",
"generic|coventry-city|grounds|years-2",
"generic|coventry-city|grounds|people-3",
"generic|coventry-city|identity|animals-4",
"generic|coventry-city|identity|animals-5",
"generic|coventry-city|identity|people-6",
"generic|coventry-city|identity|saints-7",
"generic|crystal-palace|origins|teams-0",
"generic|crystal-palace|origins|managers-1",
"generic|crystal-palace|origins|events-2",
"generic|crystal-palace|grounds|years-3",
"generic|crystal-palace|grounds|teams-4",
"generic|crystal-palace|grounds|fictional-5",
"generic|crystal-palace|identity|nicknames-6",
"generic|crystal-palace|identity|years-7",
"generic|everton|origins|names-0",
"generic|everton|origins|years-1",
"generic|everton|origins|years-2",
"generic|everton|grounds|grounds-3",
"generic|everton|grounds|places-4",
"generic|everton|grounds|numbers-5",
"generic|everton|identity|landmarks-6",
"generic|everton|identity|mottos-7",
"generic|fulham|origins|churches-0",
"generic|fulham|origins|years-1",
"generic|fulham|origins|nicknames-2",
"generic|fulham|grounds|years-3",
"generic|fulham|grounds|rivers-4",
"generic|fulham|grounds|players-5",
"generic|fulham|identity|initials-6",
"generic|fulham|identity|years-7",
"generic|hull-city|identity|years-0",
"generic|hull-city|identity|animals-1",
"generic|hull-city|identity|colours-2",
"generic|hull-city|identity|years-3",
"generic|hull-city|grounds|years-4",
"generic|hull-city|grounds|rugby-5",
"generic|hull-city|grounds|grounds-6",
"generic|hull-city|grounds|years-7",
"generic|ipswich-town|origins|years-0",
"generic|ipswich-town|origins|sportsclubs-1",
"generic|ipswich-town|origins|years-2",
"generic|ipswich-town|origins|teams-3",
"generic|ipswich-town|grounds|years-4",
"generic|ipswich-town|grounds|players-5",
"generic|ipswich-town|identity|horses-6",
"generic|ipswich-town|identity|landmarks-7",
"generic|leeds-united|origins|names-0",
"generic|leeds-united|origins|years-1",
"generic|leeds-united|origins|teams-2",
"generic|leeds-united|grounds|players-3",
"generic|leeds-united|grounds|players-4",
"generic|leeds-united|identity|roses-5",
"generic|leeds-united|identity|years-6",
"generic|leeds-united|identity|colours-7",
"generic|liverpool|origins|teams-0",
"generic|liverpool|origins|people-1",
"generic|liverpool|origins|disputes-2",
"generic|liverpool|grounds|years-3",
"generic|liverpool|grounds|players-4",
"generic|liverpool|identity|managers-5",
"generic|liverpool|identity|animals-6",
"generic|liverpool|identity|symbols-7",
"generic|manchester-city|origins|churches-0",
"generic|manchester-city|origins|names-1",
"generic|manchester-city|origins|years-2",
"generic|manchester-city|grounds|grounds-3",
"generic|manchester-city|grounds|events-4",
"generic|manchester-city|grounds|years-5",
"generic|manchester-city|identity|counties-6",
"generic|manchester-city|identity|counts-7",
"generic|manchester-united|origins|names-0",
"generic|manchester-united|origins|years-1",
"generic|manchester-united|origins|railways-2",
"generic|manchester-united|grounds|years-3",
"generic|manchester-united|grounds|nicknames-4",
"generic|manchester-united|grounds|players-5",
"generic|manchester-united|identity|towns-6",
"generic|manchester-united|identity|words-7",
"generic|newcastle-united|origins|pairs-0",
"generic|newcastle-united|origins|years-1",
"generic|newcastle-united|origins|sportsclubs-2",
"generic|newcastle-united|grounds|nicknames-3",
"generic|newcastle-united|grounds|players-4",
"generic|newcastle-united|grounds|players-5",
"generic|newcastle-united|identity|animals-6",
"generic|newcastle-united|identity|flags-7",
"generic|nottingham-forest|origins|sports-0",
"generic|nottingham-forest|origins|years-1",
"generic|nottingham-forest|origins|places-2",
"generic|nottingham-forest|grounds|years-3",
"generic|nottingham-forest|grounds|rivers-4",
"generic|nottingham-forest|grounds|towns-5",
"generic|nottingham-forest|identity|people-6",
"generic|nottingham-forest|identity|honours-7",
"generic|sunderland|origins|industries-0",
"generic|sunderland|origins|people-1",
"generic|sunderland|origins|years-2",
"generic|sunderland|grounds|grounds-3",
"generic|sunderland|grounds|places-4",
"generic|sunderland|grounds|managers-5",
"generic|sunderland|identity|landmarks-6",
"generic|sunderland|identity|mottos-7",
"generic|tottenham-hotspur|origins|people-0",
"generic|tottenham-hotspur|origins|years-1",
"generic|tottenham-hotspur|origins|years-2",
"generic|tottenham-hotspur|grounds|grounds-3",
"generic|tottenham-hotspur|grounds|years-4",
"generic|tottenham-hotspur|grounds|stands-5",
"generic|tottenham-hotspur|identity|animals-6",
"generic|tottenham-hotspur|identity|years-7"
]
KEY_INDEX = {k: i for i, k in enumerate(ORDER)}


def year_options(answer: int, seed: str):
    """Wrong years 2-12 years away (one year off is often a season-boundary judgement call), never in the future,
    with the answer's position random."""
    hi = 2025 if answer <= 2025 else answer
    below = list(range(answer - 12, answer - 1))
    above = [y for y in range(answer + 2, answer + 13) if y <= hi]
    r = random.Random(hashlib.sha256((seed + '|years').encode()).digest())
    ranks = [k for k in range(4) if len(above) >= 3 - k]
    k = r.choice(ranks)
    years = r.sample(below, k) + [answer] + r.sample(above, 3 - k)
    opts = [str(y) for y in years]
    r.shuffle(opts)
    return opts, opts.index(str(answer))


def rebuild(items):
    out = []
    for x in items:
        x = dict(x)
        i = KEY_INDEX.get(x['key'], -1)
        if i in RETIRE:
            x['retired'] = True
            out.append(x); continue
        if i in PROMPTS:
            x['prompt'] = PROMPTS[i]
        answer = str(x['answer'])
        seed = 'curated|' + x['key']
        if i in COUNTS:
            lo, hi = COUNTS[i]
            opts, _ = numeric_options(int(answer), seed, lo, hi, spread=20)
            x['wrong'] = [o for o in opts if o != answer]
        elif answer.isdigit() and 1800 <= int(answer) <= 2100:
            opts, _ = year_options(int(answer), seed)
            x['wrong'] = [o for o in opts if o != answer]
        elif i in WRONG:
            x['wrong'] = WRONG[i]
        assert answer not in x['wrong'] and len(set(x['wrong'])) == 3, (i, x)
        out.append(x)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--install', action='store_true', help='update the stored questions')
    ap.add_argument('--write-json', action='store_true', help='also rewrite generic_trivia.json (needs write access to the code directory)')
    ap.add_argument('--nightly', action='store_true', help='quiet, never fails the job')
    a = ap.parse_args()
    if a.nightly:
        try:
            run(a)
        except Exception as e:
            print(f'Curated trivia update skipped ({type(e).__name__}: {e})')
        return
    run(a)


def run(a):
    items = json.loads(TRIVIA.read_text())
    fixed = rebuild(items)
    con = sqlite3.connect(DB, timeout=60); con.row_factory = sqlite3.Row
    names = dict(con.execute('select slug,name from clubs'))
    import datetime as dt
    from zoneinfo import ZoneInfo
    today = dt.datetime.now(ZoneInfo('Europe/London')).date().isoformat()
    live = {r[0] for r in con.execute('select question_id from daily_questions where quiz_date>=?', (today,))}
    updates, retire, show = [], [], []
    for x in fixed:
        row = con.execute('select * from questions where semantic_key=?', (x['key'],)).fetchone()
        if not row or row['id'] in live:
            continue  # leave questions in today's round alone; the nightly run picks them up tomorrow
        if x.get('retired'):
            retire.append(row['id']); continue
        opts = [str(x['answer']), *x['wrong']]
        random.Random(hashlib.sha256(('curated-order|' + x['key']).encode()).digest()).shuffle(opts)
        text = clean_text(f"{names[x['slug']]}: {x['prompt']}", names[x['slug']])
        new = dict(row); new.update(question_text=text, options_json=json.dumps(opts, ensure_ascii=False), correct_index=opts.index(str(x['answer'])))
        problems = lint_question(new)
        assert not problems, (text, problems)
        assert_sterling(new)
        updates.append(new); show.append((text, opts, str(x['answer'])))
    changed = [r for r in updates if (r['question_text'], r['options_json'], r['correct_index']) !=
               tuple(con.execute('select question_text,options_json,correct_index from questions where id=?', (r['id'],)).fetchone())]
    retire = [q for q in retire if con.execute('select status from questions where id=?', (q,)).fetchone()[0] != 'retired']
    print(f'Curated trivia: {len(changed)} questions rewritten, {len(retire)} retired')
    if not a.nightly:
        for t, o, ans in random.Random(3).sample(show, min(12, len(show))):
            print('-', t, '|', ' / '.join(o), '| ans:', ans)
    updates = changed
    if a.install:
        con.execute('begin immediate')
        for r in updates:
            h = hashlib.sha256((r['semantic_key'] + '|' + r['question_text']).encode()).hexdigest()
            con.execute('update questions set question_text=?,options_json=?,correct_index=?,content_hash=? where id=?',
                        (r['question_text'], r['options_json'], r['correct_index'], h, r['id']))
        for qid in retire:
            con.execute("update questions set status='retired' where id=?", (qid,))
        con.commit()
    if a.write_json:
        # Keep retired entries (flagged) so the file stays a complete record of the reviewed set.
        TRIVIA.write_text(json.dumps(fixed, ensure_ascii=False, indent=1))
        print('generic_trivia.json updated')


if __name__ == '__main__':
    main()
