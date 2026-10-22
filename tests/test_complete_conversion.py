"""Independent vectors, state lifecycles, restart replay and permanent storage."""
import copy
from contextlib import ExitStack,nullcontext
import json
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from Section_4_Features.execution.engine import Engine
from Section_4_Features.execution import checkpoint
from Section_4_Features.execution.context import MANIFEST
from Section_4_Features.execution.contract import snake
from Section_4_Features import processor
from Section_1_Global_Core.memory_storage.Storage import features_store,klines_store,db


def bar(i,close=100,symbol='ETHUSDT',interval='1m',step=60000,**values):
    result=dict(symbol=symbol,interval=interval,open_time=i*step,close_time=(i+1)*step-1,open=close-.5,high=close+2,low=close-2,close=close,volume=10.)
    result.update(values);return result


class CompleteConversionTests(unittest.TestCase):
    def test_feature_files_cover_every_executable_reference_statement(self):
        from Section_4_Features.conversion.compile_reference import statements,SOURCE
        import importlib
        lines=SOURCE.read_text().splitlines()
        covered=set()
        for entry in MANIFEST['manifest']:
            covered.update(range(entry['start'],entry['end']+1));covered.update(entry.get('extra_lines',[]))
        expected={line for _,_,line in statements(lines,793,5112)}|{line for _,_,line in statements(lines,5741,5893)}
        self.assertEqual(expected-covered,set())
        self.assertEqual(len(MANIFEST['modules']),28)
        for name in MANIFEST['modules']:
            module=importlib.import_module(name if '.' in name else 'Section_4_Features.features.'+name)
            self.assertTrue(callable(module.update))

    def test_main_feature_consolidation_preserves_all_packets(self):
        # Captured from the pre-consolidation engine (4267c45), before moving code.
        import hashlib
        digest=hashlib.sha256();engine=Engine('ETHUSDT','15m')
        for i in range(700):
            c=100+math.sin(i/9)*14+i*.01
            client=dict(symbol='ETHUSDT',interval='15m',open_time=1700000000000+i*900000,
                        close_time=1700000000000+(i+1)*900000-1,open=c-.5,high=c+2,
                        low=c-3,close=c,volume=10+i%17)
            packet=engine.step(client)
            # Newly exported legacy candle field was absent from the old packet.
            packet.pop('prev_candle_range')
            for side in ('support','resistance','inst_support','inst_resistance'):
                for edge in ('low','high'):packet.pop(f'{side}_zone_{edge}')
            digest.update(json.dumps(packet,sort_keys=True,separators=(',',':')).encode())
        self.assertEqual(digest.hexdigest(),'9a8ab1dafc558a35c3a01123eeac30022599e0fc885e569d8bf18b5336c210c7')
        from Section_4_Features.features.registry import load
        owners={row['name']:row for row in load()}
        for name in ('liquidity','support_resistance','sessions','order_blocks','trend','momentum','candle','market_structure'):
            self.assertIn(name,owners)
        self.assertEqual(len(owners),22)
        from Section_11_UI_UX.server.hud import FIELDS
        for field in ('di_dominance','rsi','adx','ema50','vwap'):
            self.assertIn('features.'+field,FIELDS)
        for step in MANIFEST['steps']:
            import importlib
            name=step['module']
            module=importlib.import_module(name if '.' in name else 'Section_4_Features.features.'+name)
            self.assertTrue(callable(getattr(module,step['function'])))

    def test_files_follow_numbered_source_sections(self):
        from Section_4_Features.conversion.compile_reference import section_spans,SOURCE
        entries={row['section']:row for row in MANIFEST['manifest'] if isinstance(row['section'],str)}
        for section,name,start,end,title in section_spans(SOURCE.read_text().splitlines()):
            self.assertEqual((entries[section]['feature'],entries[section]['start'],entries[section]['end']),(name,start,end))
        candle=entries['4.2.12']['outputs']
        for field in ('bullEngulfing','bearRejection','bullBreakRetest','pivotHigh','prevPivotLow'):
            self.assertIn(field,candle)
        structure=entries['4.2.10']['outputs']
        self.assertIn('latestConfirmedPivotHigh',structure)
        from pathlib import Path
        folder=Path(__file__).parents[1]/'Section_4_Features'
        self.assertFalse((folder/'individual').exists())
        self.assertEqual({p.stem for p in (folder/'features').glob('*.py')}-{'__init__','registry'},set(entries[row]['feature'] for row in entries))

    def test_all_contract_fields_and_hand_calculated_wilder_seed(self):
        engine=Engine('ETHUSDT','1m',{'rsiLen':3,'atrLen':2,'adxLen':2})
        results=[engine.step(bar(i,c)) for i,c in enumerate([10.,11.,10.,12.,11.])]
        self.assertIsNone(results[2]['rsi']);self.assertAlmostEqual(results[3]['rsi'],75)
        self.assertAlmostEqual(results[4]['rsi'],100*6/11)
        self.assertEqual(results[1]['atr'],4)
        self.assertEqual({snake(name) for name,_ in MANIFEST['contract']}-{*results[-1]},set())
        self.assertEqual(len(MANIFEST['contract']),537)

    def test_full_history_ema_and_checkpoint_equivalence(self):
        engine=Engine('ETHUSDT','1m');restart=Engine('ETHUSDT','1m');expected=None
        for i in range(650):
            close=100+math.sin(i/11)*12+i*.01;client=bar(i,close)
            expected=close if expected is None else close*2/301+expected*299/301
            full=engine.step(client);resumed=restart.step(client)
            if i%79==0:restart=checkpoint.restore('ETHUSDT','1m',checkpoint.dump(restart,(2,3)),(2,3))
        self.assertAlmostEqual(full['ema300'],expected,delta=1e-10)
        self.assertEqual(full,resumed)
        self.assertIsNone(checkpoint.restore('ETHUSDT','1m',checkpoint.dump(engine,(2,3)),(2,4)))
        other=Engine('BTCUSDT','1m');other.step(bar(0,500,symbol='BTCUSDT'))
        self.assertNotEqual(other.context.last_time,engine.context.last_time)
        self.assertIsNot(other.context.persistent['supportLowArray'],engine.context.persistent['supportLowArray'])

    def test_fvg_creation_and_failure_memory(self):
        engine=Engine('ETHUSDT','1m',{'atrLen':1,'vpLookback':3})
        for i,(low,high,close) in enumerate([(9.,10.,9.5),(11.,13.,12.),(16.,17.,16.5)]):
            result=engine.step(bar(i,close,low=low,high=high,open=close))
        self.assertTrue(engine.context.persistent['fvgBullLow'])
        self.assertEqual(engine.context.persistent['fvgBullLow'][0],10)
        engine.step(bar(3,5,low=4,high=11,open=8))
        self.assertEqual(engine.context.persistent['fvgBullLow'],[])
        self.assertEqual(engine.context.persistent['fvgFailureDirection'],1)

    def test_institutional_qualification_references_existing_dynamic_zone(self):
        engine=Engine('ETHUSDT','4h',{'atrLen':2,'S/R Pivot Lookback':1,'S/R Reaction ATR':0})
        for i in range(45):
            engine.step(bar(i,100+math.sin(i/2)*5,interval='4h',step=14400000))
        memory=engine.context.persistent
        self.assertTrue(memory['supportZoneIDArray'])
        for i in range(len(memory['supportTouchArray'])):memory['supportTouchArray'][i]=20
        close=max(memory['supportHighArray'])+10
        engine.step(bar(45,close,interval='4h',step=14400000))
        self.assertTrue(memory['instSupportZoneIDArray'])
        self.assertTrue(set(memory['instSupportZoneIDArray']).issubset(memory['supportZoneIDArray']))

    def test_support_zone_edges_export_the_selected_zone_without_approximation(self):
        engine=Engine('ETHUSDT','4h',{'atrLen':2,'S/R Pivot Lookback':1,'S/R Reaction ATR':0})
        found=0
        for i in range(65):
            packet=engine.step(bar(i,100+math.sin(i/2)*5,interval='4h',step=14400000))
            for side,prefix in [('support','support'),('resistance','resistance')]:
                identity=packet[f'nearest_{side}_zone_id']
                if identity is None:continue
                index=engine.context.persistent[prefix+'ZoneIDArray'].index(identity)
                self.assertEqual(packet[f'{side}_zone_low'],engine.context.persistent[prefix+'LowArray'][index])
                self.assertEqual(packet[f'{side}_zone_high'],engine.context.persistent[prefix+'HighArray'][index])
                found+=1
        self.assertGreater(found,0)

    def test_daily_security_historical_timing_and_explicit_daily_inputs(self):
        engine=Engine('ETHUSDT','1h',{'vpLookback':3})
        for i in range(49):
            result=engine.step(bar(i,100+i,interval='1h',step=3600000))
        # At day 3's first historical hour, lookahead_off still exposes the
        # previous completed daily expression h[1], i.e. day 1's high.
        self.assertEqual(result['previous_day_high'],125)
        weekly=Engine('ETHUSDT','1w')
        result=weekly.step(bar(0,200,interval='1w',step=604800000),daily_bars=[dict(open=80,high=110,low=70),dict(open=90,high=120,low=85)])
        self.assertEqual(result['previous_day_high'],110);self.assertEqual(result['day_open'],90)

    def test_live_fork_does_not_advance_closed_state(self):
        engine=Engine('ETHUSDT','1m')
        for i in range(25):engine.step(bar(i,100+i%5))
        before=checkpoint.dump(engine,(0,0));fork=copy.deepcopy(engine)
        live=fork.step(bar(25,110),is_confirmed=False,is_realtime=True)
        self.assertNotEqual(live['ema50'],engine.context.values['ema50'])
        self.assertEqual(checkpoint.dump(engine,(0,0)),before)

    def test_converted_profile_expansion_crosses_empty_bins_without_stalling(self):
        engine=Engine('ETHUSDT','1m',{'vpLookback':2,'vpBins':4,'vpValueAreaPct':70,'atrLen':1})
        engine.step(bar(0,.05,open=.01,high=.1,low=0,volume=60))
        result=engine.step(bar(1,3.05,open=3.01,high=3.1,low=3,volume=40))
        self.assertEqual(result['vp_val'],0)
        self.assertAlmostEqual(result['vp_vah'],3.1)

    def test_all_six_regime_outputs_and_pair_memory(self):
        engine=Engine('ETHUSDT','1m')
        for i in range(80):result=engine.step(bar(i,100+i*.5))
        self.assertEqual(result['control_state'],'CONTROL_BULL')
        self.assertEqual(result['energy_state'],'ENERGY_NORMAL')
        self.assertEqual(result['regime_state'],'REGIME_BULL_TREND')
        self.assertEqual(result['fatigue_state'],'FATIGUE_NONE')
        self.assertEqual(result['trend_state'],'MATURE')
        self.assertEqual(result['transition_state'],'NONE')

    def test_export_comparison_detects_an_independent_expected_value_mismatch(self):
        from Section_4_Features.conversion.validate_export import compare,timestamp
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'expected.csv'
            path.write_text('time,open,high,low,close,volume,ema7\n0,100,101,99,100,10,100\n60,108,109,107,108,10,102\n')
            self.assertTrue(compare(path,'ETHUSDT','1m',['ema7'])['matches'])
            path.write_text(path.read_text().replace(',102\n',',103\n'))
            result=compare(path,'ETHUSDT','1m',['ema7'])
            self.assertFalse(result['matches']);self.assertEqual(result['mismatch_count'],1)
            self.assertEqual(result['first_mismatches'][0]['actual'],102)
        self.assertEqual(timestamp('1970-01-01T05:00:00+05:00'),0)


class ReplayStorageTests(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory();self.addCleanup(self.directory.cleanup)
        self.stack=ExitStack();self.addCleanup(self.stack.close)
        for store,name in ((klines_store,'klines'),(features_store,'features')):
            self.stack.enter_context(patch.object(store,'DB_PATH',Path(self.directory.name)/(name+'.db')))
        self.stack.enter_context(patch.object(processor,'_epoch',return_value=(0,0)))
        self.stack.enter_context(patch.object(processor.data_policy,'enabled',return_value=True))
        self.stack.enter_context(patch.object(processor.data_policy,'locked',side_effect=nullcontext))
        from Section_1_Global_Core.memory_storage.market_data import download_binance_history as downloader
        self.stack.enter_context(patch.object(downloader,'DB_PATH',klines_store.DB_PATH))
        downloader.open_db().close()
        processor._ENGINES.clear();processor._PREVIEWS.clear()

    def test_bounded_replay_and_checkpoint_resume_reach_gateway(self):
        db.write_klines([bar(i,100+i%9) for i in range(205)])
        self.assertEqual(processor.catch_up('ETHUSDT','1m'),200)
        self.assertEqual(db.count_features('ETHUSDT','1m'),200)
        processor._ENGINES.clear()
        self.assertEqual(processor.maintenance(['ETHUSDT'],['1m']),5)
        result=db.read_features('ETHUSDT','1m',204*60000)
        self.assertEqual(result['formula_version'],3)
        self.assertIsInstance(result['ema_bull_structure'],bool)
        self.assertIn('nearest_inst_support_score',result)
        live=processor.preview('ETHUSDT','1m',bar(205,130))
        self.assertIsNotNone(live['rsi']);self.assertEqual(db.count_features('ETHUSDT','1m'),205)
        reference=Engine('ETHUSDT','1m')
        for i in range(205):packet=reference.step(bar(i,100+i%9))
        self.assertEqual(result['ema300'],packet['ema300'])
        # A failed commit must leave both the packet and checkpoint at the
        # previous candle, then retry from that committed state after restart.
        import sqlite3
        db.write_klines([bar(205,140)])
        conn=features_store.open_db()
        conn.execute('CREATE TRIGGER reject_feature BEFORE INSERT ON features WHEN NEW.open_time=12300000 BEGIN SELECT RAISE(ABORT,"injected write failure"); END');conn.commit();conn.close()
        from types import SimpleNamespace
        with self.assertRaises(sqlite3.IntegrityError):processor.process_bar(SimpleNamespace(symbol='ETHUSDT',timeframe='1m',open_time=205*60000))
        conn=features_store.open_db()
        self.assertEqual(conn.execute('SELECT last_open_time FROM feature_engine_state').fetchone()[0],204*60000)
        conn.execute('DROP TRIGGER reject_feature');conn.commit();conn.close()
        self.assertEqual(processor.catch_up('ETHUSDT','1m'),1)
        self.assertEqual(db.read_features('ETHUSDT','1m',205*60000)['ema300'],reference.step(bar(205,140))['ema300'])

    def test_failed_pair_does_not_starve_healthy_pairs_or_skip_failed_candle(self):
        db.write_klines([bar(i,100+i%9,symbol=symbol) for symbol in ('ETHUSDT','BTCUSDT') for i in range(3)])
        original=processor.build_feature_packet
        def fail(**kwargs):
            if kwargs['symbol']=='ETHUSDT':raise RuntimeError('injected candle calculation failure')
            return original(**kwargs)
        processor._cursor=0
        with patch.object(processor,'build_feature_packet',side_effect=fail):
            self.assertEqual(processor.maintenance(['ETHUSDT','BTCUSDT'],['1m'],time_budget=5),3)
        self.assertEqual(db.count_features('ETHUSDT','1m'),0)
        self.assertEqual(db.count_features('BTCUSDT','1m'),3)
        processor._ENGINES.clear()
        self.assertEqual(processor.maintenance(['ETHUSDT','BTCUSDT'],['1m'],time_budget=5),3)
        self.assertEqual(db.count_features('ETHUSDT','1m'),3)

    def test_disabled_interval_does_not_block_enabled_interval(self):
        db.write_klines([bar(i,100+i%9,interval=iv,step=60000 if iv=='1m' else 300000) for iv in ('1m','5m') for i in range(3)])
        processor._cursor=0
        with patch.object(processor.data_policy,'enabled',side_effect=lambda symbol,interval:interval=='5m'):
            self.assertEqual(processor.maintenance(['ETHUSDT'],['1m','5m'],time_budget=5),3)
        self.assertEqual(db.count_features('ETHUSDT','1m'),0)
        self.assertEqual(db.count_features('ETHUSDT','5m'),3)

    def test_recent_candles_do_not_make_replay_jump_unfinished_history(self):
        from Section_1_Global_Core.memory_storage.market_data import update_klines as updater
        def page(indices):return [[i*60000,'100','102','98','101','5',(i+1)*60000-1] for i in indices]
        db.write_klines([bar(i,100) for i in range(3)])
        phase=[0]
        def fetch(symbol,interval,start):
            if start is None:return page(range(10,13))
            self.assertEqual(start,120001 if phase[0]==0 else 300001)
            return page(range(3,6) if phase[0]==0 else range(6,13))
        with patch.object(updater,'_LATEST_UPDATE_MS',{}),patch.object(updater,'_LAST_UPDATE_MS',{}),patch.object(updater,'_fetch',side_effect=fetch),patch.object(updater.time,'time',return_value=780.1):
            conn=klines_store.open_db()
            try:
                self.assertEqual(updater.update_one('ETHUSDT','1m',conn),6)
                self.assertEqual(klines_store.history_cursor(conn,'ETHUSDT','1m'),300001)
                self.assertEqual(db.last_kline_time('ETHUSDT','1m'),720000)
                self.assertTrue(db.read_state_page('ETHUSDT','1m')['history_pending'])
                processor.catch_up('ETHUSDT','1m')
                self.assertIsNone(db.read_features('ETHUSDT','1m',600000))
                self.assertEqual(processor._load('ETHUSDT','1m',(0,0)).context.last_time,300000)
                phase[0]=1
                self.assertEqual(updater.update_one('ETHUSDT','1m',conn),4)
                self.assertIsNone(klines_store.history_cursor(conn,'ETHUSDT','1m'))
                self.assertFalse(db.read_state_page('ETHUSDT','1m')['history_pending'])
                processor.catch_up('ETHUSDT','1m')
                self.assertEqual(db.count_features('ETHUSDT','1m'),13)
            finally:conn.close()

    def test_recent_download_cannot_commit_after_policy_epoch_changes(self):
        from Section_1_Global_Core.memory_storage.market_data import update_klines as updater
        db.write_klines([bar(0,100)])
        epoch=[0]
        def fetch(*args):
            epoch[0]+=1
            return [[600000,'100','102','98','101','5',659999]]
        with patch.object(updater,'_pair_epoch',side_effect=lambda *args:(epoch[0],0)),patch.object(updater,'_LATEST_UPDATE_MS',{}),patch.object(updater,'_LAST_UPDATE_MS',{}),patch.object(updater,'_fetch',side_effect=fetch),patch.object(updater.time,'time',return_value=780.):
            conn=klines_store.open_db()
            try:self.assertEqual(updater.update_one('ETHUSDT','1m',conn),0)
            finally:conn.close()
        self.assertEqual(db.count_klines('ETHUSDT','1m'),1)

    def test_old_feature_memory_is_backed_up_before_replacement(self):
        db.write_klines([bar(0,100)])
        db.write_features([dict(symbol='ETHUSDT',interval='1m',open_time=0,ema50=123,formula_version=2)])
        processor.catch_up('ETHUSDT','1m')
        import sqlite3
        backup=features_store.DB_PATH.with_name('features.pre-pine-v3.db')
        with sqlite3.connect(backup) as conn:self.assertEqual(conn.execute('SELECT ema50 FROM features').fetchone()[0],123)
        self.assertEqual(db.read_features('ETHUSDT','1m',0)['ema50'],100)

    def test_higher_timeframe_daily_fields_fill_when_dependency_arrives(self):
        db.write_klines([bar(0,100,interval='3d',step=259200000)])
        processor.catch_up('ETHUSDT','3d')
        first=db.read_features('ETHUSDT','3d',0)
        self.assertFalse(first['daily_source_ready']);self.assertIsNone(first['previous_day_high'])
        db.write_klines([bar(i,100+i,interval='1d',step=86400000) for i in range(3)])
        processor.maintenance(['ETHUSDT'],['3d'])
        repaired=db.read_features('ETHUSDT','3d',0)
        self.assertTrue(repaired['daily_source_ready']);self.assertEqual(repaired['previous_day_high'],103)
        db.write_klines([bar(4320,110)])  # First real minute/open of day 4.
        with patch.object(processor.time,'time',return_value=3.5*86400):
            live=processor.preview('ETHUSDT','3d',bar(1,115,interval='3d',step=259200000))
        self.assertEqual(live['previous_day_high'],104)
        self.assertEqual(live['day_open'],109.5)

if __name__=='__main__':unittest.main()
