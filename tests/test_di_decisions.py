"""User-specified two-candle DI recovery rule and closed-memory integration."""
from contextlib import ExitStack
import json
from pathlib import Path
import sqlite3
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from Section_8_Decision_Engine.rules import di_turning_point as rule
from Section_8_Decision_Engine import processor
from Section_1_Global_Core import data_policy
from Section_1_Global_Core.memory_storage.Storage import db,klines_store,features_store,adcn_store
from Section_1_Global_Core.memory_storage.market_data import download_binance_history as downloader


def di(plus,minus,spread=None,*,adx=22,close=101):
    return dict(di_plus=plus,di_minus=minus,di_spread=abs(plus-minus) if spread is None else spread,adx=adx,close=close)

SETUP=[di(10,30,adx=20,close=99),di(11,35,adx=21,close=100)]


class DiRuleTests(unittest.TestCase):
    def test_buy_continuation_branch(self):
        self.assertEqual(rule.evaluate(SETUP,di(15,27))['signal_type'],'BUY')

    def test_buy_cross_branch(self):
        prior=[di(30,10,adx=20,close=99),di(40,15,adx=21,close=100)]
        self.assertEqual(rule.evaluate(prior,di(8,12))['signal_type'],'BUY')

    def test_sell_both_branches(self):
        prior=[di(30,10,adx=20,close=103),di(35,11,adx=21,close=102)]
        self.assertEqual(rule.evaluate(prior,di(27,15))['signal_type'],'SELL')
        prior=[di(10,30,adx=20,close=103),di(15,40,adx=21,close=102)]
        self.assertEqual(rule.evaluate(prior,di(12,8))['signal_type'],'SELL')

    def test_every_outer_comparison_is_strict(self):
        from copy import deepcopy
        for target,key,value in ((0,'di_minus',35),(1,'di_minus',27),(0,'di_spread',24),(1,'di_spread',12),
                                 (2,'close',100),(2,'adx',21)):
            rows=deepcopy([*SETUP,di(15,27)]);rows[target][key]=value
            self.assertIsNone(rule.evaluate(rows[:2],rows[2])['signal_type'],(target,key))

    def test_invalid_values_are_warmup(self):
        for key in rule.FIELDS:
            for value in (None,float('nan'),float('inf'),True,-1):
                current=di(15,27);current[key]=value
                self.assertEqual(rule.evaluate(SETUP,current)['decision_state'],'WARMUP')
        self.assertEqual(rule.evaluate(SETUP[:1],di(15,27))['decision_state'],'WARMUP')

    def test_no_old_spread_cross_or_positive_rise_requirement(self):
        # Faithful Pine continuation: +DI can stay below spread and decline.
        self.assertEqual(rule.evaluate(SETUP,di(9,28))['signal_type'],'BUY')

    def test_matches_independent_pine_translation_on_random_windows(self):
        import random
        rng=random.Random(817)
        for _ in range(10000):
            a,b,c=[di(rng.randrange(1,50),rng.randrange(1,50),adx=rng.randrange(1,50),close=rng.randrange(90,110)) for _ in range(3)]
            out=None
            if a['di_minus']<b['di_minus']>c['di_minus'] and a['di_spread']<b['di_spread']>c['di_spread'] and c['close']>b['close'] and b['adx']<c['adx']:
                if a['di_minus']<a['di_plus'] and b['di_minus']<b['di_plus'] and c['di_minus']>c['di_plus']:out='BUY'
                elif b['di_spread']>b['di_plus'] and a['di_minus']>a['di_plus'] and b['di_minus']>b['di_plus'] and c['di_minus']>c['di_plus']:out='BUY'
            if a['di_plus']<b['di_plus']>c['di_plus'] and a['di_spread']<b['di_spread']>c['di_spread'] and c['close']<b['close'] and b['adx']<c['adx']:
                if a['di_plus']<a['di_minus'] and b['di_plus']<b['di_minus'] and c['di_plus']>c['di_minus']:out='SELL'
                elif b['di_spread']>b['di_minus'] and a['di_plus']>a['di_minus'] and b['di_plus']>b['di_minus'] and c['di_plus']>c['di_minus']:out='SELL'
            self.assertEqual(rule.evaluate([a,b],c)['signal_type'],out)


class DiMemoryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.stack=ExitStack();self.addCleanup(self.stack.close)
        for module,attr,value in ((klines_store,'DB_PATH',self.root/'klines.db'),(features_store,'DB_PATH',self.root/'features.db'),(adcn_store,'DB_PATH',self.root/'ADCN.db'),(downloader,'DB_PATH',self.root/'klines.db'),(data_policy,'LOCK_FILE',self.root/'policy.lock'),(data_policy,'POLICY_FILE',self.root/'policy.json')):
            self.stack.enter_context(patch.object(module,attr,value))
        self.stack.enter_context(patch.object(data_policy,'enabled',return_value=True))
        processor._CACHE.clear();processor._cursor=0
        downloader.open_db().close()

    def seed(self,values=(*SETUP,di(15,27)),symbol='ETHUSDT',interval='1m',times=None,cap=None):
        times=times or [i*60000 for i in range(len(values))]
        db.write_klines([dict(symbol=symbol,interval=interval,open_time=t,close_time=t+59999,open=100.,high=102.,low=98.,close=value.get("close",101.),volume=5.) for t,value in zip(times,values)])
        db.write_features([dict(symbol=symbol,interval=interval,open_time=t,formula_version=3,**value) for t,value in zip(times,values)])
        conn=features_store.open_db()
        conn.execute('INSERT OR REPLACE INTO feature_engine_state VALUES (?,?,?,?)',(symbol,interval,times[-1] if cap is None else cap,'{}'));conn.commit();conn.close()
        return times

    def test_background_scan_persists_old_chart_signal_without_an_existing_adcn_row(self):
        from Section_1_Global_Core.global_packet import recover_decision_evidence
        self.seed([{**v,'atr':1,'protected_high':110,'protected_low':90} for v in (*SETUP,di(15,27))])
        adcn_store.open_db().close()
        self.assertEqual(recover_decision_evidence('ETHUSDT','1m'),1)
        with sqlite3.connect(adcn_store.DB_PATH) as conn:
            self.assertEqual(conn.execute('SELECT signal_type,signal_price,provenance FROM decision_evidence').fetchone(),
                ('BUY',101,'historical reconstruction from stored close-time inputs'))
            self.assertEqual(conn.execute('SELECT finished FROM decision_evidence_scan').fetchone(),(1,))
        self.assertEqual(recover_decision_evidence('ETHUSDT','1m'),0)
        self.assertEqual(db.read_adcn('ETHUSDT','1m',120000)['signal_type'],'BUY')

    def test_worker_saves_all_six_bands_and_reload_uses_immutable_adcn_snapshot(self):
        values=[di(30,10,adx=20,close=100),di(35,11,adx=21,close=101),di(27,15,adx=22,close=100)]
        levels=dict(atr=1,resistance_zone_low=101,resistance_zone_high=101.2,
            inst_resistance_zone_low=102,inst_resistance_zone_high=102.2,nearest_bear_fvg_low=103,nearest_bear_fvg_high=103.2,
            support_zone_low=98.8,support_zone_high=99,inst_support_zone_low=97.8,inst_support_zone_high=98,
            nearest_bull_fvg_low=96.8,nearest_bull_fvg_high=97)
        self.seed([{**v,**levels} for v in values])
        processor.maintenance(['ETHUSDT'],['1m'],time_budget=2)
        with sqlite3.connect(adcn_store.DB_PATH) as conn:
            saved=conn.execute('SELECT signal_price,resistance_1,resistance_2,resistance_3,support_1,support_2,support_3 FROM decision_evidence').fetchone()
        self.assertIsNotNone(saved);self.assertEqual(saved[0],100);self.assertTrue(all(saved[1:]))
        page=db.read_state_page('ETHUSDT','1m',1,before=120001)
        expected=page['bars'][-1]['signal_context']['area_map']
        db.write_features([dict(symbol='ETHUSDT',interval='1m',open_time=120000,formula_version=3,**values[-1],atr=10,resistance_zone_low=120,resistance_zone_high=121)])
        processor._CACHE.clear()
        with patch('Section_1_Global_Core.analysis.opportunity',side_effect=AssertionError('saved geometry must be reused')):
            reloaded=db.read_state_page('ETHUSDT','1m',1,before=120001)['bars'][-1]
        self.assertEqual(reloaded['signal_context']['area_map'],expected)
        self.assertEqual(reloaded['signal_context']['storage']['status'],'persisted')
        self.assertEqual(reloaded['momentum']['signal_price'],100)
        self.assertEqual(reloaded['client']['high'],102)

    def test_latest_window_seeds_without_a_historical_replay_and_reaches_gateway(self):
        self.seed()
        self.assertEqual(processor.maintenance(['ETHUSDT'],['1m'],time_budget=2),1)
        row=db.read_adcn('ETHUSDT','1m',120000)
        self.assertEqual(row['signal_type'],'BUY');self.assertIsNone(row['final_score'])
        self.assertEqual(row['trigger'],rule.RULE_ID)
        page=db.read_state_page('ETHUSDT','1m')
        self.assertEqual(page['bars'][-1]['adcn']['signal_type'],'BUY')
        with sqlite3.connect(adcn_store.DB_PATH) as conn:self.assertEqual(conn.execute('SELECT COUNT(*) FROM decisions').fetchone()[0],1)
        processor._CACHE.clear()
        self.assertEqual(processor.catch_up('ETHUSDT','1m'),0)
        self.seed([*SETUP,di(15,27),di(16,26)])
        self.assertTrue(processor.process_bar(SimpleNamespace(symbol='ETHUSDT',timeframe='1m',open_time=180000)))
        self.assertIsNone(db.read_adcn('ETHUSDT','1m',180000)['signal_type'])

    def test_two_candle_poll_carries_the_older_decision_point(self):
        values=[*SETUP,di(15,27),*[di(16,26,close=101) for _ in range(12)]]
        times=self.seed(values)
        db.write_features([dict(symbol='ETHUSDT',interval='1m',open_time=t,formula_version=3,**value,atr=2,ema50=99,ema200=98,vwap=100,
            support_zone_low=95,support_zone_high=97,resistance_zone_low=110,resistance_zone_high=112) for t,value in zip(times,values)])
        initial=db.read_state_page('ETHUSDT','1m')
        reference=initial['bars'][-1]['signal_context']
        self.assertIsNotNone(reference);self.assertEqual(reference['open_time'],120000)
        refreshed=db.read_state_page('ETHUSDT','1m',2,analysis_reference=120000)
        self.assertEqual(len(refreshed['bars']),2)
        context=refreshed['bars'][-1]['signal_context']
        self.assertEqual(context['entry'],reference['entry']);self.assertEqual(context['open_time'],120000)
        self.assertEqual(context['plan'],reference['plan'])

    def test_historical_study_reads_canonical_prefix_without_writing_decisions(self):
        from evaluate_strategy import evaluate
        self.seed(cap=60000)
        report=evaluate(['ETHUSDT'],['1m'],(1,))
        self.assertEqual(report['pairs'][0]['bars'],2)
        self.assertEqual(report['pairs'][0]['buy_signals'],0)
        self.seed()
        report=evaluate(['ETHUSDT'],['1m'],(1,))
        self.assertEqual(report['pairs'][0]['bars'],3)
        self.assertEqual(report['pairs'][0]['buy_signals'],1)
        self.assertFalse(adcn_store.DB_PATH.exists())

    def test_chart_momentum_projects_history_without_adcn_and_with_page_predecessors(self):
        self.seed()
        page=db.read_state_page('ETHUSDT','1m',1)
        self.assertEqual(len(page['bars']),1)
        bar=page['bars'][0]
        self.assertEqual(bar['momentum']['signal_type'],'BUY')
        self.assertIsNone(bar['adcn'])
        self.assertFalse(adcn_store.DB_PATH.exists())
        # Strict page boundary and a raw gap must not borrow unrelated history.
        self.seed(times=[0,120000,180000],symbol='BTCUSDT')
        page=db.read_state_page('BTCUSDT','1m',1)
        self.assertEqual(page['bars'][0]['momentum']['decision_state'],'WARMUP')

    def test_alternation_persists_across_restart_and_opposite_unlocks_next_buy(self):
        buy=[*SETUP,di(15,27)]
        sell=[di(30,10,adx=20,close=103),di(35,11,adx=21,close=102),di(27,15)]
        self.seed(buy);processor.catch_up('ETHUSDT','1m')
        processor._CACHE.clear()
        self.seed(buy+buy+sell+buy)
        processor.catch_up('ETHUSDT','1m')
        with sqlite3.connect(adcn_store.DB_PATH) as conn:
            signals=[row[0] for row in conn.execute("SELECT signal_type FROM decisions WHERE signal_type IS NOT NULL ORDER BY open_time")]
        self.assertEqual(signals,['BUY','SELL','BUY'])
        self.assertEqual(db.read_adcn('ETHUSDT','1m',300000)['decision_state'],'SUPPRESSED')
        processor._CACHE.clear()
        self.assertEqual(processor._load('ETHUSDT','1m')['last_signal'],'BUY')

    def test_chart_anchor_search_crosses_backward_page_boundary(self):
        self.seed([*SETUP,di(15,27),*([di(15,27)]*520),*SETUP,di(15,27)])
        page=db.read_state_page('ETHUSDT','1m',1)
        self.assertEqual(page['bars'][0]['momentum']['decision_state'],'SUPPRESSED')
        self.assertEqual(db.read_previous_decision_candidate('ETHUSDT','1m',page['bars'][0]['open_time']),'BUY')
        processor.catch_up('ETHUSDT','1m')
        self.assertIsNone(db.read_adcn('ETHUSDT','1m',page['bars'][0]['open_time'])['signal_type'])

    def test_signal_sequence_is_independent_of_chart_page_size(self):
        buy=[*SETUP,di(15,27)]
        sell=[di(30,10,adx=20,close=103),di(35,11,adx=21,close=102),di(27,15)]
        self.seed(buy+buy+sell+sell+buy)
        for size in (1,2,4,7,1000):
            before=None;received=[]
            while True:
                page=db.read_state_page('ETHUSDT','1m',size,before=before)
                received.extend(page['bars'])
                before=page['next_before']
                if before is None:break
            received.sort(key=lambda bar:bar['open_time'])
            self.assertEqual([bar['momentum']['signal_type'] for bar in received if bar['momentum']['signal_type']],['BUY','SELL','BUY'],size)

    def test_signal_free_chart_does_not_search_older_history(self):
        self.seed([di(10,30),di(11,30),di(12,29)])
        with patch.object(db,'read_previous_decision_candidate',side_effect=AssertionError('unnecessary history search')):
            page=db.read_state_page('ETHUSDT','1m',3)
        self.assertTrue(all(not b['momentum']['signal_type'] for b in page['bars']))

    def test_v2_migration_keeps_checkpoint_and_seeds_last_direction(self):
        self.seed()
        conn=adcn_store.open_db()
        previous=[processor._record(item) for item in db.read_decision_seed('ETHUSDT','1m')][-2:]
        old={'version':2,'epoch':[0,0],'last':120000,'previous':previous,'seeded':True}
        adcn_store.commit_rule_rows(conn,'ETHUSDT','1m',[],120000,json.dumps(old));conn.close()
        processor._CACHE.clear()
        loaded=processor._load('ETHUSDT','1m')
        self.assertEqual(loaded['last'],120000);self.assertEqual(loaded['last_signal'],'BUY')
        self.seed([*SETUP,di(15,27),*SETUP,di(15,27)])
        processor.catch_up('ETHUSDT','1m')
        self.assertIsNone(db.read_adcn('ETHUSDT','1m',300000)['signal_type'])

    def test_sell_uses_same_closed_memory_pipeline(self):
        self.seed([di(30,10,adx=20,close=103),di(35,11,adx=21,close=102),di(27,15)])
        processor.catch_up('ETHUSDT','1m')
        self.assertEqual(db.read_adcn('ETHUSDT','1m',120000)['signal_type'],'SELL')

    def test_old_rule_checkpoint_is_reseeded_with_new_version(self):
        self.seed()
        conn=adcn_store.open_db()
        old={'version':1,'epoch':[0,0],'last':999999,'previous':[],'seeded':True}
        adcn_store.commit_rule_rows(conn,'ETHUSDT','1m',[],999999,json.dumps(old));conn.close()
        processor._CACHE.clear()
        self.assertEqual(processor.catch_up('ETHUSDT','1m'),1)
        self.assertEqual(db.read_adcn('ETHUSDT','1m',120000)['signal_type'],'BUY')
        self.assertEqual(processor._load('ETHUSDT','1m')['version'],3)

    def test_waits_for_feature_checkpoint_and_forming_candle_close(self):
        self.seed(cap=60000)
        processor.catch_up('ETHUSDT','1m')
        self.assertIsNone(db.read_adcn('ETHUSDT','1m',120000))
        self.seed()
        with patch.object(processor.time,'time',return_value=179.999):
            self.assertFalse(processor.process_bar(SimpleNamespace(symbol='ETHUSDT',timeframe='1m',open_time=120000)))
        self.assertIsNone(db.read_adcn('ETHUSDT','1m',120000))
        self.assertTrue(processor.process_bar(SimpleNamespace(symbol='ETHUSDT',timeframe='1m',open_time=120000)))
        self.assertEqual(db.read_adcn('ETHUSDT','1m',120000)['signal_type'],'BUY')

    def test_seed_gap_and_later_gap_require_two_new_setup_bars(self):
        self.seed(times=[0,120000,180000])
        processor.catch_up('ETHUSDT','1m')
        self.assertEqual(db.read_adcn('ETHUSDT','1m',180000)['decision_state'],'WARMUP')
        self.seed([*SETUP,di(15,27)],symbol='BTCUSDT')
        processor.catch_up('BTCUSDT','1m')
        self.seed([*SETUP,di(15,27)],symbol='BTCUSDT',times=[300000,360000,420000])
        processor.catch_up('BTCUSDT','1m')
        self.assertEqual(db.read_adcn('BTCUSDT','1m',300000)['decision_state'],'WARMUP')
        self.assertIsNone(db.read_adcn('BTCUSDT','1m',420000)['signal_type'])
        self.assertEqual(db.read_adcn('BTCUSDT','1m',420000)['decision_state'],'SUPPRESSED')

    def test_failed_commit_does_not_advance_checkpoint_or_cached_history(self):
        self.seed()
        conn=adcn_store.open_db()
        conn.execute('CREATE TRIGGER reject_di BEFORE INSERT ON decisions BEGIN SELECT RAISE(ABORT,"injected decision failure"); END');conn.commit();conn.close()
        with self.assertRaises(sqlite3.IntegrityError):processor.catch_up('ETHUSDT','1m')
        conn=adcn_store.open_db()
        self.assertIsNone(adcn_store.read_rule_state(conn,'ETHUSDT','1m'))
        conn.execute('DROP TRIGGER reject_di');conn.commit();conn.close()
        self.assertEqual(processor.catch_up('ETHUSDT','1m'),1)
        self.assertEqual(db.read_adcn('ETHUSDT','1m',120000)['signal_type'],'BUY')

    def test_disabled_pairs_wait_and_policy_epoch_change_prevents_commit(self):
        self.seed()
        with patch.object(data_policy,'enabled',return_value=False):self.assertEqual(processor.catch_up('ETHUSDT','1m'),0)
        original=db.read_decision_inputs
        def changed(*args):
            result=original(*args)
            self.root.joinpath('policy.json').write_text(json.dumps({'epochs':{'symbol:ETHUSDT':1},'paused_coins':[],'timeframes':{}}))
            return result
        with patch.object(db,'read_decision_inputs',side_effect=changed):self.assertEqual(processor.catch_up('ETHUSDT','1m'),0)
        self.assertIsNone(db.read_adcn('ETHUSDT','1m',120000))
        self.assertEqual(processor.catch_up('ETHUSDT','1m'),1)

    def test_rule_updates_signal_without_erasing_other_engine_columns(self):
        self.seed()
        db.write_adcn([dict(symbol='ETHUSDT',interval='1m',open_time=120000,scalp_score=42,signal_type='SELL',final_score=88)])
        processor.catch_up('ETHUSDT','1m')
        row=db.read_adcn('ETHUSDT','1m',120000)
        self.assertEqual(row['signal_type'],'BUY');self.assertEqual(row['scalp_score'],42)
        self.assertIsNone(row['final_score'])

    def test_checkpoint_failure_rolls_back_decision_rows_too(self):
        self.seed()
        conn=adcn_store.open_db()
        conn.execute('CREATE TRIGGER reject_state BEFORE INSERT ON decision_rule_state BEGIN SELECT RAISE(ABORT,"injected checkpoint failure"); END');conn.commit();conn.close()
        with self.assertRaises(sqlite3.IntegrityError):processor.catch_up('ETHUSDT','1m')
        with sqlite3.connect(adcn_store.DB_PATH) as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM decisions').fetchone()[0],0)
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM decision_rule_state').fetchone()[0],0)

    def test_symbol_and_timeframe_history_is_isolated(self):
        self.seed();self.seed([di(10,30),di(11,30),di(12,29)],symbol='BTCUSDT')
        self.seed([di(10,30),di(11,30),di(12,29)],interval='5m')
        processor.maintenance(['ETHUSDT','BTCUSDT'],['1m','5m'],time_budget=3)
        self.assertEqual(db.read_adcn('ETHUSDT','1m',120000)['signal_type'],'BUY')
        self.assertIsNone(db.read_adcn('BTCUSDT','1m',120000)['signal_type'])
        self.assertIsNone(db.read_adcn('ETHUSDT','5m',120000)['signal_type'])
