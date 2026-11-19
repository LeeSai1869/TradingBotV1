"""Candidates and confirmations are distinct, causal and window-independent."""
import copy
import json
import unittest
from Section_5_Market_Regime.events import catalog

IDENTITY=dict(symbol='BTCUSDT',timeframe='5m',generation_id='test')

def row(i,**features):
    values={key:None for key in catalog.FIELDS}
    values.update(measurement_gap=False,di_anchor_continuous=True,candidate_pivot=0,structure_events='[]',di_anchor_events='[]',structure_events_version='structure-events-v1',structure_event_status='READY')
    values.update(features)
    return dict(open_time=i*300000,close_time=(i+1)*300000-1,features=values)


def pivot(known,origin=0):
    return dict(type='PIVOT_HIGH',id='original-pivot-id',origin_time=origin,known_time=known,price=105,origin_bar=0,classification='HIGHER_HIGH')


class ResearchEvents(unittest.TestCase):
    def test_first_window_seeds_candidate_without_fabricating_start(self):
        current=row(0,candidate_pivot=1,candidate_pivot_high_price=105,candidate_pivot_high_time=0,candidate_pivot_high_bar=0)
        self.assertEqual(catalog.project(IDENTITY,current)[0],[])
        later=row(1,**current['features'])
        self.assertEqual(catalog.project(IDENTITY,later,current)[0],[])

    def test_candidate_update_and_confirmation_keep_actual_knowledge_time(self):
        a=row(0,candidate_pivot=1,candidate_pivot_high_price=105,candidate_pivot_high_time=0,candidate_pivot_high_bar=0)
        b=row(1,candidate_pivot=1,candidate_pivot_high_price=108,candidate_pivot_high_time=300000,candidate_pivot_high_bar=1)
        original=copy.deepcopy(b)
        events,_=catalog.project(IDENTITY,b,a)
        self.assertEqual([event['type'] for event in events],['STRUCTURE_CANDIDATE_HIGH_UPDATED'])
        self.assertEqual(events[0]['stage'],'CANDIDATE');self.assertEqual(events[0]['known_time'],600000)
        self.assertEqual(events[0]['origin_time'],300000);self.assertEqual(b,original)
        c=row(2,candidate_pivot=-1,candidate_pivot_high_price=108,candidate_pivot_high_time=300000,candidate_pivot_high_bar=1,candidate_pivot_low_price=100,candidate_pivot_low_time=600000,candidate_pivot_low_bar=2,
            structure_events=json.dumps([pivot(900000,300000)]))
        events,_=catalog.project(IDENTITY,c,b)
        confirmed=[event for event in events if event['stage']=='CONFIRMED']
        self.assertEqual(len(confirmed),1);self.assertEqual(confirmed[0]['source_id'],'original-pivot-id')
        self.assertEqual(confirmed[0]['origin_time'],300000);self.assertEqual(confirmed[0]['known_time'],900000)
        self.assertTrue(any(event['type']=='STRUCTURE_CANDIDATE_HIGH_CLEARED' for event in events))

    def test_inactive_structure_fields_are_not_another_candidate(self):
        a=row(0,candidate_pivot=-1,candidate_pivot_high_price=105,candidate_pivot_high_time=0,candidate_pivot_high_bar=0)
        b=row(1,candidate_pivot=-1,candidate_pivot_high_price=110,candidate_pivot_high_time=300000,candidate_pivot_high_bar=1)
        self.assertEqual(catalog.project(IDENTITY,b,a)[0],[])

    def test_di_candidate_origin_unknown_and_native_qualification_retained(self):
        a=row(0,di_plus_candidate_high=40)
        b=row(1,di_plus_candidate_high=45,di_anchor_events=json.dumps([dict(type='di_high',channel='di_plus',time=0,confirmed_time=600000,value=45,qualified=False)]))
        events,_=catalog.project(IDENTITY,b,a)
        candidate=next(event for event in events if event['stage']=='CANDIDATE')
        self.assertIsNone(candidate['origin_time'])
        confirmed=next(event for event in events if event['stage']=='CONFIRMED')
        self.assertFalse(confirmed['details']['qualified']);self.assertEqual(confirmed['known_time'],600000)
        self.assertEqual(catalog.project(IDENTITY,b,a)[0],events)

    def test_gaps_suppress_candidate_comparisons_and_future_events_are_rejected(self):
        a=row(0,di_plus_candidate_high=10)
        b=row(2,di_plus_candidate_high=15,structure_events=json.dumps([pivot(1200000)]))
        events,warnings=catalog.project(IDENTITY,b,a)
        self.assertEqual(events,[]);self.assertTrue(warnings)
        b=row(1,di_plus_candidate_high=15,measurement_gap=True)
        self.assertEqual(catalog.project(IDENTITY,b,a)[0],[])
        b=row(1,di_plus_candidate_high=15,di_anchor_continuous=False)
        self.assertEqual(catalog.project(IDENTITY,b,a)[0],[])

    def test_malformed_and_duplicate_sources_and_reference_are_explicit(self):
        b=row(1,structure_events=json.dumps([pivot(600000),pivot(600000)]),di_anchor_events=json.dumps([dict(type='price_high',price=105,time=0,known_time=600000)]))
        events,_=catalog.project(IDENTITY,b)
        self.assertEqual(len(events),2);self.assertEqual({event['stage'] for event in events},{'CONFIRMED','REFERENCE'})
        b['features']['structure_events']='malformed'
        events,notes=catalog.project(IDENTITY,b)
        self.assertEqual(len(events),1);self.assertTrue(notes)
        b['features']['structure_events']=json.dumps([dict(type=[])])
        self.assertTrue(catalog.project(IDENTITY,b)[1])

    def test_later_candles_cannot_change_prefix_events(self):
        samples=[row(i,di_minus_candidate_low=20-i) for i in range(6)]
        def evaluate(rows):return [event for i,current in enumerate(rows) for event in catalog.project(IDENTITY,current,rows[i-1] if i else None)[0]]
        prefix=evaluate(samples[:3]);complete=evaluate(samples)
        self.assertEqual(prefix,[event for event in complete if event['known_time']<=900000])
        with self.assertRaises(ValueError):catalog.project(dict(IDENTITY,timeframe='4h'),samples[0])
