"""Trend uses exact persisted Structure rows, shared budgets and immutable lineage."""
import json
import unittest
from unittest.mock import patch
import test_regime_history as fixtures
from Section_1_Global_Core import regime_research as research
from Section_1_Global_Core.memory_storage.Storage import engine_store
from Section_5_Market_Regime.engines import trend,structure

class TrendHistory(unittest.TestCase):
    setUp=fixtures.RegimeHistory.setUp

    def test_dependency_rows_budget_restart_and_projected_replay(self):
        first=research.catch_up('BTCUSDT','1m',since=None,limit=20,engine_name='TREND',now_ms=10**9)
        self.assertEqual(first['processed'],10);self.assertEqual(first['dependency_processed'],10)
        second=research.catch_up('BTCUSDT','1m',since=None,limit=20,engine_name='TREND',now_ms=10**9)
        self.assertEqual(second['run_id'],first['run_id']);self.assertEqual(second['processed'],10)
        self.assertLessEqual(second['processed']+second['dependency_processed'],20)
        conn=engine_store.open_db();state=None
        try:
            rows=conn.execute('SELECT candle_time,payload FROM engine_results WHERE run_id=? ORDER BY candle_time',(first['run_id'],)).fetchall()
            for row in rows:
                snapshot=engine_store.input_bundle(conn,first['run_id'],row['candle_time']);snapshot['computed_at']=10**9
                actual,state=trend.evaluate(snapshot,previous_state=state);self.assertEqual(actual,json.loads(row['payload']))
                dependency=snapshot['dependencies']['STRUCTURE'];self.assertEqual(dependency['candle_open_time'],row['candle_time'])
                self.assertTrue(actual['provenance']['dependency_results']);self.assertEqual(actual['identity'],dependency['identity'])
                self.assertNotIn('measurements',dependency)  # Minimal projection, not a wide feature copy.
            self.assertEqual(engine_store.load(conn,first['run_id'])[1],state)
        finally:conn.close()
        self.assertIn('trend_counts',research.diagnostics(first['run_id']))

    def test_warm_structure_is_explicit_measurement_only_not_scheduler_missingness(self):
        row=research.catch_up('BTCUSDT','1m',since=None,limit=100,engine_name='TREND',now_ms=10**9)
        self.assertEqual(row['processed'],32);self.assertLessEqual(row['latest']['coverage'],.8)
        self.assertIn('STRUCTURE_UNAVAILABLE_MEASUREMENT_ONLY',row['latest']['quality_flags'])
        self.assertIn('DEPENDENCY_AVAILABILITY_RECONSTRUCTED',row['latest']['quality_flags'])

    def test_trend_failure_cannot_commit_partial_parent_state_or_erase_dependency(self):
        with patch.object(trend,'evaluate',side_effect=RuntimeError('injected Trend failure')):
            with self.assertRaises(RuntimeError):research.catch_up('BTCUSDT','1m',since=None,limit=20,engine_name='TREND',now_ms=10**9)
        conn=engine_store.open_db()
        try:
            runs=[json.loads(r[0]) for r in conn.execute('SELECT metadata FROM engine_runs')]
            self.assertEqual([r['engine'] for r in runs],['STRUCTURE'])
        finally:conn.close()
        row=research.catch_up('BTCUSDT','1m',since=None,limit=20,engine_name='TREND',now_ms=10**9)
        self.assertEqual(row['processed'],10)

    def test_structure_backlog_does_not_persist_a_missing_dependency_result(self):
        real=research.catch_up
        def intercept(*args,**kwargs):
            if kwargs.get('engine_name')=='STRUCTURE':return dict(processed=0,status='injected dependency backlog')
            return real(*args,**kwargs)
        with patch.object(research,'catch_up',side_effect=intercept):
            row=real('BTCUSDT','1m',since=None,limit=20,engine_name='TREND',now_ms=10**9)
        self.assertEqual(row['processed'],0);self.assertIn('Waiting for Structure',row['status'])

    def test_runner_counts_dependency_rows_inside_shared_budget(self):
        from Section_1_Global_Core import analytical_processor as worker
        worker._cursor=2;worker._status.clear()
        with patch.object(research,'catch_up',return_value=dict(processed=7,dependency_processed=13,status='processed',latest={})) as call:
            self.assertEqual(worker.maintenance(['BTCUSDT'],['1m'],max_bars=20,time_budget=10,max_pairs=1),20)
            self.assertEqual(call.call_args.kwargs['engine_name'],'TREND')
