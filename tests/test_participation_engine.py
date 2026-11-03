"""Causal volume interpretation, missing flow and independent dimensions."""
import copy
import json
from pathlib import Path
import unittest
from test_regime_engine import snapshot as base
from Section_5_Market_Regime.engines import participation as engine
from Section_5_Market_Regime.engines.participation_config import ParticipationConfig


def snapshot(i,**changes):
    s=base(i);f=dict(relative_volume_valid=True,relative_volume=2.,volume_change_pct=20.,price_progress_per_relative_volume=.002,measurement_gap=False,measurement_version='shared-v1',measurement_config_id='shared')
    f.update(changes);s.update(features=f,units=engine.UNITS.copy(),field_validity={k:'VALID' if v is not None else 'UNAVAILABLE' for k,v in f.items()},field_available_at={k:s['as_of'] for k in f},market_metadata=dict(calendar='24/7 UTC'))
    return s

class ParticipationEngine(unittest.TestCase):
    def confirmed(self,**changes):
        state=None
        for i in range(3):result,state=engine.evaluate(snapshot(i,**changes),previous_state=state)
        return result,state

    def test_thresholds_and_no_aggressor_proxy(self):
        for rvol,label in ((0.,'VERY_LOW'),(.5,'LOW'),(.8,'NORMAL'),(1.5,'HIGH'),(3.,'EXTREME')):
            result,_=self.confirmed(relative_volume=rvol)
            self.assertEqual(result['classification']['activity'],label)
            self.assertEqual(result['classification']['dominance'],'UNKNOWN')
            self.assertEqual(result['coverage'],.75)
        import jsonschema
        schema=json.loads((Path(__file__).parents[1]/'Section_5_Market_Regime/contracts/result.schema.json').read_text())
        jsonschema.Draft202012Validator(schema).validate(result)

    def test_missing_volume_zero_volume_and_legacy_fallback(self):
        result,_=self.confirmed(relative_volume_valid=False,relative_volume=0.)
        self.assertEqual(result['classification'],engine.UNKNOWN);self.assertEqual(result['coverage'],0.)
        result,_=self.confirmed(relative_volume=0.,volume_change_pct=-100.,price_progress_per_relative_volume=None)
        self.assertEqual(result['classification']['activity'],'VERY_LOW');self.assertEqual(result['classification']['participation'],'DECLINING')
        self.assertEqual(result['classification']['confirmation'],'UNKNOWN');self.assertEqual(result['coverage'],.55)

    def test_price_confirmation_is_symmetric_not_directional(self):
        for progress in (-.002,.002):
            result,_=self.confirmed(price_progress_per_relative_volume=progress)
            self.assertEqual(result['classification']['confirmation'],'CONFIRMING')
        result,_=self.confirmed(relative_volume=.6,price_progress_per_relative_volume=.01)
        self.assertEqual(result['classification']['confirmation'],'DIVERGING')
        result,_=self.confirmed(price_progress_per_relative_volume=0.)
        self.assertEqual(result['classification']['confirmation'],'NEUTRAL')
        self.assertIn('POTENTIAL_ABSORPTION_OR_TWO_SIDED_ACTIVITY',result['quality_flags'])

    def test_restart_preview_gap_event_dedup_and_identity(self):
        result,state=self.confirmed();self.assertEqual(len(result['measurements']['new_events']),3)
        old=copy.deepcopy(state);s=snapshot(3);s['closed']=False
        result,same=engine.evaluate(s,previous_state=state);self.assertEqual(same,old);self.assertEqual(result['measurements']['new_events'],[])
        a,state=engine.evaluate(snapshot(3),previous_state=state)
        b,_=engine.evaluate(snapshot(3),previous_state=json.loads(json.dumps(old)))
        self.assertEqual(a,b);self.assertEqual(a['measurements']['new_events'],[])
        result,state=engine.evaluate(snapshot(5),previous_state=state);self.assertEqual(result['data_quality'],'GAP');self.assertEqual(result['classification'],engine.UNKNOWN)
        with self.assertRaises(ValueError):engine.evaluate(snapshot(5),previous_state=state)
        with self.assertRaises(ValueError):engine.evaluate(snapshot(6),ParticipationConfig(confirmation_bars=2),state)

    def test_input_availability_units_and_config(self):
        s=snapshot(0);s['field_available_at']['relative_volume']=s['as_of']+1
        result,_=engine.evaluate(s);self.assertEqual(result['coverage'],0.)
        s=snapshot(0,relative_volume_valid=1.);result,_=engine.evaluate(s);self.assertNotEqual(result['data_quality'],'INVALID')
        s=snapshot(0,relative_volume=-1.);result,_=engine.evaluate(s);self.assertEqual(result['data_quality'],'INVALID')
        with self.assertRaises(ValueError):ParticipationConfig(high_rvol=.4)
        with self.assertRaises(ValueError):ParticipationConfig(confirmation_bars=True)
