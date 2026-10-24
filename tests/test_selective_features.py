from contextlib import ExitStack,nullcontext
import copy
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from test_complete_conversion import bar
from Section_4_Features import processor
from Section_4_Features.execution import components,selective,checkpoint
from Section_4_Features.execution.engine import Engine
from Section_4_Features.features import momentum,trend,volume_profile
from Section_1_Global_Core.memory_storage.Storage import db,klines_store,features_store,adcn_store
from Section_1_Global_Core.memory_storage.market_data import download_binance_history as downloader


class SelectiveFeatures(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.stack=ExitStack();self.addCleanup(self.stack.close)
        for store,name in ((klines_store,'klines'),(features_store,'features'),(adcn_store,'ADCN'),(downloader,'klines')):
            self.stack.enter_context(patch.object(store,'DB_PATH',Path(self.tmp.name)/(name+'.db')))
        self.stack.enter_context(patch.object(processor,'_epoch',return_value=(0,0)))
        self.stack.enter_context(patch.object(processor.data_policy,'enabled',return_value=True))
        self.stack.enter_context(patch.object(processor.data_policy,'locked',side_effect=nullcontext))
        downloader.open_db().close();processor._ENGINES.clear()
        self.clients=[bar(i,100+(i%17)*.7+(i%3)*.2) for i in range(220)]
        db.write_klines(self.clients)
        self.engine=Engine('ETHUSDT','1m');self.original=[self.engine.step(b) for b in self.clients]
        db.write_features(self.original)
        conn=features_store.open_db()
        with conn:conn.execute('INSERT INTO feature_engine_state VALUES (?,?,?,?)',('ETHUSDT','1m',self.clients[-1]['open_time'],checkpoint.dump(self.engine,(0,0))))
        conn.close()
        self.before=self.raw_features()
    def config(self,**changes):
        params={**self.engine.context.parameters,**changes}
        self.stack.enter_context(patch.object(components,'desired_parameters',return_value=params))
        self.stack.enter_context(patch.object(selective,'desired_parameters',return_value=params))
        return params
    def finish(self):
        for _ in range(20):
            processor.catch_up('ETHUSDT','1m')
            conn=features_store.open_db()
            try:job=selective.read_job(conn,'ETHUSDT','1m')
            finally:conn.close()
            if not job:return
            processor._ENGINES.clear() # Simulate a restart between bounded batches.
        self.fail('targeted job failed to finish')
    def raw_features(self):
        conn=features_store.open_db()
        try:return features_store.read_range(conn,'ETHUSDT','1m',0,10**12,mask_pending=False)
        finally:conn.close()

    def test_rsi_input_only_recalculates_rsi_and_preserves_every_other_column(self):
        params=self.config(rsiLen=11)
        reference=Engine('ETHUSDT','1m',params);expected=[reference.step(b) for b in self.clients]
        with patch.object(momentum,'calculate_dmi',side_effect=AssertionError('ADX must not run')),patch.object(trend,'calculate_ema',side_effect=AssertionError('EMA must not run')):
            self.finish()
        fields={'rsi','prev_rsi','rsi_change','bull_momentum_divergence','bear_momentum_divergence'}
        for old,new,ref in zip(self.before,self.raw_features(),expected):
            for field in old:
                if field in fields:self.assertEqual(new[field],ref[field],field)
                else:self.assertEqual(new[field],old[field],field)
        # The repaired RSI seed is merged into the main checkpoint for future bars.
        next_bar=bar(220,114);db.write_klines([next_bar]);processor._ENGINES.clear()
        processor.catch_up('ETHUSDT','1m')
        result=db.read_features('ETHUSDT','1m',next_bar['open_time'])
        expected_next=reference.step(next_bar)
        self.assertEqual(result['rsi'],expected_next['rsi'])
        self.assertEqual(result['ema50'],expected_next['ema50'])
        for key,value in expected_next.items():
            if value is not None and (features_store._translated_fields.get(key)=='string' or key.endswith('_type')):value=str(value)
            self.assertEqual(result[key],value,key)

    def test_legacy_checkpoint_repairs_only_reviewed_fvg_outputs_without_resetting_cursor(self):
        old=json.loads(checkpoint.dump(self.engine,(0,0)));old.pop('components')
        old['source']=components.baseline_sources()[1]
        conn=features_store.open_db()
        with conn:conn.execute('UPDATE feature_engine_state SET state=?',(json.dumps(old),))
        conn.close()
        with patch.object(momentum,'calculate_dmi',side_effect=AssertionError('ADX must not run')),patch.object(trend,'calculate_ema',side_effect=AssertionError('EMA must not run')),patch.object(volume_profile,'accumulate_histogram',side_effect=AssertionError('Volume Profile must not run')):
            self.finish()
        self.assertEqual(self.raw_features(),self.before)
        conn=features_store.open_db()
        try:self.assertEqual(conn.execute('SELECT last_open_time FROM feature_engine_state').fetchone()[0],self.clients[-1]['open_time'])
        finally:conn.close()

    def test_targeted_update_failure_rolls_back_columns_and_partial_checkpoint(self):
        self.config(rsiLen=11)
        conn=features_store.open_db()
        with conn:conn.execute('CREATE TRIGGER reject_target BEFORE UPDATE OF rsi ON features BEGIN SELECT RAISE(ABORT,"injected selective failure"); END')
        conn.close()
        with self.assertRaises(sqlite3.IntegrityError):processor.catch_up('ETHUSDT','1m')
        conn=features_store.open_db()
        try:
            self.assertEqual(selective.read_job(conn,'ETHUSDT','1m')['last_time'],-1)
            self.assertEqual(conn.execute('SELECT last_open_time FROM feature_engine_state').fetchone()[0],self.clients[-1]['open_time'])
        finally:conn.close()
        self.assertEqual(self.raw_features()[100]['rsi'],self.original[100]['rsi'])
        conn=features_store.open_db()
        with conn:conn.execute('DROP TRIGGER reject_target')
        conn.close();processor._ENGINES.clear();self.finish()

    def test_formula_source_change_is_detected_without_global_version_bump(self):
        original=momentum.calculate_rsi
        def new_rsi(state,value,length):
            result=original(state,value,length)
            return result*.9
        self.stack.enter_context(patch.object(momentum,'calculate_rsi',new_rsi))
        updated=components.Catalog();self.stack.enter_context(patch.object(components,'_CATALOG',updated))
        plan=updated.plan(updated.changed(self.engine.component_sources,self.engine.context.parameters,self.engine.context.parameters))
        self.assertEqual(plan.columns,{'rsi','prev_rsi','rsi_change','bull_momentum_divergence','bear_momentum_divergence'})
        self.finish()
        self.assertAlmostEqual(self.raw_features()[-1]['rsi'],self.original[-1]['rsi']*.9)
        self.assertEqual(self.raw_features()[-1]['adx'],self.original[-1]['adx'])

    def test_dependency_plan_keeps_unrelated_expensive_features_out(self):
        c=components.catalog();params=self.engine.context.parameters
        for field,value in [('rsiLen',11),('ema7Len',9),('adxLen',12),('vpBins',25)]:
            plan=c.plan(c.changed(c.source,params,{**params,field:value}))
            if field!='vpBins':self.assertFalse(any(c.by_id[u].module.endswith('.volume_profile') for u in plan.execute))
            if field=='adxLen':self.assertNotIn('rsi',plan.columns)
            if field=='vpBins':self.assertNotIn('ema50',plan.columns)


    def test_parameter_families_match_full_reference_and_preserve_other_columns(self):
        c=components.catalog();old_params=self.engine.context.parameters
        for name,value in [('ema7Len',9),('adxLen',12),('atrLen',12),('volumeLookback',15),('vpBins',12),('S/R Pivot Lookback',7),('vwapBandMultiplier1',2.5),('srPivotLen',7)]:
            with self.subTest(parameter=name):
                db.write_features(self.original)
                conn=features_store.open_db()
                with conn:
                    conn.execute('DELETE FROM feature_replay_jobs');conn.execute('DELETE FROM feature_calculation_versions')
                    conn.execute('UPDATE feature_engine_state SET state=?',(checkpoint.dump(self.engine,(0,0)),))
                conn.close();processor._ENGINES.clear()
                params={**old_params,name:value};plan=c.plan(c.changed(self.engine.component_sources,old_params,params))
                reference=Engine('ETHUSDT','1m',params);expected=[reference.step(b) for b in self.clients]
                with patch.object(components,'desired_parameters',return_value=params),patch.object(selective,'desired_parameters',return_value=params):
                    self.finish()
                    for old,new,ref in zip(self.before,self.raw_features(),expected):
                        for field in old:
                            wanted=ref.get(field) if field in plan.columns else old[field]
                            if wanted is not None and (features_store._translated_fields.get(field)=='string' or field.endswith('_type')):wanted=str(wanted)
                            self.assertEqual(new[field],wanted,(name,field))
                    extra=bar(220,114);db.write_klines([extra])
                    processor._ENGINES.clear();processor.catch_up('ETHUSDT','1m')
                    result=db.read_features('ETHUSDT','1m',extra['open_time']);ref=reference.step(extra)
                    for field,wanted in ref.items():
                        if wanted is not None and (features_store._translated_fields.get(field)=='string' or field.endswith('_type')):wanted=str(wanted)
                        self.assertEqual(result[field],wanted,(name,'next bar',field))
                # Next scenario must start with the original closed prefix.
                conn=klines_store.open_db()
                with conn:conn.execute('DELETE FROM klines WHERE open_time=?',(extra['open_time'],))
                conn.close()
                conn=features_store.open_db()
                with conn:
                    conn.execute('DELETE FROM features WHERE open_time=?',(extra['open_time'],))
                    conn.execute('UPDATE feature_engine_state SET last_open_time=?',(self.clients[-1]['open_time'],))
                conn.close()

    def test_partial_restart_masks_only_dirty_columns_and_keeps_the_main_cursor(self):
        params=self.config(rsiLen=11)
        self.assertEqual(processor._advance('ETHUSDT','1m',max_bars=10),50)
        conn=features_store.open_db()
        try:
            job=selective.read_job(conn,'ETHUSDT','1m')
            self.assertEqual(job['last_time'],49*60000)
            self.assertEqual(conn.execute('SELECT last_open_time FROM feature_engine_state').fetchone()[0],219*60000)
        finally:conn.close()
        visible=db.read_features('ETHUSDT','1m',100*60000)
        self.assertIsNone(visible['rsi']);self.assertEqual(visible['ema50'],self.original[100]['ema50'])
        self.assertEqual(features_store.decision_generation('ETHUSDT','1m'),0)
        processor._ENGINES.clear();self.finish()
        reference=Engine('ETHUSDT','1m',params)
        for client in self.clients:expected=reference.step(client)
        self.assertEqual(db.read_features('ETHUSDT','1m',219*60000)['rsi'],expected['rsi'])

    def test_adx_change_invalidates_only_dependent_decisions_and_caps_inputs(self):
        self.config(adxLen=12)
        processor._advance('ETHUSDT','1m',max_bars=10)
        self.assertEqual(features_store.decision_generation('ETHUSDT','1m'),1)
        conn=features_store.open_db()
        try:self.assertEqual(features_store.replay_through(conn,'ETHUSDT','1m'),49*60000)
        finally:conn.close()
        values=db.read_features('ETHUSDT','1m',100*60000)
        self.assertIsNone(values['adx']);self.assertEqual(values['rsi'],self.original[100]['rsi'])
        from Section_8_Decision_Engine import processor as decisions
        decisions._CACHE.clear()
        with patch.object(decisions.data_policy,'read',return_value={'epochs':{}}):
            decisions.catch_up('ETHUSDT','1m')
            self.assertEqual(decisions._load('ETHUSDT','1m')['last'],49*60000)
        with sqlite3.connect(adcn_store.DB_PATH) as conn:self.assertEqual(conn.execute('SELECT COUNT(*) FROM decisions').fetchone()[0],50)
        processor._ENGINES.clear();self.finish()

    def test_strategy_edit_does_not_schedule_any_feature_replay(self):
        from Section_8_Decision_Engine.rules import di_turning_point as rule
        with patch.object(rule,'VERSION',100),patch.object(rule,'RULE_ID','NEW_STRATEGY'),patch.object(processor,'build_feature_packet',side_effect=AssertionError('strategy must not calculate features')):
            self.assertEqual(processor.catch_up('ETHUSDT','1m'),0)
        self.assertEqual(self.raw_features(),self.before)

    def test_reverting_input_mid_replay_repairs_already_changed_rows(self):
        self.config(rsiLen=11)
        processor._advance('ETHUSDT','1m',max_bars=10)
        self.assertNotEqual(self.raw_features()[40]['rsi'],self.before[40]['rsi'])
        original=self.engine.context.parameters
        with patch.object(components,'desired_parameters',return_value=original),patch.object(selective,'desired_parameters',return_value=original):
            processor._ENGINES.clear();self.finish()
        self.assertEqual(self.raw_features(),self.before)

    def test_preview_masks_dirty_values_and_refreshes_state_at_unchanged_main_cursor(self):
        client=bar(220,114)
        before=processor.preview('ETHUSDT','1m',client)
        params=self.config(rsiLen=11)
        processor._advance('ETHUSDT','1m',max_bars=10)
        during=processor.preview('ETHUSDT','1m',client)
        self.assertIsNone(during['rsi']);self.assertEqual(during['ema50'],before['ema50'])
        processor._ENGINES.clear();self.finish()
        reference=Engine('ETHUSDT','1m',params)
        for b in self.clients:reference.step(b)
        expected=reference.step(client,is_confirmed=False,is_realtime=True)
        self.assertEqual(processor.preview('ETHUSDT','1m',client)['rsi'],expected['rsi'])

    def legacy_job(self):
        legacy=components.legacy_runtime_sources()
        signature=components.digest([components.digest(legacy),components.desired_parameters()])
        conn=features_store.open_db()
        with conn:
            conn.execute('INSERT OR REPLACE INTO feature_replay_jobs VALUES (?,?,?,?,?,?,?,?)',
                         ('ETHUSDT','1m',signature,219*60000,49*60000,json.dumps(list(legacy)),None,json.dumps(list(features_store.COLUMNS))))
        conn.close()

    def test_portable_baseline_changes_are_limited_to_reviewed_zone_owners(self):
        import ast
        baseline,_=components.baseline_sources()
        with patch.object(ast,'dump',side_effect=AssertionError('interpreter AST formatting must not determine revisions')):
            current=components.Catalog()
        changed={uid for uid in current.source if current.source[uid]!=baseline.get(uid)}
        self.assertTrue(changed)
        self.assertTrue(all(current.by_id[uid].module.endswith(('.fair_value_gaps','.support_resistance','.zone_lifecycle')) for uid in changed))
        self.assertTrue(all('fvg' in col or col=='sr_zone_events' or col.startswith(('inst_support_','inst_resistance_')) for col in current.plan(current.changed(baseline,{},{})).columns))

    def test_ast_format_only_job_is_retired_without_calculation_or_cursor_reset(self):
        self.legacy_job()
        with patch.object(selective.PartialEngine,'step',side_effect=AssertionError('no repair needed')),patch.object(processor,'build_feature_packet',side_effect=AssertionError('no new candles')):
            self.assertEqual(processor.catch_up('ETHUSDT','1m'),0)
        conn=features_store.open_db()
        try:
            self.assertIsNone(selective.read_job(conn,'ETHUSDT','1m'))
            self.assertEqual(conn.execute('SELECT last_open_time FROM feature_engine_state').fetchone()[0],219*60000)
        finally:conn.close()
        self.assertEqual(self.raw_features(),self.before)

    def test_format_recovery_does_not_wait_for_another_symbols_history(self):
        self.legacy_job()
        with patch.object(selective.PartialEngine,'step',side_effect=AssertionError('metadata recovery must not calculate')):
            processor._recover_runtime_format_job(['BTCUSDT','ETHUSDT'],['1m'])
        conn=features_store.open_db()
        try:self.assertIsNone(selective.read_job(conn,'ETHUSDT','1m'))
        finally:conn.close()
        self.assertEqual(self.raw_features(),self.before)

    def test_completed_old_python_fingerprint_adopts_without_replay(self):
        self.engine.component_sources=components.legacy_runtime_sources()
        conn=features_store.open_db()
        with conn:conn.execute('UPDATE feature_engine_state SET state=?',(checkpoint.dump(self.engine,(0,0)),))
        conn.close()
        with patch.object(selective.PartialEngine,'step',side_effect=AssertionError('no repair needed')):
            self.assertEqual(processor.catch_up('ETHUSDT','1m'),0)
        self.assertEqual(self.raw_features(),self.before)

    def test_retiring_ast_format_job_retains_real_input_repair(self):
        params=self.config(rsiLen=11);self.legacy_job()
        with patch.object(momentum,'calculate_dmi',side_effect=AssertionError('ADX must not run')),patch.object(trend,'calculate_ema',side_effect=AssertionError('EMA must not run')):
            self.finish()
        reference=Engine('ETHUSDT','1m',params)
        for client in self.clients:expected=reference.step(client)
        self.assertEqual(self.raw_features()[-1]['rsi'],expected['rsi'])

    def test_fvg_source_repair_preserves_every_unrelated_column_and_future_state(self):
        self.engine.component_sources=components.baseline_sources()[0]
        self.engine.context.persistent['fvgFailureDirection']=1
        self.engine.context.persistent['fvgFailureStrength']=999
        conn=features_store.open_db()
        with conn:
            conn.execute('UPDATE feature_engine_state SET state=?',(checkpoint.dump(self.engine,(0,0)),))
            conn.execute('UPDATE features SET nearest_bull_fvg_reaction_count=-999,nearest_bear_fvg_reaction_score_normalized=-999')
        conn.close()
        with patch.object(momentum,'calculate_dmi',side_effect=AssertionError('ADX must not run')),patch.object(trend,'calculate_ema',side_effect=AssertionError('EMA must not run')),patch.object(volume_profile,'accumulate_histogram',side_effect=AssertionError('VP must not run')):
            self.finish()
        self.assertEqual(self.raw_features(),self.before)
        reference=Engine('ETHUSDT','1m')
        for b in self.clients:reference.step(b)
        extra=bar(220,114);db.write_klines([extra]);processor._ENGINES.clear();processor.catch_up('ETHUSDT','1m')
        result=db.read_features('ETHUSDT','1m',extra['open_time']);expected=reference.step(extra)
        for key,value in expected.items():
            if value is not None and (features_store._translated_fields.get(key)=='string' or key.endswith('_type')):value=str(value)
            self.assertEqual(result[key],value,key)

    def test_zone_lifecycle_backfill_preserves_other_columns_and_checkpoint(self):
        c=components.catalog()
        self.engine.component_sources={k:v for k,v in c.source.items() if '.zone_lifecycle:' not in k}
        for key in list(self.engine.context.persistent):
            if key.startswith('srDisplay'):del self.engine.context.persistent[key]
        conn=features_store.open_db()
        with conn:
            conn.execute('UPDATE features SET sr_zone_events=NULL,inst_support_zone_low=NULL,inst_support_zone_high=NULL,inst_resistance_zone_low=NULL,inst_resistance_zone_high=NULL')
            conn.execute('UPDATE feature_engine_state SET state=?',(checkpoint.dump(self.engine,(0,0)),))
        conn.close()
        with patch.object(momentum,'calculate_dmi',side_effect=AssertionError('DMI must not run')),patch.object(trend,'calculate_ema',side_effect=AssertionError('EMA must not run')),patch.object(volume_profile,'accumulate_histogram',side_effect=AssertionError('VP must not run')):
            self.finish()
        self.assertEqual(self.raw_features(),self.before)
        conn=features_store.open_db()
        try:self.assertEqual(conn.execute('SELECT last_open_time FROM feature_engine_state').fetchone()[0],self.clients[-1]['open_time'])
        finally:conn.close()
        self.stack.enter_context(patch.object(processor.data_policy,'read',return_value={'epochs':{}}))
        snapshot=db.read_sr_snapshot('ETHUSDT','1m')
        self.assertEqual(snapshot['through'],self.clients[-1]['open_time']//1000)
        self.assertEqual(snapshot['zones'],processor._load('ETHUSDT','1m',(0,0)).context.persistent['srDisplayPrevious'])
        reference=Engine('ETHUSDT','1m')
        for client in self.clients:reference.step(client)
        next_bar=bar(220,114);expected=reference.step(next_bar)
        db.write_klines([next_bar]);processor._ENGINES.clear();processor.catch_up('ETHUSDT','1m')
        actual=db.read_features('ETHUSDT','1m',next_bar['open_time'])
        self.assertEqual(actual['sr_zone_events'],expected['sr_zone_events'])
        self.assertEqual(actual['inst_support_zone_low'],expected['inst_support_zone_low'])
