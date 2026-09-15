"""Replace individual analytics with bounded daily totals; do not back up identifiers."""
import argparse
import datetime as dt
import sqlite3
from zoneinfo import ZoneInfo


def migrate(con, today):
    week = today - dt.timedelta(days=today.weekday())
    earliest = min(week, today.replace(day=1)).isoformat()
    con.execute('PRAGMA secure_delete=ON')
    con.execute('BEGIN IMMEDIATE')
    try:
        con.execute('CREATE TABLE IF NOT EXISTS club_daily_totals(event_date TEXT NOT NULL,club_slug TEXT NOT NULL,started INTEGER NOT NULL DEFAULT 0,completed INTEGER NOT NULL DEFAULT 0,PRIMARY KEY(event_date,club_slug)) WITHOUT ROWID')
        if con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='player_events'").fetchone():
            con.execute('''INSERT INTO club_daily_totals(event_date,club_slug,started,completed)
                SELECT event_date,club_slug,SUM(event_type='started'),SUM(event_type='completed')
                FROM player_events WHERE event_date>=? AND event_date<=? AND event_type IN ('started','completed')
                GROUP BY event_date,club_slug
                ON CONFLICT(event_date,club_slug) DO UPDATE SET started=started+excluded.started,completed=completed+excluded.completed''', (earliest,today.isoformat()))
            con.execute('DROP TABLE player_events')
        con.execute('DELETE FROM club_daily_totals WHERE event_date<? OR event_date>?', (earliest,today.isoformat()))
        con.commit()
    except Exception:
        con.rollback()
        raise
    con.execute('PRAGMA wal_checkpoint(TRUNCATE)')
    con.execute('VACUUM')
    con.execute('PRAGMA wal_checkpoint(TRUNCATE)')
    return con.execute('SELECT COUNT(*),COALESCE(SUM(started),0),COALESCE(SUM(completed),0) FROM club_daily_totals').fetchone()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('database')
    args = parser.parse_args()
    with sqlite3.connect('file:'+args.database+'?mode=rw',uri=True,timeout=30) as con:
        print(migrate(con,dt.datetime.now(ZoneInfo('Europe/London')).date()))
