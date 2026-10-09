import unittest
from app.research.savip_liquidity_experiment import compare_liquidity_gate
from app.strategy.reference_thresholds import HARD

BASE={"age_minutes":90,"liquidity_usd":20000,"volume_h24_usd":80000,"mcap_usd":100000}

class LiquidityExperimentTests(unittest.TestCase):
    def test_newly_admitted_only_by_liquidity(self):
        x=compare_liquidity_gate(BASE)
        self.assertEqual((x.control_eligible,x.experiment_eligible,x.newly_admitted),(False,True,True))
    def test_control_stays_unchanged(self):
        self.assertEqual(HARD["min_liquidity_usd"],25000)
        x=compare_liquidity_gate({**BASE,"liquidity_usd":25000})
        self.assertTrue(x.control_eligible)
        self.assertFalse(x.newly_admitted)
    def test_below_experiment_floor(self):
        self.assertFalse(compare_liquidity_gate({**BASE,"liquidity_usd":14999}).experiment_eligible)
    def test_other_gates_never_relaxed(self):
        for key,value in (("age_minutes",20),("volume_h24_usd",1000),("mcap_usd",5000)):
            self.assertFalse(compare_liquidity_gate({**BASE,key:value}).experiment_eligible)
    def test_missing_and_nan_fail_closed(self):
        self.assertFalse(compare_liquidity_gate({}).experiment_eligible)
        self.assertFalse(compare_liquidity_gate({**BASE,"liquidity_usd":float("nan")}).experiment_eligible)
