"""Read-only readiness and causal forward outcomes; never portfolio profitability."""
import copy
import sqlite3
import unittest
from unittest.mock import patch
from Section_1_Global_Core import intelligence_evaluation as evaluation,intelligence_audit as audit,aggregation_processor,data_policy
from Section_1_Global_Core.memory_storage.Storage import engine_store
import test_regime_history as fixtures
from Section_1_Global_Core import regime_research as research


def event(i=0,delay=0,direction='BULLISH'):
    close=(i+1)*60000-1
    return dict(candle_open_time=i*60000,candle_close_time=close,as_of=close+1,available_at=close+1+delay,
        classification=dict(direction=direction),mode='CONFIRMED',data_quality='VALID',confirmation=dict(status='CONFIRMED'),confidence=.8,coverage=1.)


class ForwardOutcomes(unittest.TestCase):
    def setUp(self):
        self.conn=sqlite3.connect(':memory:');self.addCleanup(self.conn.close)
        self.conn.execute("ATTACH DATABASE ':memory:' AS raw")
        self.conn.execute('CREATE TABLE raw.klines(symbol,interval,open_time,close_time,open,close)')
        self.conn.executemany('INSERT INTO raw.klines VALUES (?,?,?,?,?,?)',[('BTCUSDT','1m',i*60000,(i+1)*60000-1,100.+i,101.+i) for i in range(12)])

    def study(self,rows,**kwargs):return evaluation.study(rows,self.conn,'BTCUSDT','1m',now_ms=1000000,horizons=(1,3),**kwargs)

    def test_actual_publication_cannot_enter_at_prior_bar_open(self):
        exact=self.study([event()]);delayed=self.study([event(delay=1)])
        self.assertEqual(exact['sample_events'][0]['entry_open'],60000)
        self.assertEqual(delayed['sample_events'][0]['entry_open'],120000)
        one=exact['groups'][0]
        self.assertAlmostEqual(one['mean_gross_bps'],10000/101)
        self.assertAlmostEqual(one['mean_net_bps'],10000/101-12)

    def test_reconstruction_is_explicit_and_late_publication_skipped(self):
        row=event(delay=300000)
        real=self.study([row]);sim=self.study([row],availability='RECONSTRUCTED_CLOSE')
        self.assertEqual(real['conclusion'],'NO_ELIGIBLE_OUTCOMES');self.assertEqual(real['excluded']['STALE_AT_PUBLICATION'],1)
        self.assertEqual(sim['sample_events'][0]['entry_open'],60000)
        self.assertEqual(sim['availability'],'RECONSTRUCTED_CLOSE')

    def test_transition_warmup_unknown_reset_and_evidence_filters(self):
        rows=[event(i) for i in range(5)];rows[2]['classification']['direction']='NEUTRAL'
        result=self.study(rows,since=120000)
        self.assertEqual(result['events'],1);self.assertEqual(result['sample_events'][0]['source_candle'],180000)
        rows=[event(i,direction='BULLISH' if i%2==0 else 'BEARISH') for i in range(5)]
        result=self.study(rows,min_confidence=.9);self.assertEqual(result['events'],0)
        self.assertEqual(self.study(rows,max_events=2)['events'],2)
        self.assertTrue(self.study(rows,max_rows=2)['truncated'])

    def test_split_end_purge_missing_bars_and_tail(self):
        result=self.study([event()],split=180000,until=300000)
        self.assertEqual(result['excluded']['HORIZON_3_SPLIT_PURGED'],1)
        self.assertEqual(len(result['groups']),1)
        result=self.study([event()],until=180000)
        self.assertEqual(result['excluded']['HORIZON_3_END_PURGED'],1)
        self.conn.execute('DELETE FROM raw.klines WHERE open_time=120000')
        result=self.study([event()]);self.assertEqual(result['excluded']['HORIZON_3_GAP_OR_TAIL'],1)
        result=self.study([event(11)]);self.assertEqual(result['conclusion'],'NO_ELIGIBLE_OUTCOMES')

    def test_invalid_policies_and_nonfinite_prices(self):
        for kwargs in (dict(cost_bps=-1),dict(min_coverage=1.1),dict(max_rows=0),dict(availability='imaginary')):
            with self.assertRaises(ValueError):self.study([],**kwargs)
        self.conn.execute('UPDATE raw.klines SET open=0 WHERE open_time=60000')
        self.assertEqual(self.study([event()])['conclusion'],'NO_ELIGIBLE_OUTCOMES')


class Readiness(unittest.TestCase):
    def setUp(self):fixtures.RegimeHistory.setUp(self)

    def test_missing_memory_does_not_create_it(self):
        self.assertFalse(engine_store.DB_PATH.exists())
        with audit.reader() as conn:self.assertIsNone(conn)
        self.assertFalse(engine_store.DB_PATH.exists())

    def test_index_generation_epoch_and_feature_guards_are_read_only(self):
        row=research.catch_up('BTCUSDT','1m',limit=100,now_ms=1000000000)
        aggregation_processor.observe('BTCUSDT','1m','REGIME',row,now_ms=1000000001)
        generation=aggregation_processor.generation('REGIME');policy=data_policy.read()
        with audit.reader() as conn:
            run,status=audit.select_run(conn,'BTCUSDT','1m','REGIME',policy,generation,at=1000000001)
            self.assertEqual(status,'READY');self.assertEqual(run['run_id'],row['run_id'])
            self.assertEqual(audit.select_run(conn,'BTCUSDT','1m','REGIME',policy,'old',at=1000000001)[1],'OUTDATED_PRODUCER')
            changed=copy.deepcopy(policy);changed['epochs']['interval:1m']=99
            self.assertEqual(audit.select_run(conn,'BTCUSDT','1m','REGIME',changed,generation,at=1000000001)[1],'OUTDATED_DATA_GENERATION')
            with self.assertRaises(sqlite3.OperationalError):conn.execute('DELETE FROM engine_results')
        result=audit.report(['BTCUSDT'],['1m'],now_ms=1000000002)
        self.assertEqual(result['pairs'][0]['engines']['REGIME']['status'],'STALE_OR_BACKLOG')
        result=evaluation.evaluate(['BTCUSDT'],['1m'],engine='REGIME',now_ms=1000000002)
        self.assertEqual(result['pairs'][0]['status'],'EVALUATED')
        self.assertEqual(result['pairs'][0]['conclusion'],'NO_ELIGIBLE_OUTCOMES')
        self.assertGreater(result['pairs'][0]['excluded']['STALE_AT_PUBLICATION'],0)
        from Section_1_Global_Core.memory_storage.Storage import features_store
        conn=features_store.open_db()
        with conn:conn.execute("UPDATE feature_calculation_versions SET signature='outdated'")
        conn.close()
        result=audit.report(['BTCUSDT'],['1m'],now_ms=1000000002)
        self.assertEqual(result['pairs'][0]['engines']['REGIME']['status'],'FEATURE_REPLAY_PENDING_OR_CHANGED')
