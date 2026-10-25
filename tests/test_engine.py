import unittest
import numpy as np
from engine.model import simulate, reflection_touch, trading_hours, fit_volatility
from engine.calibration import metrics, walk_forward_splits
from engine.stability import publish

class EngineTests(unittest.TestCase):
    def test_reflection_limit(self):
        grid=np.linspace(0,12,49)
        _,high,_=simulate(100,.005,grid,paths=30000,seed=44,gaussian=True)
        actual=np.mean(high[:,-1]>=np.log(102/100))
        self.assertAlmostEqual(actual,reflection_touch(100,102,.005,12),delta=.015)
    def test_weekend_and_break(self):
        self.assertEqual(trading_hours('2026-10-24T12:00:00+00:00',24),0)
        self.assertEqual(trading_hours('2026-10-23T20:00:00+00:00',72),23)
        self.assertEqual(trading_hours('2026-10-23T21:00:00+00:00',1),0)
    def test_invalid_prices(self):
        with self.assertRaises(ValueError):fit_volatility([100]*100+[-1])
    def test_reproducibility(self):
        a=simulate(100,.003,[0,1,2],500,seed=4)[0]
        b=simulate(100,.003,[0,1,2],500,seed=4)[0]
        np.testing.assert_array_equal(a,b)
    def test_calibration_metrics(self):
        self.assertEqual(metrics([0,1],[0,1])['brierScore'],0)
        with self.assertRaises(ValueError):metrics([1.5],[1])
        for train,test in walk_forward_splits(1400,1000,100,24):
            self.assertGreaterEqual(test[0]-train[-1]-1,24)
    def test_stability(self):
        def fixture(p,id):return {'id':id,'mode':'live','generatedAt':'2026-01-01','levels':[100],'horizons':[{'results':[{'touch':p}]}],'status':{'mode':'stable','reason':'test'}}
        old=fixture(.3,'old'); candidate=fixture(.4,'new')
        held,state,audit=publish(candidate,old)
        self.assertEqual(held['id'],'old');self.assertFalse(audit)
        released,_,audit=publish(candidate,old,state)
        self.assertEqual(released['id'],'new');self.assertTrue(audit)
        reversed_candidate=fixture(.2,'reverse')
        held,reverse_state,_=publish(reversed_candidate,old,state)
        self.assertEqual(held['id'],'old')
        self.assertEqual(reverse_state['pending'],1)
        shock,_,_=publish(candidate,old,major_event=True)
        self.assertEqual(shock['status']['mode'],'shock')
if __name__=='__main__':unittest.main()
