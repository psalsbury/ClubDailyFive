"""Exercise the PHP tracking endpoint against disposable SQLite databases."""
import json
import socket
import sqlite3
import subprocess
import tempfile
import time
import unittest
import urllib.request
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo


class PlayerUsageTests(unittest.TestCase):
    def test_only_seen_questions_consumed_once_per_day(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            quiz = root / 'clubquiz.sqlite'
            today = datetime.now(ZoneInfo('Europe/London')).date().isoformat()
            with sqlite3.connect(quiz) as c:
                c.executescript('CREATE TABLE clubs(id INTEGER,slug TEXT,active INTEGER); INSERT INTO clubs VALUES(1,"arsenal",1); CREATE TABLE questions(id INTEGER PRIMARY KEY,use_count INTEGER,last_used_date TEXT); INSERT INTO questions VALUES(1,0,NULL),(2,0,NULL); CREATE TABLE daily_questions(club_id INTEGER,quiz_date TEXT,question_id INTEGER); CREATE TABLE question_play_days(question_id INTEGER,play_date TEXT,PRIMARY KEY(question_id,play_date));')
                c.executemany('INSERT INTO daily_questions VALUES(1,?,?)', [(today, 1), (today, 2)])
            source = (Path(__file__).resolve().parents[1] / 'site/track.php').read_text()
            (root / 'track.php').write_text(source.replace('/var/lib/clubdailyfive/', directory + '/'))
            with socket.socket() as sock:
                sock.bind(('127.0.0.1', 0))
                port = sock.getsockname()[1]
            proc = subprocess.Popen(['php', '-S', f'127.0.0.1:{port}', '-t', directory], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            try:
                for attempt in range(50):
                    try:
                        with socket.create_connection(('127.0.0.1', port), timeout=.1):
                            break
                    except OSError:
                        time.sleep(.02)
                for player in ('test-player-000001', 'test-player-000001', 'test-player-000002'):
                    body = {'player_id': player, 'club': 'arsenal', 'event': 'shown', 'question_id': 1, 'quiz_date': today}
                    req = urllib.request.Request(f'http://127.0.0.1:{port}/track.php', data=json.dumps(body).encode(), headers={'Content-Type': 'application/json'})
                    with urllib.request.urlopen(req) as response:
                        self.assertEqual(json.load(response), {'ok': True})
                with sqlite3.connect(quiz) as c:
                    self.assertEqual(c.execute('SELECT id,use_count,last_used_date FROM questions ORDER BY id').fetchall(), [(1, 1, today), (2, 0, None)])
            finally:
                proc.terminate()
                proc.wait(timeout=5)


if __name__ == '__main__':
    unittest.main()
