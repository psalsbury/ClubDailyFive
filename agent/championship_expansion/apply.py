#!/usr/bin/env python3
"""Phase 4: add the proposed players to the Player Wordle bank in one transaction, after a backup.

Each player gets an efl_player_research row ('approved') whose reason says how the debut was found:
  'Championship expansion: exact debut ...'   or   'Championship expansion: season-based debut estimate ...'
so estimated players can be listed, upgraded or removed later, e.g.
  select * from efl_player_research where reason like 'Championship expansion: season-based%';
Positions are not locked in position_overrides, so the nightly position audit can still flag them.
"""
import json, pathlib, sqlite3, datetime as dt, sys
sys.path.insert(0, '/opt/clubdailyfive/bin'); sys.path.insert(0, str(pathlib.Path(__file__).parent))
from nationality import CANONICAL
sql_quote = lambda v: "'" + v.replace("'", "''") + "'"
DB = '/var/lib/clubdailyfive/player-wordle/game.sqlite3'
WORK = pathlib.Path('/var/lib/clubdailyfive/championship-expansion')
REASON = {'exact': 'Championship expansion: exact debut date from Wikipedia (subject matched by Transfermarkt ID and date of birth)',
          'month': 'Championship expansion: debut month and year from Wikipedia (day not stated; age exact unless born that month)',
          'season': 'Championship expansion: season-based debut estimate from Transfermarkt season data (debut year/age may be out by one)'}

def main():
    proposals = json.load(open(WORK/'proposals.json'))
    now = dt.datetime.now(dt.timezone.utc).isoformat()
    backup = f"{DB}.bak.pre-championship-expansion-{dt.datetime.now().strftime('%Y%m%d-%H%M%S')}"
    src = sqlite3.connect(DB, timeout=60); dst = sqlite3.connect(backup); src.backup(dst); dst.close()
    print('backup:', backup)
    c = src; c.execute('pragma foreign_keys=on'); c.execute('begin immediate')
    # One spelling per country: the game marks nationality green only on an exact text match.
    case = ' '.join("WHEN %s THEN %s" % (sql_quote(k), sql_quote(v)) for k, v in CANONICAL.items())
    names = ','.join(sql_quote(k) for k in CANONICAL)
    for event in ('INSERT', 'UPDATE OF nationality'):
        c.execute(f"DROP TRIGGER IF EXISTS canonical_nationality_{event.split()[0].lower()}")
        c.execute(f"""CREATE TRIGGER canonical_nationality_{event.split()[0].lower()} AFTER {event} ON players WHEN NEW.nationality IN ({names})
            BEGIN UPDATE players SET nationality=CASE NEW.nationality {case} END WHERE id=NEW.id; END""")
    renamed = c.execute(f"UPDATE players SET nationality=CASE nationality {case} END WHERE nationality IN ({names})").rowcount
    print('existing players with a variant country spelling standardised:', renamed)
    added = {}; skipped = 0
    try:
        for slug, club in proposals.items():
            cid = club['club_id']; n = 0
            for p in club['players']:
                cur = c.execute("""INSERT INTO players(club_id,name,debut_age,position,position_rank,nationality,continent,appearances,prior_clubs,source_url,source_updated_at,debut_year)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(club_id,name) DO NOTHING""",
                    (cid, p['name'], p['debut_age'], p['position'], p['position_rank'], p['nationality'], p['continent'], p['appearances'], p['prior_clubs'], p['source_url'], now, p['debut_year']))
                if not cur.rowcount: skipped += 1; continue
                n += 1
                c.execute('INSERT OR REPLACE INTO efl_player_research VALUES(?,?,?,?,?,?,?,?)',
                          (cid, p['name'], p['profile_id'], 'approved', REASON[p['method']], p['source_url'], json.dumps(p, ensure_ascii=False), now))
                c.execute("""INSERT INTO player_candidates(club_id,name,discovered_at,source_url,status) VALUES(?,?,?,?,'approved')
                    ON CONFLICT(club_id,name) DO UPDATE SET status='approved',source_url=excluded.source_url""", (cid, p['name'], now, p['source_url']))
                c.execute("UPDATE enrichment_queue SET status='approved' WHERE club_id=? AND player_name=?", (cid, p['name']))
            added[slug] = n
        exact = sum(p['method'] == 'exact' for club in proposals.values() for p in club['players'])
        c.execute('INSERT INTO agent_runs(ran_at,status,details) VALUES(?,?,?)', (now, 'championship-expansion', json.dumps({'added': added, 'total_added': sum(added.values()), 'exact_debuts': exact, 'skipped_existing': skipped, 'nationality_spellings_standardised': renamed, 'backup': backup})))
        assert not c.execute('pragma foreign_key_check').fetchall()
        c.commit()
    except Exception:
        c.rollback(); raise
    assert c.execute('pragma integrity_check').fetchone()[0] == 'ok'
    print('added', sum(added.values()), 'players;', 'skipped (already present)', skipped)
    for slug, n in added.items(): print(f'  {slug:26} +{n}')

if __name__ == '__main__': main()
