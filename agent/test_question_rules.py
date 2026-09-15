import sqlite3
import unittest
from question_variety import select_varied, validate_round, banned_question
from migrate_question_rules import migrate


def q(text, date='2025-01-01'):
    return {'question_text': text, 'fact_date': date}


class RulesTests(unittest.TestCase):
    def test_same_match_across_topics(self):
        with self.assertRaisesRegex(ValueError, 'Repeated match'):
            validate_round([q('What was the highest attendance?'), q('Which player scored a hat-trick?')])

    def test_search_keeps_alternative_match_in_same_family(self):
        fresh = q('What was the final score?')
        bank = [q('What was the highest attendance?'), q('What was the lowest attendance?', '2025-02-01'), q('Who was the manager?'), q('What was the largest transfer fee?'), q('Who was the top goalscorer?')]
        result = select_varied(bank, fresh)
        self.assertEqual(result[0]['fact_date'], '2025-02-01')
        validate_round([*result, fresh])

    def test_first_team_banned_but_half_allowed(self):
        for text in ['Which team scored first in the match?', 'Archive question: Which side scored first?', 'Which team scored the opening goal?']:
            self.assertTrue(banned_question(q(text)))
            with self.assertRaises(ValueError):
                validate_round([q(text)])
        self.assertFalse(banned_question(q('In which half was the first goal scored?')))

    def test_migration_idempotent_preserves_active_round(self):
        c = sqlite3.connect(':memory:')
        c.executescript('CREATE TABLE questions(id INTEGER PRIMARY KEY,question_text TEXT,status TEXT,use_count INTEGER,last_used_date TEXT); CREATE TABLE daily_questions(club_id INTEGER,quiz_date TEXT,question_id INTEGER); CREATE TABLE clubs(id INTEGER,slug TEXT); INSERT INTO clubs VALUES(1,"arsenal"); INSERT INTO questions VALUES(1,"Which side scored first?","reviewed",2,"2026-09-17"); INSERT INTO daily_questions VALUES(1,"2026-09-16",1),(1,"2026-09-17",1);')
        migrate(c, '2026-09-16', set())
        self.assertEqual(c.execute('SELECT status,use_count FROM questions').fetchone()[:], ('retired', 0))
        self.assertEqual(c.execute('SELECT quiz_date FROM daily_questions').fetchone()[0], '2026-09-16')
        self.assertTrue(migrate(c, '2026-09-16')['already_applied'])


if __name__ == '__main__':
    unittest.main()
