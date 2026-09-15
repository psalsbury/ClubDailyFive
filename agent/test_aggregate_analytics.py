import datetime as dt
import sqlite3
import unittest
from migrate_aggregate_analytics import migrate


class AggregateAnalyticsTests(unittest.TestCase):
    def test_preserves_counts_erases_people_and_is_idempotent(self):
        c=sqlite3.connect(':memory:')
        c.execute('CREATE TABLE player_events(player_id TEXT,club_slug TEXT,event_type TEXT,event_date TEXT)')
        c.executemany('INSERT INTO player_events VALUES(?,?,?,?)', [
            ('a','arsenal','started','2026-09-30'),
            ('a','arsenal','completed','2026-09-30'),
            ('a','arsenal','started','2026-10-01'),
            ('b','arsenal','started','2026-10-01'),
            ('b','arsenal','completed','2026-10-01'),
            ('c','chelsea','selected','2026-10-01'),
            ('old','arsenal','started','2026-09-01')])
        c.commit()
        self.assertEqual(migrate(c,dt.date(2026,10,1)),(2,3,2))
        self.assertEqual(migrate(c,dt.date(2026,10,1)),(2,3,2))
        self.assertEqual(c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall(),[('club_daily_totals',)])
        self.assertEqual(c.execute("SELECT SUM(started),SUM(completed) FROM club_daily_totals WHERE event_date>='2026-10-01'").fetchone(),(2,1))
        self.assertEqual(migrate(c,dt.date(2026,11,1)),(0,0,0))

if __name__=='__main__':unittest.main()
