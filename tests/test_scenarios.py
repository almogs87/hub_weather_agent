import unittest
from datetime import date
from app.scenarios import Hub, Demand, Disruption, allocate, evaluate


class ScenarioTests(unittest.TestCase):
    def setUp(self):
        self.h = [Hub('A',80),Hub('B',80),Hub('C',40)]
        self.d = [Demand('X',60),Demand('Y',60)]
        self.links = {('A','X'):10,('B','X'):20,('B','Y'):10,('C','Y'):20}

    def run_scenario(self, events=(), end=5):
        return evaluate(self.h,self.d,self.links,100,date(2025,1,1),date(2025,1,end),events)

    def test_baseline_and_distance_objective(self):
        r = self.run_scenario()
        self.assertEqual(r['baseline']['served_units'],120)
        self.assertEqual(r['baseline']['demand_km'],1200)
        self.assertEqual(r['recovery_status'],'baseline_service_maintained')

    def test_backup_absorbs_single_outage(self):
        r=self.run_scenario([Disruption(('A',),date(2025,1,1),3)])
        self.assertEqual(r['unserved_demand_days'],0)
        self.assertEqual(r['days'][0]['utilization'],{'A':None,'B':1,'C':1})

    def test_regional_outage_and_recovery(self):
        r=self.run_scenario([Disruption(('A','B'),date(2025,1,1),3)])
        self.assertEqual(r['unserved_demand_days'],240)
        self.assertEqual(r['service_recovery_date'],'2025-01-04')
        self.assertEqual(r['days'][0]['unserved_by_area'],{'X':60,'Y':20})

    def test_partial_capacity(self):
        events=[Disruption(('A',),date(2025,1,1),1),Disruption(('B',),date(2025,1,1),1,.5)]
        self.assertEqual(self.run_scenario(events)['days'][0]['unserved_units'],40)

    def test_linear_recovery(self):
        e=Disruption(('B',),date(2025,1,1),1,.5,2)
        self.assertEqual([e.fraction(date(2025,1,i)) for i in range(1,4)],[.5,.75,1])
        events=[Disruption(('A',),date(2025,1,1),3),e]
        self.assertEqual([d['unserved_units'] for d in self.run_scenario(events)['days']],[40,20,0,0,0])

    def test_overlap_uses_minimum(self):
        events=[Disruption(('A',),date(2025,1,1),1,.5),Disruption(('A',),date(2025,1,1),1,.25)]
        self.assertEqual(self.run_scenario(events)['days'][0]['available_capacities']['A'],20)

    def test_no_recovery_inside_horizon(self):
        r=self.run_scenario([Disruption(('A','B'),date(2025,1,1),8)])
        self.assertIsNone(r['service_recovery_date'])
        self.assertEqual(r['recovery_status'],'not_recovered_within_horizon')

    def test_structural_shortfall_separated(self):
        self.d=[Demand('X',100),Demand('Y',150)]
        r=self.run_scenario()
        self.assertEqual(r['structural_unserved_demand_days'],250)
        self.assertEqual(r['incremental_unserved_demand_days'],0)

    def test_service_components_and_distance(self):
        r=allocate([Hub('H',100,'hawaii')],[Demand('X',10)],{('H','X'):1},100)
        self.assertEqual(r['served_units'],0)
        self.assertEqual(allocate(self.h,self.d,self.links,5)['served_units'],0)

    def test_residual_paths_prevent_greedy_shortfall(self):
        # A initially takes X, but must move to Y so B can serve X.
        r=allocate([Hub('A',1),Hub('B',1)],[Demand('X',1),Demand('Y',1)],
                   {('A','X'):1,('A','Y'):2,('B','X'):2},10)
        self.assertEqual(r['served_units'],2)
        self.assertEqual(r['demand_km'],4)

    def test_order_reproducibility(self):
        self.assertEqual(allocate(self.h,self.d,self.links,100),allocate(self.h[::-1],self.d[::-1],dict(reversed(list(self.links.items()))),100))

    def test_validation(self):
        for hubs in [[Hub('A',-1)],[Hub('A',float('nan'))],[Hub('A',1),Hub('A',1)]]:
            with self.assertRaises(ValueError):
                allocate(hubs,self.d,{},100)
        with self.assertRaises(ValueError):
            self.run_scenario([Disruption(('unknown',),date(2025,1,1),1)])
        with self.assertRaises(ValueError):
            self.run_scenario([Disruption(('A',),date(2025,1,1),0)])


if __name__=='__main__':
    unittest.main()
