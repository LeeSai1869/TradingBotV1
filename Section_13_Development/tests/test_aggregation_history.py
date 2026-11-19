"""Indexed publication availability, source generations and immutable MTF history."""
from dataclasses import replace
import json
import unittest
from unittest.mock import patch
import test_regime_history as fixtures
from Section_1_Global_Core import aggregation_processor as processor, aggregation_store, regime_research, data_policy
from Section_1_Global_Core.memory_storage.Storage import features_store
from Section_5_Market_Regime import aggregation
from Section_5_Market_Regime.aggregation_config import AggregationConfig


class AggregationHistory(unittest.TestCase):
    setUp=fixtures.RegimeHistory.setUp

    def publish(self):
        row=regime_research.catch_up('BTCUSDT','1m',limit=100,now_ms=3910000)
        processor.observe('BTCUSDT','1m','REGIME',row,now_ms=3910001)
        return row

    def test_indexed_sources_deduplicate_and_reproduce_exact_inputs(self):
        row=self.publish()
        first=processor.refresh('BTCUSDT','REGIME',intervals=['1m'],now_ms=3910001)
        self.assertEqual(first['processed'],1);self.assertEqual(len(first['latest']['result_refs']),1)
        self.assertEqual(first['latest']['alignment'],'UNKNOWN')  # One TF cannot establish MTF alignment.
        second=processor.refresh('BTCUSDT','REGIME',intervals=['1m'],now_ms=3910100)
        self.assertEqual(second['processed'],0);self.assertEqual(first['result_id'],second['result_id'])
        conn=aggregation_store.open_db()
        try:
            bundle=aggregation_store.input_bundle(conn,first['result_id']);bundle['computed_at']=3910001
            self.assertEqual(aggregation.evaluate(bundle),first['latest'])
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM mtf_sources').fetchone()[0],1)
            self.assertNotIn('measurements',bundle['timeframes'][0]['result'])
        finally:conn.close()
        stale=processor.refresh('BTCUSDT','REGIME',intervals=['1m'],now_ms=4000000)
        self.assertEqual(stale['latest']['timeframes']['1m']['reason'],'STALE');self.assertEqual(stale['processed'],1)

    def test_late_publication_and_explicit_reconstructed_close_simulation(self):
        self.publish()
        actual=processor.refresh('BTCUSDT','REGIME',intervals=['1m'],as_of=3840000,now_ms=3910001)
        self.assertFalse(actual['latest']['result_refs'])
        cfg=AggregationConfig(availability='RECONSTRUCTED_CLOSE')
        simulated=processor.refresh('BTCUSDT','REGIME',intervals=['1m'],config=cfg,as_of=3840000,now_ms=3910001)
        self.assertEqual(len(simulated['latest']['result_refs']),1)
        self.assertEqual(simulated['latest']['timeframes']['1m']['known_time'],3840000)
        self.assertIn('SIMULATED_CLOSE_AVAILABILITY_NOT_ORIGINAL_PUBLICATION',simulated['latest']['quality_flags'])
        self.assertGreater(simulated['latest']['timeframes']['1m']['available_at'],3840000)

    def test_unavailable_generation_and_disabled_scope_never_fall_back(self):
        self.publish()
        with patch.object(processor,'generation',return_value='new-producer'):
            changed=processor.refresh('BTCUSDT','REGIME',intervals=['1m'],now_ms=3910002)
        self.assertEqual(changed['latest']['timeframes']['1m']['reason'],'INCOMPATIBLE_PRODUCER_GENERATION')
        processor.observe('BTCUSDT','1m','REGIME',dict(status='Waiting for committed feature replay'),now_ms=3910003)
        blocked=processor.refresh('BTCUSDT','REGIME',intervals=['1m'],now_ms=3910004)
        self.assertFalse(blocked['latest']['result_refs']);self.assertIn('ENGINE_UNAVAILABLE',blocked['latest']['timeframes']['1m']['reason'])
        policy=data_policy.read();policy['timeframes']['1m']='inactive';data_policy.write(policy)
        disabled=processor.refresh('BTCUSDT','REGIME',intervals=['1m'],now_ms=3910005)
        self.assertEqual(disabled['latest']['timeframes']['1m']['reason'],'DISABLED');self.assertEqual(disabled['latest']['weights'],{})

    def test_source_replay_and_deletion_epoch_block_older_evidence(self):
        self.publish();conn=features_store.open_db()
        try:
            with conn:conn.execute('UPDATE feature_calculation_versions SET generation=1')
        finally:conn.close()
        changed=processor.refresh('BTCUSDT','REGIME',intervals=['1m'],now_ms=3910002)
        self.assertEqual(changed['latest']['timeframes']['1m']['reason'],'SOURCE_REPLAY_PENDING_OR_CHANGED')
        policy=data_policy.read();policy['epochs']['interval:1m']=1;data_policy.write(policy)
        changed=processor.refresh('BTCUSDT','REGIME',intervals=['1m'],now_ms=3910003)
        self.assertEqual(changed['latest']['timeframes']['1m']['reason'],'INCOMPATIBLE_DATA_GENERATION')

    def test_calendar_next_close_and_budget_yield(self):
        from datetime import datetime,timezone
        stamp=lambda y,m,d:int(datetime(y,m,d,tzinfo=timezone.utc).timestamp()*1000)
        self.assertEqual(processor.advance(stamp(2026,2,1),'1M'),stamp(2026,3,1))
        self.assertEqual(processor.advance(stamp(2028,2,1),'1M'),stamp(2028,3,1))
        self.assertEqual(processor.advance(stamp(2026,1,1),'3M'),stamp(2026,4,1))
        self.publish()
        row=processor.refresh('BTCUSDT','REGIME',intervals=['1m'],now_ms=3910001,deadline=0)
        self.assertEqual(row['processed'],0);self.assertIn('yielded',row['status'])
        conn=aggregation_store.open_db()
        try:self.assertEqual(conn.execute('SELECT COUNT(*) FROM mtf_results').fetchone()[0],0)
        finally:conn.close()

    def test_rollback_and_future_publication_are_rejected(self):
        row=self.publish()
        with self.assertRaises(ValueError):processor.observe('BTCUSDT','1m','REGIME',row,now_ms=1)
        conn=aggregation_store.open_db()
        try:
            with conn:conn.execute("CREATE TRIGGER reject_mtf BEFORE INSERT ON mtf_results BEGIN SELECT RAISE(ABORT,'injected'); END")
        finally:conn.close()
        import sqlite3
        with self.assertRaises(sqlite3.IntegrityError):processor.refresh('BTCUSDT','REGIME',intervals=['1m'],now_ms=3910001)
        conn=aggregation_store.open_db()
        try:self.assertEqual(conn.execute('SELECT COUNT(*) FROM mtf_input_bundles').fetchone()[0],0)
        finally:conn.close()

    def test_two_independent_timeframe_histories_and_spare_runner_budget(self):
        self.publish()
        from Section_1_Global_Core.memory_storage.Storage import klines_store,db
        from Section_4_Features.execution.engine import Engine
        from Section_4_Features.execution import checkpoint
        from Section_4_Features.execution.components import current_signature
        conn=klines_store.open_db()
        try:
            with conn:conn.execute("DELETE FROM klines WHERE symbol='BTCUSDT' AND interval='3m'")
        finally:conn.close()
        conn=features_store.open_db()
        try:
            with conn:conn.execute("DELETE FROM features WHERE symbol='BTCUSDT' AND interval='3m'")
        finally:conn.close()
        clients=[dict(c,interval='3m',open_time=i*180000,close_time=(i+1)*180000-1) for i,c in enumerate(self.clients)]
        engine=Engine('BTCUSDT','3m');db.write_klines(clients);db.write_features([engine.step(c) for c in clients])
        conn=features_store.open_db()
        try:
            with conn:
                conn.execute('INSERT INTO feature_engine_state VALUES (?,?,?,?)',('BTCUSDT','3m',64*180000,checkpoint.dump(engine,(0,0))))
                conn.execute('INSERT INTO feature_calculation_versions(symbol,interval,signature,generation) VALUES (?,?,?,0)',('BTCUSDT','3m',current_signature()))
        finally:conn.close()
        row=regime_research.catch_up('BTCUSDT','3m',limit=100,now_ms=11701000)
        processor.observe('BTCUSDT','3m','REGIME',row,now_ms=11701001)
        cfg=AggregationConfig(freshness_grace_ms=10000000)  # Explicit relaxed policy for this differently seeded fixture.
        merged=processor.refresh('BTCUSDT','REGIME',intervals=['1m','3m'],config=cfg,now_ms=11701001)
        self.assertEqual(len(merged['latest']['result_refs']),2);self.assertEqual(merged['latest']['alignment'],'ALIGNED')
        from Section_1_Global_Core import analytical_processor as worker
        response=dict(processed=19,status='processed',latest={},symbol='BTCUSDT',timeframe='1m')
        worker._cursor=0;worker._status.clear()
        with patch.object(regime_research,'catch_up',return_value=response),patch.object(processor,'observe') as observe,patch.object(processor,'refresh',return_value=dict(processed=1)) as refresh:
            self.assertEqual(worker.maintenance(['BTCUSDT'],['1m'],history_time_budget=0,max_bars=20,time_budget=10,max_pairs=1),20)
            observe.assert_called_once();refresh.assert_called_once()
            self.assertIn('deadline',refresh.call_args.kwargs)
        worker._cursor=0
        with patch.object(regime_research,'catch_up',return_value=dict(response,processed=20)),patch.object(processor,'observe') as observe:
            self.assertEqual(worker.maintenance(['BTCUSDT'],['1m'],history_time_budget=0,max_bars=20,time_budget=10,max_pairs=1),20)
            observe.assert_not_called()

    def test_new_unindexed_gap_checkpoint_cannot_fall_back_to_good_label(self):
        row=self.publish();conn=aggregation_store.open_db()
        try:
            old=conn.execute('SELECT bundle_id FROM engine_results WHERE run_id=? AND candle_time=?',(row['run_id'],row['latest']['candle_open_time'])).fetchone()[0]
            result=dict(row['latest'],candle_open_time=3900000,candle_close_time=3959999,as_of=3960000,available_at=3960000,computed_at=3960000,data_quality='GAP')
            from Section_1_Global_Core.memory_storage.Storage import engine_store
            with conn:
                conn.execute('INSERT INTO engine_results VALUES (?,?,?,?,?)',(row['run_id'],3900000,old,engine_store.encode(engine_store.stable_result(result)),engine_store.encode(result)))
                conn.execute('UPDATE engine_runs SET cursor=? WHERE run_id=?',(3900000,row['run_id']))
        finally:conn.close()
        # Still inside the older result's freshness grace, but a bad new close is known.
        merged=processor.refresh('BTCUSDT','REGIME',intervals=['1m'],now_ms=3960001)
        self.assertFalse(merged['latest']['result_refs'])
        self.assertEqual(merged['latest']['timeframes']['1m']['reason'],'NEWER_COMMITTED_CHECKPOINT_NOT_INDEXED')
