"""Day-precision start dates of each candidate's spell(s) at the club, from Wikidata (P54 member of sports team, P580 start time)."""
import json, pathlib, time, urllib.parse
from fetch_wiki import get
WORK = pathlib.Path('/var/lib/clubdailyfive/championship-expansion')
cands = json.load(open(WORK/'candidates.json'))
club_titles = {c['member']['wiki']: slug for slug, c in cands.items()}
ids = sorted({c['profile']['player_id'] for club in cands.values() for c in club['candidates'][:200]})
out = {}
for i in range(0, len(ids), 300):
    values = ' '.join('"%s"' % x for x in ids[i:i+300])
    q = '''SELECT ?tm ?title ?start WHERE { VALUES ?tm { %s } ?p wdt:P2446 ?tm; p:P54 ?st. ?st ps:P54 ?team; pqv:P580 ?sv.
      ?sv wikibase:timeValue ?start; wikibase:timePrecision 11 .
      ?a schema:about ?team; schema:isPartOf <https://en.wikipedia.org/>; schema:name ?title. }''' % values
    data = json.loads(get('https://query.wikidata.org/sparql?' + urllib.parse.urlencode({'query': q}), 'application/sparql-results+json'))
    for b in data['results']['bindings']:
        slug = club_titles.get(b['title']['value'])
        if slug: out.setdefault(slug, {}).setdefault(b['tm']['value'], []).append(b['start']['value'][:10])
    time.sleep(2)
(WORK/'wikidata_spells.json').write_text(json.dumps(out))
print('players with a day-precision start date at the club:', sum(len(v) for v in out.values()))
