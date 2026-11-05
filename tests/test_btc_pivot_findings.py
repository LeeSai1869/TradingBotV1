import copy
import unittest
from analyze_btc_pivot_study import groups_for,effect_profile

class Findings(unittest.TestCase):
    def row(self,outcome,year,mean,count=50):
        return dict(side='BUY_SIDE',outcome=outcome,year=year,pivots=count,count=[count],mean=[mean],stddev=[1.],minimum=[mean-1],maximum=[mean+1])
    def test_legacy_atr_collision_recovers_percentage_explicitly(self):
        row=self.row('HIT','ALL',.005);second=copy.deepcopy(row)
        for key in ('mean','stddev','minimum','maximum'):second[key]=[v*100 for v in row[key]]
        packet=dict(features=dict(atr_percent=[row,second]));before=copy.deepcopy(packet)
        rows,n=groups_for(packet,'atr_pct_of_close');self.assertEqual(n,1);self.assertEqual(rows[0]['mean'],[.5]);self.assertEqual(packet,before)
        packet['features']['atr_percent'][1]['count']=[49]
        with self.assertRaises(ValueError):groups_for(packet,'atr_pct_of_close')
    def test_missing_nonhit_cohort_is_not_a_zero_mean(self):
        result=effect_profile([self.row('HIT','ALL',3)],'BUY_SIDE',0)
        self.assertIsNone(result['nonhit_mean']);self.assertEqual(result['eligible_years'],0)
    def test_year_consistency_requires_both_cohorts_and_sample_count(self):
        rows=[self.row('HIT','2020',3),self.row('NO_HIT','2020',1),self.row('HIT','2021',1,10),self.row('NO_HIT','2021',3,10)]
        result=effect_profile(rows,'BUY_SIDE',0);self.assertEqual(result['eligible_years'],1);self.assertEqual(result['positive_years'],1)
        self.assertEqual(result['median_within_year_standardized_difference'],2)
