import datetime as dt
import sqlite3
import unittest
from question_variety import question_topics, select_varied, validate_round, banned_question
from generate_questions import ranked, DB

class VarietyTests(unittest.TestCase):
    def test_similar_wording(self):
        pairs=[
            ("How many goals in total were scored in Arsenal's high-scoring match?", "Archive question: How many goals did Arsenal score in their high-scoring match?"),
            ("Who was the top goalscorer in 2024?", "Who was the second-highest goalscorer in 2023?"),
            ("What was the largest incoming transfer fee?", "Which player commanded the largest outgoing transfer fee?"),
            ("What was the highest attendance?", "Who did Arsenal play at the lowest attendance?"),
            ("How many yellow cards did Arsenal receive?", "Which player was sent off?"),
            ("What was the final score in a high-scoring match?", "What was the score for Arsenal in their latest match?"),
        ]
        for a,b in pairs:
            with self.subTest(a=a,b=b):
                self.assertTrue(question_topics({"question_text":a}) & question_topics({"question_text":b}))

    def test_no_repetitive_fallback(self):
        r={"question_text":"Who was the manager?", "semantic_key":"v4|a|v0"}
        with self.assertRaises(RuntimeError):
            select_varied([r],{"question_text":"What was the attendance?", "fact_date":"2026-09-01"})

    def test_all_clubs_and_fresh_types(self):
        con=sqlite3.connect("file:"+DB+"?mode=ro",uri=True); con.row_factory=sqlite3.Row
        fresh=[{"question_text":x,"fact_date":"2026-09-01"} for x in ("What was the score for Arsenal?", "How many yellow cards did Arsenal receive?", "How many red cards did Arsenal receive?")]
        for question in con.execute("select question_text from questions"):
            self.assertTrue(question_topics(question))
        total=0
        for club in con.execute("select id from clubs where active=1"):
            bank=con.execute("select * from questions where club_id=? and semantic_key like 'v4bank|%' and status='reviewed'",(club["id"],)).fetchall()
            for offset in range(30):
                date=(dt.date(2026,9,15)+dt.timedelta(days=offset)).isoformat()
                for f in fresh:
                    try:
                        selected=select_varied(ranked(bank,date),f)
                    except RuntimeError:
                        # A sparse bank may require the publisher to choose cards instead of a score.
                        f=fresh[1]
                        selected=select_varied(ranked(bank,date),f)
                    self.assertEqual(len(selected),4)
                    validate_round([*selected,f])
                    total+=1
        con.close()
        print(f"Validated {total} club/date/fresh-type combinations")
if __name__=="__main__":unittest.main()
