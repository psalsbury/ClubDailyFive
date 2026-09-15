import json
import unittest
from build_v4_bank import leak_safe_question
class MatchPerspectiveTests(unittest.TestCase):
 def render(self, club, home, hg, ag, away, opponent):
  return leak_safe_question({'question_text':f'Who did {club} play in the high-scoring 2024-25 league match that finished {home} {hg}-{ag} {away}?','options_json':json.dumps([opponent,'Other A','Other B','Other C']),'correct_index':0,'semantic_key':'v3bank|test|high_scoring|match|opp','fact_date':'2025-02-01'})
 def test_abbreviations_and_results(self):
  for club,alias in [('Nottingham Forest',"Nott'm Forest"),('Manchester City','Man City'),('Manchester United','Man United'),('Brighton & Hove Albion','Brighton')]:
   for hg,ag in [(7,0),(0,7),(3,3)]:
    home=self.render(club,alias,hg,ag,'Opponent','Opponent')
    self.assertIn('1 February 2025',home)
    self.assertIn('at home',home);self.assertIn(f'{hg}-{ag}',home)
    self.assertIn('beat' if hg>ag else 'lose to' if hg<ag else 'draw with',home)
    away=self.render(club,'Opponent',hg,ag,alias,'Opponent')
    self.assertIn('away',away);self.assertIn(f'{ag}-{hg}',away)
    self.assertIn('beat' if ag>hg else 'lose to' if ag<hg else 'draw with',away)
    self.assertNotIn('Opponent',home);self.assertNotIn('Opponent',away)
 def test_dated_source_and_idempotence(self):
  from question_dates import dated_opponent_question
  row={'question_text':"Who did Nottingham Forest play in the high-scoring 2024-25 league match on 1 February 2025 that finished Nott'm Forest 7-0 Brighton?",'options_json':json.dumps(['Brighton','Other A','Other B','Other C']),'correct_index':0,'semantic_key':'v3bank|test|high_scoring|match|opp','fact_date':'2025-02-01'}
  text=leak_safe_question(row)
  self.assertIn('beat at home',text)
  self.assertEqual(text.count('1 February 2025'),1)
  self.assertEqual(dated_opponent_question(text,row['fact_date']),text)
  self.assertNotIn('Brighton',text)
 def test_unresolved_opponent_rejected(self):
  with self.assertRaises(RuntimeError):self.render('Forest',"Nott'm Forest",7,0,'Brighton','Unknown')
if __name__=='__main__':unittest.main()
