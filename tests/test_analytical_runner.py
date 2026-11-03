"""Automatic recent classification, fair bounded turns, and Structure adapter."""
import copy
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from test_regime_engine import snapshot
import test_regime_history as history_fixtures
from Section_1_Global_Core import analytical_processor as worker,regime_research as research
from Section_1_Global_Core.memory_storage.Storage import engine_store,db
from Section_4_Features.execution.engine import Engine
from Section_4_Features.execution import checkpoint
from Section_5_Market_Regime.engines import structure


def source(i,**fields):
    item=snapshot(i);values=dict(current_structure='STRUCTURE_BULL',bullish_structure_active=True,bearish_structure_active=False,range_structure_active=False,
        bull_bos_count=0,bear_bos_count=0,range_bos_count=0,last_structure_bos='',last_structure_choch='',
        measurement_gap=False,measurement_version='shared-v1',measurement_config_id='x',structure_events='[]',structure_events_version='structure-events-v1',structure_event_status='READY')
    values.update(fields);item['features']=values;item['units']=structure.UNITS.copy();item['field_validity']={k:'VALID' if v is not None else 'UNAVAILABLE' for k,v in values.items()};item['field_available_at']={k:item['as_of'] for k in values}
    return item

class StructureEngine(unittest.TestCase):
    def test_explicit_mapping_break_dedup_and_no_candidate_pivots(self):
        result,state=structure.evaluate(source(0))
        self.assertEqual(result['classification']['active_structure'],'HH_HL');self.assertEqual(result['coverage'],1.)
        from Section_4_Features.features import structure_events as producer
        _,buffer=producer.transition(producer.new_state(),[],'BTCUSDT','1m',dict(open_time=60000,close_time=119999),'BOS','bullishBOS',1,0)
        result,state=structure.evaluate(source(1,bull_bos_count=1,last_structure_bos='bullishBOS',structure_events=json.dumps(buffer)),previous_state=state)
        self.assertEqual(result['classification']['condition'],'BROKEN');events=result['measurements']['new_events'];self.assertEqual(len(events),1)
        self.assertIsNone(events[0]['origin_time']);self.assertEqual(events[0]['known_time'],120000)
        result,state=structure.evaluate(source(2,bull_bos_count=1,last_structure_bos='bullishBOS'),previous_state=state)
        self.assertEqual(result['measurements']['new_events'],[]);self.assertEqual(result['classification']['last_event'],'BOS')
        self.assertNotIn('new_high_type',structure.FIELDS)
        import jsonschema
        schema=json.loads((Path(__file__).parents[1]/'Section_5_Market_Regime/contracts/result.schema.json').read_text())
        jsonschema.Draft202012Validator(schema).validate(result)

    def test_cold_counters_gap_future_preview_and_restart(self):
        result,state=structure.evaluate(source(0,bull_bos_count=10));self.assertEqual(result['measurements']['new_events'],[])
        snap=source(1,bull_bos_count=11);snap['closed']=False;original=copy.deepcopy(state)
        preview,same=structure.evaluate(snap,previous_state=state);self.assertEqual(same,original);self.assertEqual(preview['measurements']['new_events'],[])
        result,state=structure.evaluate(source(2,bull_bos_count=11),previous_state=state)
        self.assertEqual(result['data_quality'],'GAP');self.assertEqual(result['measurements']['new_events'],[])
        snap=source(3);snap['field_available_at']['current_structure']=snap['as_of']+1
        result,state=structure.evaluate(snap,previous_state=json.loads(json.dumps(state)))
        self.assertEqual(result['classification']['direction'],'UNKNOWN')

class RunnerTurns(unittest.TestCase):
    def test_round_robin_limits_failure_isolation_and_event_does_not_gate(self):
        worker._cursor=0;worker._status.clear();seen=[]
        def advance(symbol,interval,**options):
            seen.append((symbol,interval,options['engine_name']));self.assertIsNone(options['since'])
            if len(seen)==1:raise RuntimeError('injected adapter failure')
            return dict(processed=options['limit'],status='processed',latest={})
        with patch.object(research,'catch_up',side_effect=advance):
            self.assertLessEqual(worker.maintenance(['BTCUSDT','ETHUSDT'],['1m'],max_bars=120,time_budget=10),120)
            worker.maintenance(['BTCUSDT','ETHUSDT'],['1m'],max_bars=120,time_budget=10)
            worker.maintenance(['BTCUSDT','ETHUSDT'],['1m'],max_bars=120,time_budget=10)
        self.assertTrue(any(row[0]=='ETHUSDT' for row in seen));self.assertTrue(worker.process_bar(SimpleNamespace()))
        with patch.object(research,'catch_up') as call:worker.maintenance([],['1m']);call.assert_not_called()

class AutomaticHistory(unittest.TestCase):
    setUp=history_fixtures.RegimeHistory.setUp

    def test_saved_recent_seed_resumes_and_structure_uses_separate_history(self):
        first=research.catch_up('BTCUSDT','1m',since=None,now_ms=10**9)
        self.assertEqual(first['processed'],32)
        second=research.catch_up('BTCUSDT','1m',since=None,now_ms=10**9)
        self.assertEqual(second['run_id'],first['run_id']);self.assertEqual(second['processed'],0)
        other=research.catch_up('BTCUSDT','1m',since=None,engine_name='STRUCTURE',now_ms=10**9)
        self.assertEqual(other['processed'],32);self.assertNotEqual(other['run_id'],first['run_id'])
        self.assertEqual(other['latest']['engine'],'STRUCTURE')
        conn=engine_store.open_db()
        try:self.assertEqual(conn.execute('SELECT COUNT(*) FROM engine_live_seeds').fetchone()[0],2)
        finally:conn.close()

        # A new close follows the saved seed, without creating another run.
        engine=Engine('BTCUSDT','1m')
        for client in self.clients:engine.step(client)
        client=dict(self.clients[-1],open_time=65*60000,close_time=66*60000-1)
        db.write_klines([client])
        blocked=research.catch_up('BTCUSDT','1m',since=None,now_ms=10**9)
        self.assertEqual(blocked['processed'],0);self.assertIn('latest closed candle',blocked['status'])
        db.write_features([engine.step(client)])
        from Section_1_Global_Core.memory_storage.Storage import features_store
        conn=features_store.open_db()
        with conn:conn.execute('UPDATE feature_engine_state SET last_open_time=?,state=? WHERE symbol=? AND interval=?',(65*60000,checkpoint.dump(engine,(0,0)),'BTCUSDT','1m'))
        conn.close()
        third=research.catch_up('BTCUSDT','1m',since=None,now_ms=10**9)
        self.assertEqual(third['run_id'],first['run_id']);self.assertEqual(third['processed'],1)
