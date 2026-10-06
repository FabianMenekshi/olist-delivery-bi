import unittest
from src.stats import wilson_interval

class WilsonTests(unittest.TestCase):
    def test_known_reference(self):
        low,high=wilson_interval(50,100)
        self.assertAlmostEqual(low,0.4038315304,places=8)
        self.assertAlmostEqual(high,0.5961684696,places=8)
    def test_no_observations_is_not_zero_risk(self):
        self.assertEqual(wilson_interval(0,0),(None,None))
    def test_boundary_uncertainty(self):
        low,high=wilson_interval(0,10)
        self.assertAlmostEqual(low,0)
        self.assertGreater(high,0.27)
        low,high=wilson_interval(10,10)
        self.assertLess(low,0.73)
        self.assertAlmostEqual(high,1)
    def test_invalid_counts(self):
        for k,n in [(2,1),(-1,2),(0,-1)]:
            with self.assertRaises(ValueError): wilson_interval(k,n)

if __name__=='__main__': unittest.main()
