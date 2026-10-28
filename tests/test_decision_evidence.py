"""Durable ADCN evidence is immutable and independent of subsequent chart reads."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from Section_1_Global_Core.memory_storage.Storage import adcn_store
from Section_1_Global_Core.analysis import annotate
from Section_10_Opportunity_Engine.engine import evaluate,with_costs
from Section_10_Opportunity_Engine.context import anchor


def packet(side='SELL'):
    fields=dict(atr=1,resistance_zone_low=106,resistance_zone_high=106.2,
        inst_resistance_zone_low=109,inst_resistance_zone_high=109.2,nearest_bear_fvg_low=112,nearest_bear_fvg_high=112.2,
        support_zone_low=93.8,support_zone_high=94,inst_support_zone_low=90.8,inst_support_zone_high=91,
        nearest_bull_fvg_low=87.8,nearest_bull_fvg_high=88)
    confidence=dict(status='ready',buy_score=30,sell_score=70)
    result=anchor(evaluate(100,fields),side=side,open_time=120000,confidence=confidence)
    result['available_ms']=180000
    return result


class StoredEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'ADCN.db'
        self.patch=patch.object(adcn_store,'DB_PATH',self.path);self.patch.start();self.addCleanup(self.patch.stop)
        self.conn=adcn_store.open_db();self.addCleanup(self.conn.close)

    def test_opportunity_version_isolates_new_spacing_without_overwriting_old_snapshots(self):
        from Section_1_Global_Core.decision_evidence import epoch_key
        with patch('Section_1_Global_Core.decision_evidence.data_policy.read',return_value={'epochs':{}}),patch('Section_1_Global_Core.decision_evidence.features_store.decision_generation',return_value=0):
            with patch('Section_10_Opportunity_Engine.engine.VERSION','opportunity-v4'):old=epoch_key('X','1m')
            with patch('Section_10_Opportunity_Engine.engine.VERSION','opportunity-v5'):new=epoch_key('X','1m')
        adcn_store.save_evidence(self.conn,'X','1m',old,packet(),recorded_ms=190000,provenance='old spacing')
        self.assertNotEqual(old,new)
        self.assertEqual(adcn_store.evidence_range(self.conn,'X','1m',0,200000,new),{})
        self.assertTrue(adcn_store.evidence_range(self.conn,'X','1m',0,200000,old))

    def test_eight_values_survive_reopen_and_repeated_inserts_cannot_rewrite(self):
        context=packet()
        self.assertEqual(adcn_store.save_evidence(self.conn,'BTCUSDT','15m','[0,0,0]',context,recorded_ms=190000,provenance='closed decision worker'),1)
        changed=copy.deepcopy(context);changed['entry']=999
        self.assertEqual(adcn_store.save_evidence(self.conn,'BTCUSDT','15m','[0,0,0]',changed,recorded_ms=200000,provenance='overwrite attempt'),0)
        row=self.conn.execute('SELECT signal_price,confidence_score,resistance_1,resistance_2,resistance_3,support_1,support_2,support_3 FROM decision_evidence').fetchone()
        self.assertEqual(row[:2],(100,70));self.assertTrue(all(row[2:]))
        reopened=adcn_store.open_db()
        try:loaded=adcn_store.evidence_range(reopened,'BTCUSDT','15m',0,200000,'[0,0,0]')[(120000,'SELL')]
        finally:reopened.close()
        self.assertEqual(loaded['area_map'],context['area_map'])
        self.assertEqual(loaded['storage']['status'],'persisted')

    def test_saved_snapshot_prevents_recalculation_even_if_features_are_missing(self):
        stored=packet();stored['storage']=dict(status='persisted')
        bar=dict(open_time=120000,client=dict(open_time=120000,close_time=179999,open=100,high=105,low=99,close=100),features=None,
            adcn=dict(analysis_snapshot=stored),momentum=dict(signal_type='SELL'))
        with patch('Section_1_Global_Core.analysis.opportunity',side_effect=AssertionError('must use saved zones')):
            annotate([bar],now_ms=200000)
        self.assertEqual(bar['signal_context']['area_map'],stored['area_map'])
        self.assertEqual(bar['confidence'],stored['confidence'])
        self.assertTrue(all(a['low']>100 for a in bar['opportunity']['areas']['resistance']))
        self.assertTrue(all(a['high']<100 for a in bar['opportunity']['areas']['support']))

    def test_cost_settings_reprice_saved_geometry_without_mutation(self):
        original=packet()['opportunity'];before=copy.deepcopy(original)
        result=with_costs(json.loads(json.dumps(original)),8,3)
        self.assertEqual(original,before)
        for role in ('support','resistance'):
            self.assertEqual([(z['low'],z['high']) for z in result['areas'][role]],[(z['low'],z['high']) for z in original['areas'][role]])
        self.assertEqual(result['costs']['round_trip_bps'],22)
        self.assertLess(result['buy']['targets'][0]['net_reward_pct'],original['buy']['targets'][0]['net_reward_pct'])

    def test_no_snapshot_leaks_across_epoch_and_missing_slots_are_null(self):
        context=packet();context['area_map']['support']=[]
        adcn_store.save_evidence(self.conn,'X','1h','[0,0,0]',context,recorded_ms=190000,provenance='historical reconstruction')
        self.assertEqual(adcn_store.evidence_range(self.conn,'X','1h',0,200000,'[1,0,0]'),{})
        self.assertEqual(self.conn.execute('SELECT support_1,support_2,support_3 FROM decision_evidence').fetchone(),(None,None,None))

    def test_presentation_restores_persisted_decision_when_features_unavailable(self):
        from Section_8_Decision_Engine.presentation import annotate as decisions
        stored=packet();bar=dict(open_time=120000,client=dict(close_time=179999,close=100),features=None,adcn=dict(analysis_snapshot=stored))
        decisions([bar])
        self.assertEqual(bar['momentum']['signal_type'],'SELL')
        self.assertEqual(bar['momentum']['signal_price'],100)
