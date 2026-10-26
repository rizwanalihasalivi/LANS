"""Recorded decision parity and rejection of incomplete/unpaired pilot evidence."""
import copy,csv,json,unittest
from bootstrap import ROOT
from run_pilots import screening

class Screening(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  with (ROOT/'results/revision4-pilots/evaluation/episodes.csv').open() as stream:
   cls.rows=list(csv.DictReader(stream))
  for r in cls.rows:
   for k in ('seed','speed','noise_seed'):r[k]=int(r[k])
   for k in ('penalized_rmse','active_fraction'):r[k]=float(r[k])
   r['survived']=r['survived']=='True'
 def test_recorded_decision_unchanged(self):
  old=json.loads((ROOT/'results/revision4-pilots/pilot-decision.json').read_text())
  for arm,expected in zip('BCD',old['assessments']):
   actual=screening(self.rows,arm)
   self.assertEqual(actual['checks'],expected['checks']);self.assertEqual(actual['eligible'],expected['eligible'])
 def test_missing_severe_grid_rejected(self):
  with self.assertRaisesRegex(ValueError,'incomplete'):screening([r for r in self.rows if r['scenario']!='latency100'],'B')
 def test_duplicate_rejected(self):
  with self.assertRaisesRegex(ValueError,'duplicate'):screening(self.rows+[self.rows[0]],'B')
 def test_unpaired_noise_rejected(self):
  rows=copy.deepcopy(self.rows);next(r for r in rows if r['method']=='B_hybrid')['noise_seed']+=1
  with self.assertRaisesRegex(ValueError,'unpaired'):screening(rows,'B')
if __name__=='__main__':unittest.main()
