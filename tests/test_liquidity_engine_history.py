"""Read-only as-of recorder projection and immutable analytical history."""
import copy
import json
import unittest
from unittest.mock import patch
import test_regime_history as fixtures
from test_liquidity_engine import snapshot, observation
from Section_1_Global_Core import regime_research as research, liquidity_inputs
from Section_1_Global_Core.liquidity import store
from Section_1_Global_Core.memory_storage.Storage import engine_store
from Section_5_Market_Regime.engines import liquidity
from Section_5_Market_Regime.engines.liquidity_config import LiquidityConfig


class LiquidityHistory(unittest.TestCase):
    def setUp(self):
        fixtures.RegimeHistory.setUp(self)
        self.enterContext(patch.object(store,'DB_PATH',self.root/'recorded-liquidity.db'))

    def write_observations(self,s):
        bundle=observation(s);sample=copy.deepcopy(bundle['sample']);sample['analytics']={'60s':sample.pop('flow_60s')}
        # A large display payload must not be copied into analytical inputs.
        sample['bands']=[dict(low=1.,high=2.,notional_usdt=100.)]*2000
        base=copy.deepcopy(sample);base.update(available_ms=s['as_of']-300000,sampled_ms=s['as_of']-300000,context=copy.deepcopy(bundle['oi_baseline']['context']))
        writer=store.open_writer()
        try:
            with writer:
                store.write_sample(writer,base,available_ms=base['available_ms'])
                store.write_sample(writer,sample,available_ms=sample['available_ms'])
        finally:writer.close()
        return bundle

    def test_projection_known_time_global_gap_and_no_missing_database_creation(self):
        s=snapshot(40);cfg=LiquidityConfig()
        with liquidity_inputs.reader() as conn:self.assertEqual(liquidity_inputs.project(conn,s,cfg)['status'],'UNAVAILABLE')
        self.assertFalse(store.DB_PATH.exists())
        self.write_observations(s)
        with liquidity_inputs.reader() as conn:
            projected=liquidity_inputs.project(conn,s,cfg)
            self.assertEqual(projected['status'],'RECORDED');self.assertNotIn('bands',projected['sample'])
            self.assertLessEqual(projected['sample']['available_ms'],s['as_of'])
            self.assertLessEqual(projected['oi_baseline']['available_ms'],s['as_of']-300000)
        earlier=copy.deepcopy(s);earlier['as_of']-=1000
        with liquidity_inputs.reader() as conn:
            projected=liquidity_inputs.project(conn,earlier,cfg)
            # The newer sample is unavailable; the old one cannot pass freshness.
            self.assertLessEqual(projected['sample']['available_ms'],earlier['as_of'])
            s['observations']=projected
            result,_=liquidity.evaluate(s)
            self.assertEqual(result['classification']['book_state'],'UNKNOWN')
        writer=store.open_writer()
        try:
            with writer:store.set_status(writer,'*','offline','connection lost',now_ms=s['as_of']-100)
        finally:writer.close()
        with liquidity_inputs.reader() as conn:s['observations']=liquidity_inputs.project(conn,s,cfg)
        result,_=liquidity.evaluate(s);self.assertEqual(result['classification']['book_state'],'UNKNOWN')
        self.assertIn('OBSERVATION_GAP',result['quality_flags'])

    def test_committed_recorder_input_survives_pruning_and_exact_replay(self):
        client=self.clients[33]
        s=snapshot(33,candle={k:client[k] for k in ('open','high','low','close')});self.write_observations(s)
        row=research.catch_up('BTCUSDT','1m',since=client['open_time'],limit=1,engine_name='LIQUIDITY',now_ms=10**9)
        self.assertEqual(row['processed'],1);self.assertEqual(row['latest']['classification']['book_state'],'DEEP')
        self.assertEqual(row['latest']['classification']['derivatives_state'],'BUILDING')
        conn=engine_store.open_db()
        try:
            bundle=engine_store.input_bundle(conn,row['run_id'],client['open_time']);bundle['computed_at']=10**9
            expected,state=liquidity.evaluate(bundle)
            self.assertEqual(expected,row['latest']);self.assertEqual(state,engine_store.load(conn,row['run_id'])[1])
        finally:conn.close()
        writer=store.open_writer()
        try:
            with writer:writer.execute('DELETE FROM samples')
        finally:writer.close()
        conn=engine_store.open_db()
        try:
            restored=engine_store.input_bundle(conn,row['run_id'],client['open_time']);restored['computed_at']=10**9
            self.assertEqual(liquidity.evaluate(restored)[0],row['latest'])
            self.assertNotIn('bands',restored['observations']['sample'])
        finally:conn.close()
        report=research.diagnostics(row['run_id']);self.assertIn('dimension_counts',report);self.assertNotIn('trend_counts',report)
        self.assertEqual(report['dimension_counts']['book_state'],{'DEEP':1})

    def test_recent_seed_resume_unavailable_observations_and_no_dependencies(self):
        first=research.catch_up('BTCUSDT','1m',since=None,limit=20,engine_name='LIQUIDITY',now_ms=10**9)
        second=research.catch_up('BTCUSDT','1m',since=None,limit=20,engine_name='LIQUIDITY',now_ms=10**9)
        self.assertEqual(first['processed'],20);self.assertEqual(second['processed'],12)
        self.assertEqual(first['run_id'],second['run_id']);self.assertEqual(first['dependency_processed'],0)
        self.assertEqual(second['latest']['classification']['book_state'],'UNKNOWN')
        self.assertFalse(store.DB_PATH.exists())

    def test_corrupt_optional_recorder_packet_does_not_block_structural_history(self):
        writer=store.open_writer()
        try:
            with writer:writer.execute('INSERT INTO samples VALUES (?,?,?,?)',('BTCUSDT',34*60000-1,34*60000-1,b'corrupt'))
        finally:writer.close()
        result=research.catch_up('BTCUSDT','1m',since=33*60000,limit=1,engine_name='LIQUIDITY',now_ms=10**9)
        self.assertEqual(result['processed'],1);self.assertEqual(result['latest']['classification']['book_state'],'UNKNOWN')
        self.assertIn('OBSERVED_DATA_UNAVAILABLE',result['latest']['quality_flags'])

    def test_bad_oi_baseline_does_not_erase_current_book(self):
        s=snapshot(40);self.write_observations(s)
        writer=store.open_writer()
        try:
            with writer:writer.execute('UPDATE samples SET payload=? WHERE available_ms=?',(b'corrupt',s['as_of']-300000))
        finally:writer.close()
        with liquidity_inputs.reader() as conn:s['observations']=liquidity_inputs.project(conn,s,LiquidityConfig())
        result,_=liquidity.evaluate(s)
        self.assertEqual(result['classification']['book_state'],'DEEP')
        self.assertEqual(result['classification']['derivatives_state'],'UNKNOWN')
        self.assertIsNone(s['observations']['oi_baseline'])
