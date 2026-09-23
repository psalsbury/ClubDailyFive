import json
import sqlite3
import unittest

from attendance_options import attendance_options, migrate_attendance_options


class AttendanceOptionsTest(unittest.TestCase):
    def assert_valid(self, options, correct, ceiling):
        values = [int(value) for value in options]
        self.assertEqual(4, len(set(values)))
        self.assertIn(correct, values)
        self.assertTrue(all(value <= ceiling for value in values))
        self.assertTrue(all(abs(value - correct) >= 1_000 for value in values if value != correct))

    def test_highest_attendance_uses_only_lower_distractors(self):
        self.assert_valid(attendance_options(30_445, 30_445, "high"), 30_445, 30_445)

    def test_lowest_attendance_stays_below_season_high(self):
        self.assert_valid(attendance_options(24_123, 30_445, "low"), 24_123, 30_445)

    def test_migrates_all_numeric_variants_but_not_opponent_question(self):
        con = sqlite3.connect(":memory:")
        con.row_factory = sqlite3.Row
        con.execute("CREATE TABLE questions(id INTEGER PRIMARY KEY,club_id INTEGER,question_text TEXT,options_json TEXT,correct_index INTEGER)")
        rows = [
            (1, 7, "What was Forest's highest home league attendance in 2024-25?", ["30445", "30100", "29000", "28000"], 0),
            (2, 7, "Archive question: What was Forest's lowest home league attendance in 2024-25?", ["24123", "24000", "25000", "26000"], 0),
            (3, 7, "Who did Forest play when they recorded their highest home league attendance in 2024-25?", ["Arsenal", "Chelsea", "Everton", "Fulham"], 0),
        ]
        con.executemany("INSERT INTO questions VALUES(?,?,?,?,?)", [(i,c,t,json.dumps(o),a) for i,c,t,o,a in rows])
        self.assertEqual(2, migrate_attendance_options(con))
        for row in con.execute("SELECT * FROM questions WHERE id IN (1,2)"):
            options=json.loads(row["options_json"]); correct=int(options[row["correct_index"]])
            self.assert_valid(options, correct, 30_445)
        self.assertEqual(json.dumps(rows[2][3]), con.execute("SELECT options_json FROM questions WHERE id=3").fetchone()[0])


if __name__ == "__main__":
    unittest.main()
