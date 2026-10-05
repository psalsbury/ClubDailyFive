import unittest
from transfermarkt_players import season_year,norm
from collect_efl_players import debut
class TransfermarktChecks(unittest.TestCase):
 def test_century(self):
  self.assertEqual(season_year('96/97'),1996)
  self.assertEqual(season_year('16/17'),2016)
 def test_transfer_date_is_not_debut(self):
  raw='<h2>Bolton Wanderers</h2><p>On 20 January 2011, he joined Bolton Wanderers and made his debut on 29 January against Wigan.</p>'
  self.assertEqual(debut(raw,{'name':'Bolton Wanderers','team':'Bolton Wanderers'},2011),(None,None))
 def test_explicit_debut(self):
  raw='<h2>Bolton Wanderers</h2><p>He made his debut for Bolton Wanderers on 29 January 2011 against Wigan.</p>'
  self.assertEqual(debut(raw,{'name':'Bolton Wanderers','team':'Bolton Wanderers'},2011)[0].isoformat(),'2011-01-29')
 def test_identity(self):
  self.assertEqual(norm('AFC Bournemouth'),norm('Bournemouth'))
if __name__=='__main__':unittest.main()
