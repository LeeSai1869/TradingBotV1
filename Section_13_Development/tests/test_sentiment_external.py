"""Optional sources: causal revisions, independent failure, no implicit networking."""
import copy
import io
import json
import sqlite3
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from Section_1_Global_Core import sentiment_external as sources,sentiment_inputs
from Section_5_Market_Regime.engines import sentiment
from test_sentiment_engine import snapshot


def profile(identifier='news',category='NEWS',**kwargs):
    return dict(provider_id=identifier,category=category,source_name='Test provider',publisher_group=identifier,
        method='Synthetic scored fixture',terms_url='https://example.org/terms',enabled=True,reliability=1.,**kwargs)


def record(**kwargs):
    return dict(dict(event_id='event',revision='1',asset='BTCUSDT',published_ms=100,kind='AGGREGATE_SENTIMENT',score=.8),**kwargs)


class ExternalSources(unittest.TestCase):
    def setUp(self):
        self.temp=self.enterContext(tempfile.TemporaryDirectory());self.path=Path(self.temp)/'sources.db'
        self.enterContext(patch.object(sources,'DB_PATH',self.path))

    def project(self,at=200):
        with sources.reader() as conn:return sources.project(conn,'BTCUSDT',at)

    def test_missing_store_is_read_only_and_provider_disabled_by_default_example(self):
        self.assertEqual(self.project(),[]);self.assertFalse(self.path.exists())
        cfg=profile();cfg['enabled']=False;sources.configure(cfg,now_ms=0)
        with self.assertRaises(ValueError):sources.import_records('news',[record()],received_ms=150)
        with patch('urllib.request.build_opener') as network:
            with self.assertRaises(ValueError):sources.fetch('news')
            network.assert_not_called()

    def test_causal_revision_and_configuration_history(self):
        sources.configure(profile(),now_ms=0)
        self.assertEqual(sources.import_records('news',[record()],received_ms=150),1)
        self.assertEqual(self.project(149),[])
        before=self.project(150);self.assertEqual(before[0]['score'],.8)
        self.assertEqual(sources.import_records('news',[record()],received_ms=151),0)
        with self.assertRaises(ValueError):sources.import_records('news',[record(score=-.8)],received_ms=160)
        sources.import_records('news',[record(revision='10',score=None)],received_ms=180)
        self.assertEqual(self.project(175),before);self.assertIsNone(self.project(180)[0]['score'])
        sources.import_records('news',[record(revision='2',score=-.9)],received_ms=190)
        self.assertEqual(self.project(190)[0]['revision'],'2')  # receipt order, never lexical version order
        cfg=profile();cfg['enabled']=False;sources.configure(cfg,now_ms=200)
        self.assertEqual(self.project(199)[0]['score'],-.9);self.assertEqual(self.project(200),[])

    def test_validation_and_atomic_import(self):
        sources.configure(profile(),now_ms=0)
        for invalid in (record(score=float('nan')),record(published_ms=201),record(kind='UNSCORED_HEADLINE')):
            with self.assertRaises(ValueError):sources.import_records('news',[record(event_id='good'),invalid],received_ms=200)
            self.assertEqual(self.project(),[])
        for config in (dict(profile(),endpoint='http://example.org'),dict(profile(),auth_env='secret value',auth_header='Authorization'),dict(profile(),reliability=0)):
            with self.assertRaises(ValueError):sources.configure(config,now_ms=1)

    def test_manual_fetch_uses_env_only_and_canonical_response(self):
        sources.configure(profile(endpoint='https://example.org/scores',auth_env='TEST_SENTIMENT_KEY',auth_header='Authorization',auth_prefix='Bearer '),now_ms=0)
        response=io.BytesIO(json.dumps([record()]).encode())
        with patch.dict('os.environ',{'TEST_SENTIMENT_KEY':'private-token'}),patch('urllib.request.build_opener') as opener:
            opener.return_value.open.return_value=response
            self.assertEqual(sources.fetch('news'),1)
            request=opener.return_value.open.call_args.args[0]
            self.assertEqual(request.get_header('Authorization'),'Bearer private-token')
        self.assertNotIn('private-token',self.path.read_bytes().decode(errors='ignore'))
        self.assertIsNone(sources.NoRedirect().redirect_request(None,None,None,None,None,None))

    def test_external_only_engine_and_frozen_projection(self):
        s=snapshot();at=s['as_of']
        sources.configure(profile(),now_ms=0)
        sources.import_records('news',[record(published_ms=at-1000)],received_ms=at-500)
        with sources.reader() as conn:s['sentiment_sources']=sentiment_inputs.project(sentiment_inputs.Sources(None,conn),s)
        original=copy.deepcopy(s)
        result,_=sentiment.evaluate(s)
        self.assertEqual(result['classification']['sentiment'],'BULLISH');self.assertEqual(result['coverage'],.2)
        self.assertEqual(result['classification']['positioning'],'UNKNOWN');self.assertEqual(s,original)
        self.assertNotIn('NEWS',result['measurements']['unavailable_sources'])
        self.assertEqual(sentiment.evaluate(original)[0],result)

    def test_freshness_conflict_dedup_and_unscored_are_explicit(self):
        s=snapshot();at=s['as_of']
        for identifier,category,score in [('news','NEWS',.8),('social','SOCIAL',-.8)]:
            sources.configure(profile(identifier,category),now_ms=0)
            sources.import_records(identifier,[record(published_ms=at-1000,score=score)],received_ms=at-500)
        with sources.reader() as conn:s['sentiment_sources']['external']=sources.project(conn,'BTCUSDT',at)
        result,_=sentiment.evaluate(s)
        self.assertEqual(result['classification']['sentiment'],'NEUTRAL');self.assertAlmostEqual(result['coverage'],.8)
        self.assertAlmostEqual(result['confidence'],.4);self.assertIn('CONFLICTING_EXTERNAL_SENTIMENT',result['quality_flags'])
        rows=s['sentiment_sources']['external'];rows[1]['publisher_group']=rows[0]['publisher_group']
        result,_=sentiment.evaluate(s);self.assertAlmostEqual(result['coverage'],.6)
        self.assertIn('CORRELATED_PUBLISHER_GROUP_EXCLUDED',result['quality_flags'])
        for row in rows:row['published_ms']=0;row['kind']='UNSCORED_HEADLINE';row['score']=None
        result,_=sentiment.evaluate(s);self.assertEqual(result['coverage'],.4)
        rows[0].update(kind='AGGREGATE_SENTIMENT',score=.8,published_ms=at-1000)
        from Section_5_Market_Regime.engines.sentiment_config import SentimentConfig
        result,_=sentiment.evaluate(s,SentimentConfig(news_ttl_ms=100));self.assertIn('EXTERNAL_STALE:news',result['quality_flags'])
        s['sentiment_sources']=None
        self.assertEqual(sentiment.evaluate(s)[0]['coverage'],0.)

    def test_market_wide_downweight_and_causal_rejection(self):
        s=snapshot();at=s['as_of'];sources.configure(profile(),now_ms=0)
        sources.import_records('news',[record(asset='*',published_ms=at-1000)],received_ms=at-500)
        with sources.reader() as conn:rows=sources.project(conn,'BTCUSDT',at)
        s['sentiment_sources']['external']=rows
        self.assertAlmostEqual(sentiment.evaluate(s)[0]['coverage'],.5)
        rows[0]['received_ms']=at+1
        self.assertEqual(sentiment.evaluate(s)[0]['coverage'],.4)

    def test_independent_positive_categories_and_later_profile_revision(self):
        s=snapshot();at=s['as_of']
        for identifier,category in [('news','NEWS'),('social','SOCIAL')]:
            sources.configure(profile(identifier,category),now_ms=0)
            sources.import_records(identifier,[record(published_ms=at-1000)],received_ms=at-500)
        cfg=profile();cfg['reliability']=.9;sources.configure(cfg,now_ms=at-100)
        with sources.reader() as conn:s['sentiment_sources']['external']=sources.project(conn,'BTCUSDT',at)
        result,_=sentiment.evaluate(s)
        self.assertEqual(result['classification']['sentiment'],'EXTREMELY_BULLISH')
        self.assertAlmostEqual(result['coverage'],.78)
        self.assertNotIn('BROAD_SENTIMENT_AND_CROWDING_UNAVAILABLE',result['quality_flags'])
        self.assertEqual(result['measurements']['funding_scope'],'DERIVATIVES_FUNDING_TILT_ONLY')

    def test_corrupt_optional_memory_preserves_derivative_context(self):
        conn=sqlite3.connect(':memory:');self.addCleanup(conn.close)
        s=snapshot()
        projection=sentiment_inputs.project(sentiment_inputs.Sources(None,conn),s)
        self.assertTrue(projection['external_error'])
        s['sentiment_sources']['external_error']=projection['external_error']
        result,_=sentiment.evaluate(s)
        self.assertEqual(result['coverage'],.4)
        self.assertEqual(result['classification']['sentiment'],'BULLISH')
        self.assertIn('EXTERNAL_SOURCE_MEMORY_UNAVAILABLE',result['quality_flags'])


class ExternalHistory(unittest.TestCase):
    def setUp(self):
        import test_regime_history as fixtures
        fixtures.RegimeHistory.setUp(self)
        from Section_1_Global_Core.liquidity import store
        self.enterContext(patch.object(store,'DB_PATH',self.root/'missing-recorder.db'))
        self.enterContext(patch.object(sources,'DB_PATH',self.root/'optional-sources.db'))

    def test_runner_freezes_minimal_external_bundle_and_restores_after_source_edit(self):
        from Section_1_Global_Core import regime_research as research
        from Section_1_Global_Core.memory_storage.Storage import engine_store
        client=self.clients[33];at=client['close_time']+1
        sources.configure(profile(),now_ms=0)
        sources.import_records('news',[record(published_ms=at-1000)],received_ms=at-500)
        row=research.catch_up('BTCUSDT','1m',since=client['open_time'],limit=1,engine_name='SENTIMENT',now_ms=10**9)
        self.assertEqual(row['processed'],1);self.assertEqual(row['latest']['classification']['sentiment'],'BULLISH')
        self.assertEqual(row['latest']['coverage'],.2)
        sources.import_records('news',[record(revision='2',score=-.9,published_ms=at-1000)],received_ms=at+1)
        conn=engine_store.open_db()
        try:
            bundle=engine_store.input_bundle(conn,row['run_id'],client['open_time']);bundle['computed_at']=10**9
            self.assertEqual(bundle['sentiment_sources']['external'][0]['score'],.8)
            self.assertEqual(sentiment.evaluate(bundle)[0],row['latest'])
        finally:conn.close()
