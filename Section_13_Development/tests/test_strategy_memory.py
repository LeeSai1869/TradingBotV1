"""Real isolated stores: projection, missing data, exact context and coin isolation."""
import json
import unittest
from unittest.mock import patch

import test_regime_history as fixtures
from Section_8_Decision_Engine import strategy_memory as m, strategy_analyzer as a
from Section_1_Global_Core import regime_research, analytical_history, aggregation_processor
from Section_1_Global_Core.memory_storage.Storage import features_store,engine_store,adcn_store


class StrategyMemory(unittest.TestCase):
    def setUp(self):
        fixtures.RegimeHistory.setUp(self)
        engine_store.open_db().close()

    def test_catalog_includes_raw_only_coin_and_all_schema_fields(self):
        u=m.universe();self.assertIn('BTCUSDT',u['symbols']);self.assertIn('SUIUSDT',u['symbols'])
        self.assertGreater(u['feature_columns'],500);self.assertGreater(u['adcn_columns'],10)
        meta=m.metadata('BTCUSDT','1m')
        fields={f['id'] for f in meta['fields']}
        self.assertIn('feature.nearest_support',fields);self.assertIn('adcn.scalp_score',fields)
        self.assertIn('context.1M.REGIME.primary',fields)

    def test_only_requested_features_are_loaded_and_values_are_unmodified(self):
        s=m.load('BTCUSDT','1m',fields=['feature.ema50','adcn.signal_type'],now_ms=10**9)
        self.assertEqual(len(s['candles']),65)
        self.assertIn('ema50',s['exported_feature_columns']);self.assertNotIn('ema200',s['exported_feature_columns'])
        c=features_store.open_db()
        try:v=c.execute('SELECT ema50 FROM features WHERE symbol=? AND interval=? AND open_time=?',('BTCUSDT','1m',40*60000)).fetchone()[0]
        finally:c.close()
        self.assertEqual(s['candles'][40]['features']['ema50'],v)
        self.assertEqual(s['candles'][1]['adcn']['signal_type'],'BUY')
        self.assertEqual(a.Memory(s).value(1,'adcn.signal_type'),('BUY',None))

    def test_missing_feature_row_remains_unknown_without_dropping_prices(self):
        c=features_store.open_db()
        with c:c.execute('DELETE FROM features WHERE symbol=? AND interval=? AND open_time=?',('BTCUSDT','1m',5*60000))
        c.close();s=m.load('BTCUSDT','1m',fields=['feature.rsi'],now_ms=10**9)
        self.assertEqual(len(s['candles']),65)
        self.assertFalse(s['candles'][5]['feature_valid'])
        self.assertIsNone(a.Memory(s).value(5,'feature.rsi')[0])

    def test_pending_replay_does_not_use_stale_features(self):
        c=features_store.open_db()
        with c:c.execute('INSERT INTO feature_replay_jobs VALUES (?,?,?,?,?,?,?,?)',('BTCUSDT','1m','new',64*60000,-1,'[]',None,'[]'))
        c.close();s=m.load('BTCUSDT','1m',fields=['feature.ema50'],limit=4,now_ms=10**9)
        self.assertFalse(s['memory']['feature_current']);self.assertTrue(all(not r['feature_valid'] for r in s['candles']))

    def selective_job(self, columns, through=-1):
        from Section_4_Features.execution.components import current_signature
        c=features_store.open_db()
        with c:
            c.execute("UPDATE feature_calculation_versions SET signature='',invalidated_columns=? WHERE symbol='BTCUSDT' AND interval='1m'",(json.dumps(columns),))
            c.execute('INSERT INTO feature_replay_jobs VALUES (?,?,?,?,?,?,?,?)',('BTCUSDT','1m',current_signature(),64*60000,through,'[]',None,json.dumps(columns)))
        c.close()

    def test_structure_repair_preserves_stored_rsi_and_di_inputs(self):
        before=m.load('BTCUSDT','1m',fields=['feature.rsi','di.abs_spread'],now_ms=10**9)
        self.selective_job(['current_structure','structure_events'])
        after=m.load('BTCUSDT','1m',fields=['feature.rsi','di.abs_spread','feature.current_structure'],now_ms=10**9)
        self.assertFalse(after['memory']['feature_current'])
        self.assertTrue(after['memory']['feature_inputs_compatible'])
        old,new=a.Memory(before),a.Memory(after)
        for i in range(65):
            for field in ('feature.rsi','feature.di_plus','feature.di_minus','di.abs_spread'):
                self.assertEqual(new.value(i,field),old.value(i,field))
            self.assertIsNone(new.value(i,'feature.current_structure')[0])
        self.assertIsNotNone(new.value(60,'di.abs_spread')[0])
        from test_strategy_analyzer import config
        strategy=config()
        strategy['branches'][0]['when']={'all':[dict(field='di.abs_spread',op='gte',value=0,stage='trigger'),dict(field='feature.rsi',op='gte',value=0,stage='activate')]}
        strategy['branches'][1]['when']=dict(field='price.close',op='available')
        expected,actual=a.analyze(before,strategy),a.analyze(after,strategy)
        self.assertGreater(len(actual['signals']),0)
        self.assertEqual(actual['signals'],expected['signals'])

    def test_affected_cells_only_become_available_through_repair_cursor(self):
        self.selective_job(['rsi','di_minus'],through=40*60000)
        s=m.load('BTCUSDT','1m',fields=['feature.rsi','feature.ema50','di.abs_spread'],now_ms=10**9)
        memory=a.Memory(s)
        self.assertIsNotNone(memory.value(40,'feature.rsi')[0])
        self.assertIsNone(memory.value(41,'feature.rsi')[0])
        self.assertIsNone(memory.value(41,'di.abs_spread')[0])
        self.assertIsNotNone(memory.value(41,'feature.ema50')[0])

    def test_unknown_generation_without_selective_job_stays_blocked(self):
        c=features_store.open_db()
        with c:c.execute("UPDATE feature_calculation_versions SET signature='unknown'")
        c.close()
        s=m.load('BTCUSDT','1m',fields=['feature.rsi'],now_ms=10**9)
        self.assertTrue(all(not row['feature_valid'] for row in s['candles']))

    def test_date_window_and_warmup_are_bounded(self):
        s=m.load('BTCUSDT','1m',fields=['feature.ema50'],since=50*60000,until=60*60000,warmup=3,now_ms=10**9)
        self.assertGreater(s['candles'][0]['open_time'],40*60000)
        self.assertEqual(s['candles'][-1]['close_time'],60*60000-1)
        self.assertTrue(all(r['close_time']<60*60000 for r in s['candles']))

    def test_stored_context_is_read_without_running_a_classifier(self):
        regime_research.catch_up('BTCUSDT','1m',engine_name='REGIME',limit=65,now_ms=10**9)
        c=engine_store.open_db()
        run=c.execute('SELECT run_id,metadata FROM engine_runs').fetchone();meta=json.loads(run[1]);c.close()
        fake=dict(run_id=run[0],metadata=meta,cursor=64*60000)
        with patch.object(analytical_history,'select',return_value=(fake,'processed')),patch.object(regime_research,'catch_up',side_effect=AssertionError('must only read memory')):
            s=m.load('BTCUSDT','1m',fields=['context.1m.REGIME.primary','context.1m.REGIME.output.confidence'],now_ms=10**9)
        payload=s['engine_history']['1m:REGIME']['results']['3600000']
        value=a.Memory(s).value(60,'context.1m.REGIME.output.confidence')
        if payload['data_quality'] in ('VALID','PARTIAL'):self.assertEqual(value[0],payload['confidence'])
        self.assertIsNone(a.Memory(s).value(60,'context.4h.REGIME.primary')[0])

    def test_coin_reads_do_not_reuse_another_coins_prices(self):
        btc=m.load('BTCUSDT','1m',limit=1,now_ms=10**9)
        sui=m.load('SUIUSDT','1m',limit=1,now_ms=10**9)
        self.assertNotEqual(btc['source_id'],sui['source_id'])
        self.assertGreater(btc['candles'][0]['close'],100)
        self.assertEqual(sui['candles'][0]['close'],11)

    def test_history_index_refresh_after_read_start_does_not_hide_prefix(self):
        from Section_1_Global_Core import data_policy
        result=regime_research.catch_up('BTCUSDT','1m',engine_name='REGIME',limit=65,now_ms=10**9)
        c=engine_store.open_db()
        try:
            run=c.execute('SELECT run_id,metadata FROM engine_runs WHERE run_id=?',(result['run_id'],)).fetchone()
            meta=json.loads(run[1]);binding={k:meta[k] for k in ('identity','engine_version','config_hash','input_signature')}
            binding.update(raw_epoch=[0,0],revision='initial')
            with c:c.execute('INSERT OR REPLACE INTO engine_history_bindings VALUES (?,?,?,?,?,?,?,?)',
                            ('BTCUSDT','1m','REGIME',aggregation_processor.generation('REGIME'),run[0],json.dumps(binding),'processed',10**9+50))
        finally:c.close()
        s=m.load('BTCUSDT','1m',fields=['context.1m.REGIME.primary'],now_ms=10**9)
        history=s['engine_history']['1m:REGIME']['results']
        self.assertEqual(len(history),65)
        self.assertTrue(all(p['as_of']<=s['observed_as_of'] for p in history.values()))


if __name__=='__main__':unittest.main()
