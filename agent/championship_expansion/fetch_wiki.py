#!/usr/bin/env python3
"""Phase 2 (read-only on the game DB): fetch English Wikipedia articles for the candidates.

Articles are found through Wikidata by Transfermarkt player ID (P2446), so a namesake can never be
picked up. Pages come from the MediaWiki parse API (meant for bots), one request at a time, honouring
maxlag and Retry-After. HTML is cached in efl-cache/wiki-api keyed by title.
"""
import json, pathlib, time, urllib.parse, urllib.request, urllib.error, hashlib, sys
BASE = pathlib.Path('/var/lib/clubdailyfive')
CACHE = BASE/'efl-cache/wiki-api'
OLD_CACHE = BASE/'efl-cache/players'  # pages saved by the existing collector, keyed by /wiki/ URL
WORK = pathlib.Path('/var/lib/clubdailyfive/championship-expansion')
UA = 'ClubDailyFive/1.0 (https://clubdailyfive.com; admin@clubdailyfive.com) research-batch'
PER_CLUB = 135  # enough new candidates per club to reach ~100 after rejections

def get(url, accept='application/json'):
    for attempt in range(6):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept': accept})
            return urllib.request.urlopen(req, timeout=60).read()
        except urllib.error.HTTPError as e:
            if e.code in (429, 503):
                wait = int(e.headers.get('Retry-After') or 0) or 30 * (attempt + 1)
                print(f'  slowed down by server ({e.code}); waiting {wait}s', flush=True); time.sleep(wait); continue
            raise
        except urllib.error.URLError:
            time.sleep(10 * (attempt + 1))
    raise RuntimeError('gave up on ' + url)

def sitelinks(tm_ids):
    out = {}
    ids = sorted(tm_ids)
    for i in range(0, len(ids), 300):
        values = ' '.join('"%s"' % x for x in ids[i:i+300])
        q = '''SELECT ?tm ?item ?title ?dob WHERE { VALUES ?tm { %s } ?item wdt:P2446 ?tm.
          OPTIONAL { ?item wdt:P569 ?dob } OPTIONAL { ?a schema:about ?item; schema:isPartOf <https://en.wikipedia.org/>; schema:name ?title } }''' % values
        data = json.loads(get('https://query.wikidata.org/sparql?' + urllib.parse.urlencode({'query': q}), 'application/sparql-results+json'))
        for b in data['results']['bindings']:
            r = out.setdefault(b['tm']['value'], {'items': set(), 'titles': set(), 'dobs': set()})
            r['items'].add(b['item']['value'].rsplit('/', 1)[1])
            if 'title' in b: r['titles'].add(b['title']['value'])
            if 'dob' in b: r['dobs'].add(b['dob']['value'][:10])
        time.sleep(1)
    return {k: {'items': sorted(v['items']), 'titles': sorted(v['titles']), 'dobs': sorted(v['dobs'])} for k, v in out.items()}

def article(title):
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE/(hashlib.sha256(title.encode()).hexdigest() + '.html')
    if path.exists(): return path.read_text()
    old = OLD_CACHE/hashlib.sha256(('https://en.wikipedia.org/wiki/' + urllib.parse.quote(title.replace(' ', '_'))).encode()).hexdigest()
    if old.exists() and len(old.read_text()) > 1000:
        html = old.read_text()
    else:
        url = 'https://en.wikipedia.org/w/api.php?' + urllib.parse.urlencode({'action': 'parse', 'page': title, 'prop': 'text', 'format': 'json', 'formatversion': 2, 'redirects': 1, 'maxlag': 5})
        data = json.loads(get(url))
        if 'error' in data:
            if data['error'].get('code') == 'maxlag': time.sleep(10); return article(title)
            raise LookupError(data['error'].get('info'))
        html = data['parse']['text']
    path.write_text(html)
    return html

def main():
    cands = json.load(open(WORK/'candidates.json'))
    chosen = {}
    for slug, club in cands.items():
        new = [c for c in club['candidates'] if not c['existing']][:PER_CLUB]
        for c in new: chosen[c['profile']['player_id']] = c['name']
    print('candidates to look up:', len(chosen), flush=True)
    links_path = WORK/'wikidata_links.json'
    links = json.load(open(links_path)) if links_path.exists() else {}
    missing = set(chosen) - set(links)
    if missing:
        links.update(sitelinks(missing)); links_path.write_text(json.dumps(links))
    titles = {pid: links[pid]['titles'][0] for pid in chosen if pid in links and len(links[pid]['titles']) == 1}
    print('with an English Wikipedia article:', len(titles), flush=True)
    done = 0; failed = 0; t0 = time.time()
    for pid, title in titles.items():
        try: article(title)
        except Exception as e: failed += 1; print('  failed', title, type(e).__name__, e, flush=True)
        done += 1
        if done % 100 == 0: print(f'{done}/{len(titles)} fetched, {failed} failed, {time.time()-t0:.0f}s', flush=True)
    print(f'DONE {done} fetched, {failed} failed', flush=True)

if __name__ == '__main__': main()
