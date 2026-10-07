"""Managers and club legends for build_heritage_bank.py. Two records must agree on every fact used."""
from __future__ import annotations

import datetime as dt
import hashlib
import random
import re
import urllib.parse

import build_heritage_bank as hb
import wiki_tables as wt

FIELD = re.compile(r'\|\s*(years|clubs|caps|goals|manageryears|managerclubs)(\d+)\s*=')
MONTHS = {m: i for i, m in enumerate(('january', 'february', 'march', 'april', 'may', 'june', 'july', 'august',
                                       'september', 'october', 'november', 'december'), 1)}


def display(title):
    return re.sub(r'\s*\(.*?\)\s*$', '', title).strip()


def _strip(value):
    value = re.sub(r'<ref[^>]*/>|<ref[^>]*>.*?</ref>|<!--.*?-->', '', value, flags=re.S)
    value = re.sub(r'\{\{(?:nowrap|nobr)\|([^{}]*)\}\}', r'\1', value, flags=re.I)
    value = re.sub(r'\{\{[^{}]*\}\}', '', value)
    return value.strip()


def infobox_rows(wikitext):
    """{(kind, n): raw value} for the career rows of an infobox football biography."""
    box = wikitext[:20000]
    hits = list(FIELD.finditer(box))
    rows = {}
    for i, m in enumerate(hits):
        end = hits[i + 1].start() if i + 1 < len(hits) else len(box)
        raw = box[m.end():end]
        raw = re.split(r'\n\s*\||\n\}\}', raw)[0]
        rows[(m.group(1), int(m.group(2)))] = _strip(raw)
    return rows


def link_target(value):
    m = re.search(r'\[\[([^\]|#]+)', value)
    return m.group(1).strip() if m else value.strip()


def years(value):
    found = re.findall(r'(1[89]\d{2}|20\d{2})', value)
    if not found:
        return None
    start = int(found[0])
    if len(found) > 1:
        return start, int(found[1])
    return start, (None if re.search(r'[–-]\s*$|present', value, re.I) else start)


def number(value):
    m = re.match(r'^\(?\s*(\d+)', value.replace(',', ''))
    return int(m.group(1)) if m else None


def rank_pick(items, n, seed):
    items = list(items)
    random.Random(hashlib.sha256(seed.encode()).digest()).shuffle(items)
    return items[:n]


def shuffled(options, answer, seed):
    options = rank_pick(options, len(options), seed)
    return options, options.index(answer)


def parse_date(text):
    t = re.sub(r'\[.*?\]', '', text).strip().lower()
    if not t or 'present' in t:
        return None
    m = re.search(r'(\d{1,2})?\s*([a-z]+)?\s*(1[89]\d{2}|20\d{2})', t)
    if not m:
        return 'bad'
    month = MONTHS.get(m.group(2) or '', 0)
    try:
        return dt.date(int(m.group(3)), month or 1, int(m.group(1)) if m.group(1) and month else 1), bool(month)
    except ValueError:
        return 'bad'


# ------------------------------------------------------------------ managers

def person_link(cell):
    """The person's article in a name cell, skipping the flag link that often comes first."""
    text = hb.norm(cell['text'])
    for link in cell['links']:
        name = hb.norm(display(link))
        if name and name in text:
            return link
    return None


def club_managers(club):
    """Rows of the club's 'List of ... managers' page joined to each manager's infobox spell at the club."""
    title = f"List of {club['wiki']} managers"
    rows = []
    page = hb.wp_html(title)
    grids = wt.tables(page, css='')  # some lists use unstyled tables
    def has_record(g):
        return any(re.sub(r'\[.*?\]', '', c['text']).strip().lower() in ('m', 'p', 'g', 'gp', 'games', 'matches', 'played', 'pld') for row in g[:3] for c in row)
    need_record = any(has_record(g) for g in grids)
    for g in grids:
        span_col = False
        hi, idx = wt.header_index(g, 'manager', 'from', 'to')
        if hi is None:
            hi, idx = wt.header_index(g, 'name', 'from', 'to')
        if hi is None:
            hi, idx = wt.header_index(g, 'manager', 'years')
            span_col = hi is not None
        if hi is None:
            hi, idx = wt.header_index(g, 'name', 'tenure')
            span_col = hi is not None
        if hi is None:
            hi, idx = wt.header_index(g, 'name', 'years')
            span_col = hi is not None
        if hi is None:
            continue
        m_col = None
        for header in g[hi:hi + 3]:  # grouped headers put P/W/D/L on a second row
            heads = [re.sub(r'\[.*?\]', '', c['text']).strip().lower() for c in header]
            m_col = next((j for j, h in enumerate(heads) if h in ('m', 'p', 'g', 'gp', 'games', 'matches', 'played', 'pld')), None)
            if m_col is not None:
                break
        if m_col is None and need_record:
            continue  # assistant/coach tables carry no match record; only the managers table does
        for r in g[hi + 1:]:
            if len(r) <= max(idx):
                continue
            if span_col:
                y = years(r[idx[1]]['text'])
                person = person_link(r[idx[0]])
                if not y or not person:
                    continue
                links = [person]
                text = ' '.join(c['text'] for c in r).lower()
                rows.append({'title': links[0], 'name': display(links[0]), 'start': dt.date(y[0], 1, 1),
                             'end': dt.date(y[1], 1, 1) if y[1] else None, 'caretaker': bool(re.search(r'caretaker|interim|acting|joint', text)),
                             'matches': number(r[m_col]['text']) if m_col is not None and m_col < len(r) else None})
                continue
            person = person_link(r[idx[0]])
            if not person:
                continue
            links = [person]
            text = ' '.join(c['text'] for c in r).lower()
            caretaker = bool(re.search(r'caretaker|interim|acting|player-manager|joint|co-manager', text))
            start, end = parse_date(r[idx[1]]['text']), parse_date(r[idx[2]]['text'])
            if start == 'bad' or start is None or end == 'bad':
                continue
            matches = number(r[m_col]['text']) if m_col is not None and m_col < len(r) else None
            rows.append({'title': links[0], 'name': display(links[0]), 'start': start[0],
                         'end': end[0] if end else None, 'caretaker': caretaker, 'matches': matches})
    prose = {}
    if not rows:
        rows, prose = prose_managers(page)
    if not rows:
        return [], title
    boxes = hb.wp_wikitext({r['title'] for r in rows})
    for r in rows:
        box = infobox_rows(boxes.get(r['title'], ''))
        spells = []
        for (kind, n), value in box.items():
            if kind != 'managerclubs':
                continue
            target = link_target(value)
            if not (target == club['wiki'] or hb.same_club(target, club['wiki'])) or re.search(r'caretaker|interim|assistant|coach|youth|reserve|under-|women|u\d\d', value, re.I):
                continue
            y = years(box.get(('manageryears', n), ''))
            if y:
                spells.append(y)
        if r.get('from_prose'):
            # Prose lists: the infobox spell supplies the years; the list's own section must state them.
            section = prose.get(r['title'], '')
            match = next(((s, e) for s, e in spells if str(s) in section and (e is None or str(e) in section)), None)
            r['verified'] = bool(match) and not re.search(r'caretaker', section[:200], re.I)
            if match:
                r['start'] = dt.date(match[0], 1, 1); r['end'] = dt.date(match[1], 1, 1) if match[1] else None
            continue
        end_year = r['end'].year if r['end'] else None
        r['verified'] = any(s == r['start'].year and e == end_year for s, e in spells)
    return [r for r in rows if r['start']], title


def prose_managers(page):
    """Lists written as one section per manager (e.g. West Ham): heading = manager, section text = their spell."""
    rows, sections = [], {}
    parts = re.split(r'<div class="mw-heading mw-heading3">(.*?)</div>', page, flags=re.S)
    for heading, body in zip(parts[1::2], parts[2::2]):
        links = re.findall(r'href="/wiki/([^"#]+)"', heading)
        h3 = re.search(r'<h3[^>]*>(.*?)</h3>', heading, re.S)
        name = re.sub(r'<[^>]+>', '', h3.group(1) if h3 else heading).strip()
        text = re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', body))
        link = urllib.parse.unquote(links[0]).replace('_', ' ') if links else None
        if not link:
            body_links = [urllib.parse.unquote(l).replace('_', ' ') for l in re.findall(r'href="/wiki/([^"#:]+)"', body)]
            link = next((l for l in body_links if hb.norm(display(l)) == hb.norm(name)), None)
        if not link or not re.search(r'appoint|manager', text, re.I):
            continue
        sections[link] = text
        rows.append({'title': link, 'name': display(link), 'start': None, 'end': None, 'caretaker': False,
                     'matches': None, 'from_prose': True})
    return rows, sections


def managers_questions(clubs, sparql, wp_wikitext, wins_by_club=None):
    out, report = [], {'clubs': 0, 'managers_listed': 0, 'managers_verified': 0}
    for slug, club in clubs.items():
        try:
            rows, list_title = club_managers(club)
        except Exception as e:  # source outage: skip this club tonight
            report.setdefault('errors', []).append(f'{slug}: {e}')
            continue
        report['clubs'] += 1
        report['managers_listed'] += len(rows)
        good = [r for r in rows if r['verified'] and not r['caretaker']]
        report['managers_verified'] += len(good)
        src = 'https://en.wikipedia.org/wiki/' + urllib.parse.quote(list_title.replace(' ', '_'))
        name = club['name']
        starts = {}
        for r in rows:
            starts.setdefault(r['start'].year, []).append(r)
        # A. Who was appointed in year Y (only when exactly one appointment of any kind that year).
        for r in good:
            y = r['start'].year
            if len(starts[y]) != 1 or y > 2025:
                continue
            others = [o for o in good if o['title'] != r['title'] and 3 <= abs(o['start'].year - y) <= 30
                      and not (o['start'].year <= y <= (o['end'].year if o['end'] else 9999))]
            names = sorted({o['name'] for o in others} - {r['name']})
            if len(names) < 3:
                continue
            distract = rank_pick(names, 3, f'{slug}|{y}|appointed')
            opts, idx = shuffled([r['name'], *distract], r['name'], f'{slug}|{y}|appointed|order')
            until = f" and stayed until {r['end'].year}" if r['end'] else ''
            out.append(dict(club=club, family='managers', key=f'appointed|{y}|{hb.norm(r["name"])}', fact_date=None, src=src,
                            text=f"Who was appointed {name} manager in {y}?", options=(opts, idx),
                            explanation=f"{r['name']} was appointed {name} manager in {y}{until}."))
        # B. Manager when a verified trophy was won (spell must cover the whole calendar year in both records).
        for comp, final_name, y in (wins_by_club or {}).get(slug, []):
            holders = [r for r in rows if r['start'].year < y and (r['end'] is None or r['end'].year > y)]
            if len(holders) != 1 or holders[0] not in good:
                continue
            r = holders[0]
            names = sorted({o['name'] for o in good if o['title'] != r['title'] and abs(o['start'].year - y) <= 35} - {r['name']})
            if len(names) < 3:
                continue
            distract = rank_pick(names, 3, f'{slug}|{y}|{comp}|boss')
            opts, idx = shuffled([r['name'], *distract], r['name'], f'{slug}|{y}|{comp}|boss|order')
            out.append(dict(club=club, family='honours', key=f'trophy-manager|{comp}|{y}', fact_date=None, src=src,
                            text=f"Who was {name}'s manager when they won the {final_name}?", options=(opts, idx),
                            explanation=f"{r['name']} was in charge ({r['start'].year}–{r['end'].year if r['end'] else 'present'}) when {name} won the {final_name}."))
        # C. Most matches in charge (all spells added up), with a clear margin that the tenures also support.
        people = {}
        for r in rows:
            p = people.setdefault(r['title'], {'title': r['title'], 'name': r['name'], 'matches': 0, 'years': 0, 'complete': True, 'spells': []})
            p['complete'] &= bool(r['matches']) and r['end'] is not None and r['end'].year <= 2025 and (r['verified'] or r['caretaker'])
            p['matches'] += r['matches'] or 0
            p['years'] += ((r['end'] or dt.date(2026, 1, 1)) - r['start']).days / 365.25
            p['spells'].append(r)
        verified_people = {r['title'] for r in good}
        counted = sorted([p for p in people.values() if p['complete'] and p['title'] in verified_people], key=lambda p: -p['matches'])
        made = 0
        for top in counted[:6]:
            top['start'] = min(r['start'] for r in top['spells']); top['end'] = max(r['end'] for r in top['spells'])
            pool = sorted({o['name'] for o in counted if o['matches'] * 1.5 <= top['matches'] and o['years'] < top['years']} - {top['name']})
            if len(pool) < 3:
                continue
            distract = rank_pick(pool, 3, f'{slug}|{top["title"]}|matches')
            opts, idx = shuffled([top['name'], *distract], top['name'], f'{slug}|{top["title"]}|matches|order')
            out.append(dict(club=club, family='managers', key=f'most-matches|{hb.norm(top["name"])}|{"-".join(sorted(map(hb.norm, distract)))}',
                            fact_date=None, src=src, text=f"Which of these managers took charge of the most matches for {name}?",
                            options=(opts, idx), explanation=f"{top['name']} managed {name} in {top['matches']} matches" + (f" across {len(top['spells'])} spells" if len(top['spells']) > 1 else '') + f" ({top['start'].year}–{top['end'].year})."))
            made += 1
            if made >= 3:
                break
    return out, report


# ------------------------------------------------------------------ legends

def club_legends(club, sparql, wp_wikitext):
    title = club['wiki'].replace('"', '\\"')
    rows = sparql(f'''SELECT ?ptitle ?apps ?goals ?start ?end WHERE {{
      ?cart schema:about ?club; schema:isPartOf <https://en.wikipedia.org/>; schema:name "{title}"@en.
      ?p p:P54 ?st. ?st ps:P54 ?club; pq:P1350 ?apps. OPTIONAL{{?st pq:P1351 ?goals}} OPTIONAL{{?st pq:P580 ?start}} OPTIONAL{{?st pq:P582 ?end}}
      FILTER(?apps >= 60)
      ?part schema:about ?p; schema:isPartOf <https://en.wikipedia.org/>; schema:name ?ptitle. }}''')
    by_player = {}
    for r in rows:
        by_player.setdefault(r['ptitle']['value'], []).append(r)
    cands = {}
    for p, spells in by_player.items():
        if len(spells) != 1:
            continue  # several spells: totals are ambiguous
        s = spells[0]
        if 'goals' not in s or 'start' not in s or 'end' not in s:
            continue
        if not all(re.match(r'^\d{4}', s[k]['value']) for k in ('start', 'end')) or not re.match(r'^[\d.]+$', s['goals']['value'] + s['apps']['value']):
            continue  # Wikidata "unknown value" placeholders
        end = int(s['end']['value'][:4])
        if end > 2024:
            continue  # recent spell: numbers may still be revised
        cands[p] = {'title': p, 'name': display(p), 'apps': int(float(s['apps']['value'])), 'goals': int(float(s['goals']['value'])),
                    'start': int(s['start']['value'][:4]), 'end': end}
    boxes = wp_wikitext(list(cands))
    verified = []
    for p, c in cands.items():
        box = infobox_rows(boxes.get(p, ''))
        matches = []
        for (kind, n), value in box.items():
            if kind != 'clubs' or '→' in value or 'loan' in value.lower():
                continue
            target = link_target(value)
            if target == club['wiki'] or hb.same_club(target, club['wiki']):
                matches.append(n)
        if len(matches) != 1:
            continue
        n = matches[0]
        caps, goals = number(box.get(('caps', n), '')), number(box.get(('goals', n), ''))
        span = years(box.get(('years', n), ''))
        if caps == c['apps'] and goals == c['goals'] and span == (c['start'], c['end']):
            verified.append(c)
    # Two players can share a display name; drop both rather than risk ambiguity.
    names = [c['name'] for c in verified]
    return [c for c in verified if names.count(c['name']) == 1], len(cands)


def legends_questions(clubs, sparql, wp_wikitext):
    out, report = [], {'clubs': 0, 'candidates': 0, 'verified': 0}
    for slug, club in clubs.items():
        try:
            legends, n = club_legends(club, sparql, wp_wikitext)
        except Exception as e:
            report.setdefault('errors', []).append(f'{slug}: {e}')
            continue
        report['clubs'] += 1; report['candidates'] += n; report['verified'] += len(legends)
        name = club['name']
        src = 'https://en.wikipedia.org/wiki/' + urllib.parse.quote(club['wiki'].replace(' ', '_'))
        for stat, word, ratio, minimum in (('goals', 'scored the most league goals', 1.25, 15), ('apps', 'made the most league appearances', 1.15, 100)):
            ordered = sorted(legends, key=lambda c: -c[stat])
            made = 0
            for top in ordered[:8]:
                if top[stat] < minimum:
                    break
                pool = [c for c in legends if c['title'] != top['title'] and c[stat] * ratio <= top[stat] and c['apps'] >= 100]
                pool.sort(key=lambda c: abs(c['start'] - top['start']))  # same era, so it is not just "the famous one"
                names = sorted({c['name'] for c in pool[:10]} - {top['name']})
                if len(names) < 3:
                    continue
                distract = rank_pick(names, 3, f'{slug}|{top["title"]}|{stat}')
                opts, idx = shuffled([top['name'], *distract], top['name'], f'{slug}|{top["title"]}|{stat}|order')
                out.append(dict(club=club, family='legends', key=f'most-{stat}|{hb.norm(top["name"])}', fact_date=None, src=src,
                                text=f"Which of these players {word} for {name}?", options=(opts, idx),
                                explanation=f"{top['name']} made {top['apps']} league appearances and scored {top['goals']} league goals for {name} ({top['start']}–{top['end']})."))
                made += 1
                if made >= 3:
                    break
        for c in sorted([c for c in legends if c['apps'] >= 150], key=lambda c: -c['apps'])[:6]:
            pool = sorted({o['name'] for o in legends if o['title'] != c['title'] and (o['start'], o['end']) != (c['start'], c['end'])
                           and abs(o['start'] - c['start']) <= 15 and o['apps'] >= 100} - {c['name']})
            if len(pool) < 3:
                continue
            distract = rank_pick(pool, 3, f'{slug}|{c["title"]}|spell')
            opts, idx = shuffled([c['name'], *distract], c['name'], f'{slug}|{c["title"]}|spell|order')
            out.append(dict(club=club, family='legends', key=f'spell|{hb.norm(c["name"])}', fact_date=None, src=src,
                            text=f"Which player made {c['apps']} league appearances for {name} between {c['start']} and {c['end']}?",
                            options=(opts, idx), explanation=f"{c['name']} played {c['apps']} league games for {name} from {c['start']} to {c['end']}, scoring {c['goals']}."))
    return out, report
