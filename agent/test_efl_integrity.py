import sqlite3,unittest
from collect_efl_players import protection,protect
from generate_questions import scoreopts
from source_utils import broad_position
from question_variety import select_varied,validate_round

class EFLIntegrity(unittest.TestCase):
    def test_ambiguous_role_requires_review(self):
        self.assertEqual(broad_position('Attacking midfielder'),'Midfielder')
        self.assertEqual(broad_position('Centre-back'),'Defender')
        self.assertEqual(broad_position('Winger'),'Forward')
        self.assertIsNone(broad_position('Defender / midfielder'))
        self.assertIsNone(broad_position(''))

    def test_verified_role_survives_future_import(self):
        c=sqlite3.connect(':memory:')
        c.executescript('CREATE TABLE players(id INTEGER PRIMARY KEY,position TEXT,position_rank INTEGER); INSERT INTO players VALUES(1,"Defender",1);')
        protection(c);protect(c,1,'Midfielder','https://tigerbase.hullcity.com/','Historical club role')
        c.execute('UPDATE players SET position="Defender",position_rank=1 WHERE id=1')
        self.assertEqual(c.execute('SELECT position,position_rank FROM players').fetchone(),('Midfielder',2))

    def test_nil_nil_has_four_distinct_choices(self):
        choices,index=scoreopts(0,0,'nil-nil-regression')
        self.assertEqual(len(set(choices)),4)
        self.assertEqual(choices[index],'0-0')

    def test_selector_tries_alternative_club_fact(self):
        def row(i,f):return {'id':i,'semantic_key':f,'question_text':'Sourced fact','fact_date':None}
        fresh=row(99,'v4bank|efl|player_appearances|test|a')
        bank=[row(1,'generic|test|player-birth|x'),row(2,'generic|test|founded|x'),row(3,'v4bank|efl|player_biography|test|x'),row(4,'v4bank|efl|runs|test|x'),row(5,'v4bank|efl|season_record|test|x')]
        selected=select_varied(bank,fresh)
        self.assertEqual(selected[0]['id'],2)
        validate_round([*selected,fresh])

if __name__=='__main__':unittest.main()
