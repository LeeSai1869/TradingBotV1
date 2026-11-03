"""Immutable external-source lineage, as-of joins and independent runner work."""
import copy
import json
import unittest
from unittest.mock import patch
import test_regime_history as fixtures
from test_sentiment_engine import snapshot
from Section_1_Global_Core import regime_research as research, sentiment_inputs
from Section_1_Global_Core.liquidity import store
from Section_1_Global_Core.memory_storage.Storage import engine_store
from Section_5_Market_Regime.engines import sentiment


class SentimentHistory(unittest.TestCase):
    def setUp(self):
        fixtures.RegimeHistory.setUp(self)
        self.enterContext(patch.object(store,'DB_PATH',self.root/'sentiment-source.db'))

    def prepare(self,index=33):
        client=self.clients[index];s=snapshot(index,rate=.0001,baseline_rate=0.)
        source=s['sentiment_sources'];current=copy.deepcopy(source['current']);baseline=copy.deepcopy(source['baseline'])
        for packet in (current,baseline):
            packet['metrics']['mid']=client['close'];packet['context'].update(mark_price=client['close'],index_price=client['close'])
            packet['bands']=[dict(low=1.,high=2.,notional_usdt=100.)]*1000
        writer=store.open_writer()
        try:
            with writer:
                store.write_sample(writer,baseline,available_ms=baseline['available_ms'])
                store.write_sample(writer,current,available_ms=current['available_ms'])
        finally:writer.close()
        return client

    def test_actual_projection_history_restore_and_retention_independence(self):
        client=self.prepare()
        row=research.catch_up('BTCUSDT','1m',since=client['open_time'],limit=1,engine_name='SENTIMENT',now_ms=10**9)
        self.assertEqual(row['processed'],1);self.assertEqual(row['dependency_processed'],0)
        self.assertEqual(row['latest']['classification']['sentiment'],'BULLISH')
        self.assertEqual(row['latest']['classification']['stability'],'IMPROVING')
        self.assertEqual(row['latest']['classification']['positioning'],'UNKNOWN')
        conn=engine_store.open_db()
        try:
            bundle=engine_store.input_bundle(conn,row['run_id'],client['open_time']);bundle['computed_at']=10**9
            expected,state=sentiment.evaluate(bundle)
            self.assertEqual(expected,row['latest']);self.assertEqual(state,engine_store.load(conn,row['run_id'])[1])
            self.assertNotIn('bands',bundle['sentiment_sources']['current'])
            self.assertEqual(bundle['sentiment_sources']['current']['context']['funding_rate'],.0001)
        finally:conn.close()
        writer=store.open_writer()
        try:
            with writer:writer.execute('DELETE FROM samples')
        finally:writer.close()
        conn=engine_store.open_db()
        try:
            bundle=engine_store.input_bundle(conn,row['run_id'],client['open_time']);bundle['computed_at']=10**9
            self.assertEqual(sentiment.evaluate(bundle)[0],row['latest'])
        finally:conn.close()
        report=research.diagnostics(row['run_id']);self.assertEqual(report['dimension_counts']['sentiment'],{'BULLISH':1});self.assertNotIn('trend_counts',report)

    def test_missing_recorder_no_creation_automatic_resume_and_unknown(self):
        first=research.catch_up('BTCUSDT','1m',since=None,limit=20,engine_name='SENTIMENT',now_ms=10**9)
        second=research.catch_up('BTCUSDT','1m',since=None,limit=20,engine_name='SENTIMENT',now_ms=10**9)
        self.assertEqual(first['processed'],20);self.assertEqual(second['processed'],12);self.assertEqual(first['run_id'],second['run_id'])
        self.assertEqual(second['latest']['classification'],sentiment.UNKNOWN);self.assertFalse(store.DB_PATH.exists())

    def test_future_publication_and_global_gap_are_not_joined(self):
        client=self.prepare();s=snapshot(33);s['candle']={k:client[k] for k in ('open','high','low','close')}
        with sentiment_inputs.reader() as conn:
            projected=sentiment_inputs.project(conn,dict(s,as_of=s['as_of']-1000))
        self.assertLessEqual(projected['current']['available_ms'],s['as_of']-1000)
        s['sentiment_sources']=projected
        self.assertEqual(sentiment.evaluate(s)[0]['classification'],sentiment.UNKNOWN)
        writer=store.open_writer()
        try:
            with writer:store.set_status(writer,'*','offline','gap',now_ms=s['as_of']-100)
        finally:writer.close()
        with sentiment_inputs.reader() as conn:s['sentiment_sources']=sentiment_inputs.project(conn,s)
        self.assertEqual(sentiment.evaluate(s)[0]['classification'],sentiment.UNKNOWN)

    def test_corrupt_baseline_preserves_current_funding_and_runner_budget(self):
        client=self.prepare();writer=store.open_writer()
        try:
            with writer:writer.execute('UPDATE samples SET payload=? WHERE available_ms=?',(b'corrupt',client['close_time']+1-300000))
        finally:writer.close()
        row=research.catch_up('BTCUSDT','1m',since=client['open_time'],limit=1,engine_name='SENTIMENT',now_ms=10**9)
        self.assertEqual(row['latest']['classification']['sentiment'],'BULLISH');self.assertEqual(row['latest']['classification']['stability'],'UNKNOWN')
        from Section_1_Global_Core import analytical_processor as worker
        worker._cursor=8;worker._status.clear()
        with patch.object(research,'catch_up',return_value=dict(processed=20,status='processed',latest={})) as call:
            self.assertEqual(worker.maintenance(['BTCUSDT'],['1m'],max_bars=20,time_budget=10,max_pairs=1),20)
            self.assertEqual(call.call_args.kwargs['engine_name'],'SENTIMENT')
