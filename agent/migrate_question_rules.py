"""Back up and retire prohibited questions without deleting saved round history."""
import argparse
import datetime as dt
import json
import sqlite3
from pathlib import Path
from zoneinfo import ZoneInfo
from generate_questions import DB, BACKUPS
from question_variety import banned_question


def migrate(con, today, played_clubs=None):
    con.row_factory = sqlite3.Row
    con.execute('BEGIN IMMEDIATE')
    try:
        con.execute('CREATE TABLE IF NOT EXISTS question_rule_migrations (version TEXT PRIMARY KEY, applied_at TEXT NOT NULL)')
        if con.execute("SELECT 1 FROM question_rule_migrations WHERE version='player-use-v1'").fetchone():
            con.rollback()
            return {'already_applied': True}
        con.execute('CREATE TABLE IF NOT EXISTS question_play_days (question_id INTEGER NOT NULL REFERENCES questions(id), play_date TEXT NOT NULL, PRIMARY KEY(question_id,play_date))')
        con.execute('CREATE TABLE IF NOT EXISTS question_rule_exclusions (question_id INTEGER PRIMARY KEY REFERENCES questions(id), reason TEXT NOT NULL)')
        banned = [r['id'] for r in con.execute('SELECT * FROM questions') if banned_question(r)]
        con.executemany('INSERT OR IGNORE INTO question_rule_exclusions VALUES (?,?)', [(qid, 'First-scoring team question') for qid in banned])
        con.executemany("UPDATE questions SET status='retired' WHERE id=?", [(qid,) for qid in banned])
        # Only remove unpublished future rounds. Keep today's/in-progress rounds.
        future = list(con.execute('SELECT question_id,count(*) AS n FROM daily_questions WHERE quiz_date>? GROUP BY question_id', (today,)))
        con.execute('DELETE FROM daily_questions WHERE quiz_date>?', (today,))
        for row in future:
            con.execute('UPDATE questions SET use_count=max(0,use_count-?),last_used_date=(SELECT max(quiz_date) FROM daily_questions WHERE question_id=?) WHERE id=?', (row['n'], row['question_id'], row['question_id']))
        # Legacy publication counts are retained conservatively for older dates.
        # Today's untouched clubs can be refunded using existing start events.
        if played_clubs is not None:
            for row in con.execute('SELECT dq.question_id,c.slug FROM daily_questions dq JOIN clubs c ON c.id=dq.club_id WHERE dq.quiz_date=?', (today,)).fetchall():
                if row['slug'] in played_clubs:
                    con.execute('INSERT OR IGNORE INTO question_play_days VALUES (?,?)', (row['question_id'], today))
                else:
                    con.execute('UPDATE questions SET use_count=max(0,use_count-1),last_used_date=(SELECT max(quiz_date) FROM daily_questions WHERE question_id=? AND quiz_date<?) WHERE id=?', (row['question_id'], today, row['question_id']))
        con.execute("INSERT INTO question_rule_migrations VALUES ('player-use-v1',?)", (dt.datetime.now(dt.timezone.utc).isoformat(),))
        con.commit()
        return {'excluded_questions': len(banned), 'future_selections_removed': sum(r['n'] for r in future)}
    except Exception:
        con.rollback()
        raise


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    con = sqlite3.connect('file:' + DB + '?mode=' + ('rw' if args.apply else 'ro'), uri=True)
    con.row_factory = sqlite3.Row
    if not args.apply:
        print(json.dumps({'prohibited_questions': sum(banned_question(r) for r in con.execute('SELECT * FROM questions')), 'apply_required': True}))
        return
    Path(BACKUPS).mkdir(parents=True, exist_ok=True)
    backup = str(Path(BACKUPS) / ('question-rules-' + dt.datetime.now().strftime('%Y%m%d-%H%M%S-%f') + '.sqlite'))
    with sqlite3.connect(backup) as dest:
        con.backup(dest)
    today = dt.datetime.now(ZoneInfo('Europe/London')).date().isoformat()
    with sqlite3.connect('file:' + str(Path(DB).with_name('analytics.sqlite')) + '?mode=ro', uri=True) as analytics:
        if analytics.execute("SELECT 1 FROM sqlite_master WHERE name='club_daily_totals'").fetchone():
            played = {r[0] for r in analytics.execute("SELECT club_slug FROM club_daily_totals WHERE event_date=? AND (started>0 OR completed>0)", (today,))}
        else:
            played = {r[0] for r in analytics.execute("SELECT DISTINCT club_slug FROM player_events WHERE event_date=? AND event_type IN ('started','completed')", (today,))}
    print(json.dumps({'backup': backup, **migrate(con, today, played)}))


if __name__ == '__main__':
    main()
