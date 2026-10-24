from contextlib import ExitStack
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from test_complete_conversion import bar
from Section_1_Global_Core.memory_storage.Storage import db,features_store,klines_store
from Section_1_Global_Core.memory_storage.market_data import download_binance_history as downloader
from Section_1_Global_Core import data_policy
from Section_4_Features.execution.engine import Engine
from Section_4_Features.execution.checkpoint import dump


class FVGFramesTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.stack=ExitStack();self.addCleanup(self.stack.close)
        for store,name in [(features_store,'features'),(klines_store,'klines'),(downloader,'klines')]:
            self.stack.enter_context(patch.object(store,'DB_PATH',Path(self.temp.name)/(name+'.db')))
        self.stack.enter_context(patch.object(data_policy,'read',return_value={'epochs':{}}))
        downloader.open_db().close()
        self.engine=Engine('ETHUSDT','4h',{'atrLen':1,'FVG_MIN_ATR_MULT':.1})
        self.bars=[bar(i,c,interval='4h',step=14400000) for i,c in enumerate([10,10,16,17])]
        db.write_klines(self.bars);db.write_features([self.engine.step(b) for b in self.bars])
        conn=features_store.open_db()
        with conn:conn.execute('INSERT INTO feature_engine_state VALUES (?,?,?,?)',('ETHUSDT','4h',self.bars[-1]['open_time'],dump(self.engine,(0,0))))
        conn.close()

    def test_frame_uses_bounded_stored_features_and_all_checkpoint_active_gaps(self):
        frame=db.read_fvg_frame('ETHUSDT','4h')
        self.assertEqual(len(frame['bars']),4)
        expected=list(zip(self.engine.context.persistent['fvgBullLow'],self.engine.context.persistent['fvgBullHigh']))
        self.assertGreater(len(expected),0)
        self.assertEqual([(z['low'],z['high']) for z in frame['active'] if z['side']=='bull'],expected)
        self.assertTrue(frame['bars'][2]['features']['qualified_bull_fvg'])
        self.assertNotIn('ema50',frame['bars'][-1]['features'])
        with patch.object(klines_store,'read_last_n',side_effect=AssertionError('unchanged source must not reread history')):
            self.assertEqual(db.read_fvg_frame('ETHUSDT','4h',frame['version']),{'version':frame['version'],'unchanged':True})

    def test_current_chart_seed_packet_does_not_duplicate_feature_history(self):
        frame=db.read_fvg_frame('ETHUSDT','4h',include_bars=False)
        self.assertEqual(frame['bars'],[]);self.assertGreater(len(frame['active']),0)

    def test_pending_fvg_repair_masks_events_and_withholds_old_active_arrays(self):
        conn=features_store.open_db()
        with conn:conn.execute('INSERT INTO feature_replay_jobs VALUES (?,?,?,?,?,?,?,?)',('ETHUSDT','4h','test',self.bars[-1]['open_time'],-1,'[]',None,json.dumps(['qualified_bull_fvg','nearest_bull_fvg_low'])))
        conn.close()
        frame=db.read_fvg_frame('ETHUSDT','4h')
        self.assertEqual(frame['active'],[])
        self.assertIsNone(frame['bars'][2]['features']['qualified_bull_fvg'])

    def test_source_epoch_invalidates_browser_version_without_deleting_data(self):
        frame=db.read_fvg_frame('ETHUSDT','4h')
        from Section_1_Global_Core import data_policy
        with patch.object(data_policy,'read',return_value={'epochs':{'interval:4h':1}}):
            updated=db.read_fvg_frame('ETHUSDT','4h',frame['version'])
        self.assertNotEqual(updated['version'],frame['version']);self.assertEqual(updated['active'],[])

    def test_old_active_gaps_survive_the_next_raw_bar_before_features_arrive(self):
        previous=db.read_fvg_frame('ETHUSDT','4h')['active']
        db.write_klines([bar(4,18,interval='4h',step=14400000)])
        self.assertEqual(db.read_fvg_frame('ETHUSDT','4h')['active'],previous)
        # The same closed-candle invalidation applies while the feature writer
        # catches up; a touched close through the low removes the old gap.
        db.write_klines([bar(5,5,interval='4h',step=14400000,high=18,low=4)])
        self.assertEqual(db.read_fvg_frame('ETHUSDT','4h')['active'],[])

    def test_optional_source_failure_does_not_break_the_candle_response(self):
        import sqlite3
        from Section_11_UI_UX.server import routes
        with patch.object(db,'read_fvg_frame',side_effect=sqlite3.OperationalError('busy')):
            self.assertEqual(routes._fvg_frame('ETHUSDT','4h'),{'unchanged':True,'status':'stored FVG source unavailable'})

    def test_progress_reports_checkpoint_and_affected_repair_separately(self):
        latest=self.bars[-1]['open_time']
        progress=db.read_feature_progress('ETHUSDT','4h',latest)
        self.assertEqual(progress['through'],latest);self.assertEqual(progress['status'],'features current')
        pending=db.read_feature_progress('ETHUSDT','4h',latest+14400000,history_pending=True)
        self.assertEqual(pending['status'],'historical feature replay');self.assertTrue(pending['history_pending'])
        conn=features_store.open_db()
        with conn:conn.execute('INSERT INTO feature_replay_jobs VALUES (?,?,?,?,?,?,?,?)',('ETHUSDT','4h','test',latest,0,'[]',None,json.dumps(['nearest_bull_fvg_reaction_count'])))
        conn.close()
        repair=db.read_feature_progress('ETHUSDT','4h',latest)
        self.assertEqual(repair['repair'],{'through':0,'target':latest,'columns':1})
        self.assertEqual(repair['status'],'updating affected features')
