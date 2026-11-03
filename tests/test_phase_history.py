"""Exact dependency lineage, bounded processing and atomic Phase persistence."""
import json
import unittest
from unittest.mock import patch
import test_regime_history as fixtures
from Section_1_Global_Core import regime_research as research
from Section_1_Global_Core.memory_storage.Storage import engine_store
from Section_5_Market_Regime.engines import phase


class PhaseHistory(unittest.TestCase):
    setUp = fixtures.RegimeHistory.setUp

    def test_budget_resume_minimal_dependencies_and_immutable_reconstruction(self):
        run=None
        for i in range(10):
            row=research.catch_up('BTCUSDT','1m',since=None,limit=20,engine_name='PHASE',now_ms=10**9)
            self.assertLessEqual(row['processed']+row.get('dependency_processed',0),20)
            if run:self.assertEqual(run,row['run_id'])
            run=row['run_id']
            if not row['processed']:break
        conn=engine_store.open_db();state=None
        try:
            rows=conn.execute('SELECT candle_time,payload FROM engine_results WHERE run_id=? ORDER BY candle_time',(run,)).fetchall()
            self.assertEqual(len(rows),32)
            for row in rows:
                snap=engine_store.input_bundle(conn,run,row['candle_time']);snap['computed_at']=10**9
                expected,state=phase.evaluate(snap,previous_state=state)
                self.assertEqual(expected,json.loads(row['payload']))
                self.assertEqual(set(snap['dependencies']),set(phase.DEPENDENCIES))
                for name,dep in snap['dependencies'].items():
                    self.assertEqual(dep['identity'],snap['identity']);self.assertEqual(dep['candle_open_time'],snap['candle_open_time'])
                    ref=snap['dependency_refs'][name].split(':')
                    stored=json.loads(conn.execute('SELECT payload FROM engine_results WHERE run_id=? AND candle_time=?',(ref[0],int(ref[1]))).fetchone()[0])
                    self.assertEqual(ref[2],engine_store.digest(engine_store.stable_result(stored)))
                    if name=='STRUCTURE':self.assertEqual(set(dep['measurements']),{'new_events'})
                    else:self.assertNotIn('measurements',dep)
            self.assertEqual(state,engine_store.load(conn,run)[1])
        finally:conn.close()
        self.assertIn('phase_counts',research.diagnostics(run));self.assertNotIn('direction_counts',research.diagnostics(run))

    def test_dependency_backlog_waits_instead_of_writing_false_missingness(self):
        real=research.catch_up
        def intercept(*args,**kwargs):
            if kwargs.get('engine_name')=='PARTICIPATION':return dict(processed=0,status='injected backlog')
            return real(*args,**kwargs)
        with patch.object(research,'catch_up',side_effect=intercept):
            row=real('BTCUSDT','1m',since=None,limit=20,engine_name='PHASE',now_ms=10**9)
        self.assertEqual(row['processed'],0);self.assertIn('Waiting for PARTICIPATION',row['status'])
        self.assertLessEqual(row['dependency_processed'],20)
        conn=engine_store.open_db()
        try:
            engines=[json.loads(r[0])['engine'] for r in conn.execute('SELECT metadata FROM engine_runs')]
            self.assertNotIn('PHASE',engines)
        finally:conn.close()

    def test_parent_failure_preserves_child_history_without_partial_parent_checkpoint(self):
        with patch.object(phase,'evaluate',side_effect=RuntimeError('injected Phase failure')):
            with self.assertRaises(RuntimeError):research.catch_up('BTCUSDT','1m',since=None,limit=20,engine_name='PHASE',now_ms=10**9)
        conn=engine_store.open_db()
        try:
            engines=[json.loads(r[0])['engine'] for r in conn.execute('SELECT metadata FROM engine_runs')]
            self.assertEqual(set(engines),{'TREND','STRUCTURE','PARTICIPATION'})
        finally:conn.close()
        row=research.catch_up('BTCUSDT','1m',since=None,limit=20,engine_name='PHASE',now_ms=10**9)
        self.assertEqual(row['processed'],4)

    def test_tiny_budget_is_explicit_and_runner_counts_nested_work(self):
        row=research.catch_up('BTCUSDT','1m',since=None,limit=4,engine_name='PHASE',now_ms=10**9)
        self.assertEqual(row['processed'],0);self.assertIn('five rows',row['status'])
        from Section_1_Global_Core import analytical_processor as worker
        worker._cursor=6;worker._status.clear()
        with patch.object(research,'catch_up',return_value=dict(processed=4,dependency_processed=16,status='processed',latest={})) as call:
            self.assertEqual(worker.maintenance(['BTCUSDT'],['1m'],max_bars=20,time_budget=10,max_pairs=1),20)
            self.assertEqual(call.call_args.kwargs['engine_name'],'PHASE')
