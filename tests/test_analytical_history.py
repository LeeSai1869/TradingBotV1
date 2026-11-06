"""Real SQLite history replay, live isolation, dependency lineage and coverage."""
import contextlib
import hashlib
import io
import json
import unittest
from unittest.mock import patch
import test_regime_history as fixtures
from Section_1_Global_Core import analytical_history as history,analytical_processor as live
from Section_1_Global_Core import aggregation_processor,intelligence_audit,data_policy,pivot_context_audit
from Section_1_Global_Core.memory_storage.Storage import engine_store,features_store,klines_store


class HistoryReplay(unittest.TestCase):
    setUp=fixtures.RegimeHistory.setUp

    def test_restart_advances_old_history_without_replacing_live_publications(self):
        from Section_1_Global_Core import regime_research
        recent=regime_research.catch_up('BTCUSDT','1m',since=None,now_ms=10**9)
        aggregation_processor.observe('BTCUSDT','1m','REGIME',recent,now_ms=10**9+1)
        hashes=lambda:tuple(hashlib.sha256(p.read_bytes()).hexdigest() for p in (features_store.DB_PATH,klines_store.DB_PATH))
        before=hashes()
        first=history.advance('BTCUSDT','1m','REGIME',limit=20,now_ms=10**9+2)
        second=history.advance('BTCUSDT','1m','REGIME',limit=20,now_ms=10**9+3)
        self.assertEqual(first['processed'],20);self.assertEqual(second['processed'],20)
        self.assertEqual(first['run_id'],second['run_id']);self.assertNotEqual(first['run_id'],recent['run_id'])
        policy=data_policy.read();generation=aggregation_processor.generation('REGIME')
        with intelligence_audit.reader() as conn:
            current,_=intelligence_audit.select_run(conn,'BTCUSDT','1m','REGIME',policy,generation,at=10**9+3)
            self.assertEqual(current['run_id'],recent['run_id'])
            progress=history.progress(conn,None,'BTCUSDT','1m','REGIME',policy,generation,at=10**9+3)
            self.assertEqual(progress['status'],'SOURCE_UNAVAILABLE')
            self.assertEqual(pivot_context_audit.select_history_run(conn,'BTCUSDT','1m','REGIME',policy,generation,at=10**9+3)[0]['run_id'],recent['run_id'])
        third=history.advance('BTCUSDT','1m','REGIME',limit=100,now_ms=10**9+4)
        self.assertEqual(third['processed'],25)
        from Section_1_Global_Core import regime_inputs
        source=regime_inputs.open_sources()
        try:
            with intelligence_audit.reader() as conn:
                progress=history.progress(conn,source,'BTCUSDT','1m','REGIME',policy,generation,at=10**9+4)
                self.assertEqual(progress['classified_candles'],65);self.assertEqual(progress['first_ms'],0)
                self.assertEqual(progress['pending_candles'],0);self.assertEqual(progress['status'],'CAUGHT_UP')
                chosen,status=pivot_context_audit.select_history_run(conn,'BTCUSDT','1m','REGIME',policy,generation,at=10**9+4)
                self.assertEqual(chosen['run_id'],first['run_id']);self.assertIn('HISTORICAL_LANE',status)
        finally:source.close()
        self.assertEqual(before,hashes())

    def test_all_ten_engines_join_historical_dependencies_without_live_bindings(self):
        for turn in range(3):
            for engine in history.ENGINES:history.advance('BTCUSDT','1m',engine,limit=200,now_ms=10**9+turn)
        conn=engine_store.open_db()
        try:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM mtf_bindings').fetchone()[0],0)
            rows=conn.execute('SELECT engine,run_id FROM engine_history_bindings').fetchall()
            self.assertEqual(len(rows),10)
            for engine,run_id in rows:
                self.assertIsNotNone(run_id,engine)
                self.assertEqual(conn.execute('SELECT COUNT(*) FROM engine_results WHERE run_id=?',(run_id,)).fetchone()[0],65,engine)
            bias_run=dict(rows)['BIAS'];bundle=engine_store.input_bundle(conn,bias_run,0)
            for name,ref in bundle['dependency_refs'].items():self.assertTrue(ref.startswith(dict(rows)[name]+':'))
        finally:conn.close()

    def test_paused_and_stale_generations_never_report_complete(self):
        with patch.object(data_policy,'enabled',return_value=False):
            self.assertEqual(history.advance('BTCUSDT','1m','REGIME')['status'],'paused')
        history.advance('BTCUSDT','1m','REGIME',now_ms=10**9)
        with intelligence_audit.reader() as conn:
            run,status=history.select(conn,'BTCUSDT','1m','REGIME',data_policy.read(),'changed',at=10**9)
            self.assertIsNone(run);self.assertEqual(status,'OUTDATED_PRODUCER')

    def test_status_cli_separates_live_readiness_from_historical_row_counts(self):
        import intelligence_status
        history.advance('BTCUSDT','1m','REGIME',limit=100)
        output=io.StringIO();path=self.root/'readiness.json'
        with patch('sys.argv',['intelligence_status.py','--symbols','BTCUSDT','--intervals','1m','--summary','--output',str(path)]),contextlib.redirect_stdout(output):intelligence_status.main()
        self.assertIn('Selected symbols: BTCUSDT',output.getvalue())
        self.assertIn('classified=65 pending=0',output.getvalue())
        result=json.loads(path.read_text())
        self.assertEqual(result['pairs'][0]['engines']['REGIME']['history']['status'],'CAUGHT_UP')
        self.assertEqual(result['pairs'][0]['engines']['REGIME']['status'],'PUBLICATION_INDEX_UNAVAILABLE')

    def test_pending_feature_repair_and_new_uncomputed_close_are_explicit(self):
        from Section_1_Global_Core import regime_inputs
        from Section_1_Global_Core.memory_storage.Storage import db
        history.advance('BTCUSDT','1m','REGIME',limit=100,now_ms=10**9)
        db.write_klines([dict(self.clients[-1],open_time=65*60000,close_time=66*60000-1)])
        source=regime_inputs.open_sources()
        try:
            with intelligence_audit.reader() as conn:
                result=history.progress(conn,source,'BTCUSDT','1m','REGIME',data_policy.read(),aggregation_processor.generation('REGIME'),at=10**9)
                self.assertEqual(result['status'],'WAITING_FOR_FEATURE_CHECKPOINT');self.assertEqual(result['pending_candles'],1)
        finally:source.close()
        conn=features_store.open_db()
        with conn:conn.execute('INSERT INTO feature_replay_jobs VALUES (?,?,?,?,?,?,?,?)',('BTCUSDT','1m','next',64*60000,-1,'[]',None,'[]'))
        conn.close();source=regime_inputs.open_sources()
        try:
            with intelligence_audit.reader() as conn:
                result=history.progress(conn,source,'BTCUSDT','1m','REGIME',data_policy.read(),aggregation_processor.generation('REGIME'),at=10**9)
                self.assertEqual(result['status'],'FEATURE_REPLAY_PENDING')
        finally:source.close()


class Scheduling(unittest.TestCase):
    def test_history_has_fair_bounded_turns_and_independent_live_budget(self):
        seen=[]
        def step(s,t,e,**kwargs):
            seen.append((s,t,e));return dict(processed=kwargs['limit'],status='processed')
        with patch.object(history,'_cursor',0),patch.object(history,'_messages',{}),patch.object(history,'advance',side_effect=step),contextlib.redirect_stdout(io.StringIO()):
            for _ in range(12):self.assertLessEqual(history.maintenance(['BTC','ETH'],['1h'],max_bars=100,time_budget=10),100)
        self.assertIn(('ETH','1h','REGIME'),seen)
        with patch.object(live.regime_research,'catch_up',return_value=dict(processed=0,status='waiting')),patch.object(history,'maintenance',return_value=7) as replay:
            self.assertEqual(live.maintenance(['BTC'],['1h'],max_pairs=1),7)
            replay.assert_called_once()

    def test_empty_scope_and_busy_scope_do_not_spin(self):
        with patch.object(history,'advance',side_effect=TimeoutError('busy')) as step,patch.object(history,'_cursor',0):
            self.assertEqual(history.maintenance([],['1h']),0);step.assert_not_called()
            self.assertEqual(history.maintenance(['BTC'],['1h'],time_budget=10),0)
            self.assertEqual(step.call_count,1);self.assertEqual(history._cursor,1)
