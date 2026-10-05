import sqlite3
import unittest
from question_variety import select_varied, validate_round, banned_question
from migrate_question_rules import migrate
from generate_questions import ranked


def q(text, date='2025-01-01'):
    return {'question_text': text, 'fact_date': date}


class RulesTests(unittest.TestCase):
    def test_same_match_across_topics(self):
        with self.assertRaisesRegex(ValueError, 'Repeated match'):
            validate_round([q('What was the highest attendance?'), q('Which player scored a hat-trick?')])

    def test_search_keeps_alternative_match_in_same_family(self):
        fresh = q('What was the final score?')
        bank = [q('What was the highest attendance?'), q('What was the lowest attendance?', '2025-02-01'), q('Who was the manager?'), q('What was the largest transfer fee?')]
        bank.insert(0, {'question_text':'What is the club nickname?', 'fact_date':None, 'semantic_key':'generic|test|nickname', 'id':0})
        for i,row in enumerate(bank): row.setdefault('id',i); row.setdefault('semantic_key','v4bank|test|'+str(i))
        fresh.update(id=99,semantic_key='matchfact|test|score')
        result = select_varied(bank, fresh)
        self.assertEqual(next(r for r in result if 'lowest attendance' in r['question_text'])['fact_date'], '2025-02-01')
        validate_round([*result, fresh])

    def test_wording_variant_inherits_family_usage(self):
        rows = [
            {'id': 1, 'semantic_key': 'v4bank|forest|same-fact|v0', 'use_count': 1, 'last_used_date': '2026-09-26'},
            {'id': 2, 'semantic_key': 'v4bank|forest|same-fact|v1', 'use_count': 0, 'last_used_date': None},
            {'id': 3, 'semantic_key': 'v4bank|forest|different-fact|v0', 'use_count': 0, 'last_used_date': None},
        ]
        ordered = ranked(rows, '2026-09-27')
        self.assertEqual(ordered[0]['id'], 3)
        self.assertIn(ordered[-1]['id'], (1, 2))

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
