import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
import hashlib
import sqlite3
from unittest.mock import patch
from Section_4_Features.execution.engine import Engine
from Section_4_Features.execution import checkpoint
from Section_1_Global_Core.memory_storage.Storage import features_store
from Section_11_UI_UX.server import volume_profile


class ProfileSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.patch=patch.object(features_store,'DB_PATH',Path(self.temp.name)/'features.db');self.patch.start();self.addCleanup(self.patch.stop)
        volume_profile._CACHE.clear()
        self.engine=Engine('ETHUSDT','1m',{'vpLookback':4,'vpBins':4,'vpValueAreaPct':70})
        for i,(lo,volume) in enumerate(zip([0.,1.,2.,3.],[10.,40.,30.,20.])):
            bar=dict(symbol='ETHUSDT',interval='1m',open_time=i*60000,close_time=(i+1)*60000-1,open=lo+.05,close=lo+.05,high=lo+.1,low=lo,volume=volume)
            self.result=self.engine.step(bar)
        self.latest={'open_time':180000,'features':self.result}
        conn=features_store.open_db()
        with conn:conn.execute('INSERT INTO feature_engine_state VALUES (?,?,?,?)',('ETHUSDT','1m',180000,checkpoint.dump(self.engine,(0,0))))
        conn.close()

    def test_histogram_and_poc_value_area_match_independent_dense_vector(self):
        result=volume_profile.snapshot('ETHUSDT','1m',self.latest,'0:0')
        self.assertEqual(result['status'],'ready')
        self.assertEqual([b['volume'] for b in result['bins']],[10.,40.,30.,20.])
        self.assertAlmostEqual(sum(b['volume'] for b in result['bins']),100.)
        self.assertAlmostEqual(result['levels']['vp_poc'],1.1625)
        self.assertAlmostEqual(result['levels']['vp_va_low'],.775)
        self.assertAlmostEqual(result['levels']['vp_va_high'],2.325)
        self.assertEqual([b['node'] for b in result['bins']],['low','high','high','normal'])
        with patch.object(volume_profile.json,'loads',side_effect=AssertionError('unchanged state should be cached')):
            self.assertEqual(volume_profile.snapshot('ETHUSDT','1m',self.latest,'0:0'),result)

    def test_each_closed_candle_keeps_its_own_rolling_profile_levels(self):
        old=self.result
        new=self.engine.step(dict(symbol='ETHUSDT',interval='1m',open_time=240000,close_time=299999,
                                  open=10.05,close=10.05,high=10.1,low=10.,volume=100.))
        conn=features_store.open_db()
        try:
            features_store.insert_rows(conn,[old,new])
            rows=features_store.read_range(conn,'ETHUSDT','1m',0,300000)
        finally:conn.close()
        self.assertEqual([r['open_time'] for r in rows],[180000,240000])
        self.assertAlmostEqual(rows[0]['vp_poc'],1.1625)
        self.assertAlmostEqual(rows[0]['vp_va_low'],.775)
        self.assertAlmostEqual(rows[0]['vp_va_high'],2.325)
        self.assertAlmostEqual(rows[1]['vp_poc'],8.9625)
        self.assertAlmostEqual(rows[1]['vp_va_low'],1.)
        self.assertAlmostEqual(rows[1]['vp_va_high'],10.1)

    def test_wrong_candle_epoch_or_inconsistent_levels_withholds_histogram(self):
        for latest,epoch in [({'open_time':120000,'features':self.result},'0:0'),(self.latest,'1:0'),({'open_time':180000,'features':{**self.result,'vp_poc':99}},'0:0')]:
            self.assertNotEqual(volume_profile.snapshot('ETHUSDT','1m',latest,epoch)['status'],'ready')

    def test_targeted_profile_repair_withholds_old_bins(self):
        conn=features_store.open_db()
        with conn:conn.execute('INSERT INTO feature_replay_jobs VALUES (?,?,?,?,?,?,?,?)',('ETHUSDT','1m','test',180000,0,'[]',None,json.dumps(['vp_poc'])))
        conn.close()
        self.assertNotEqual(volume_profile.snapshot('ETHUSDT','1m',self.latest,'0:0')['status'],'ready')

    def test_missing_profile_state_is_nonfatal(self):
        conn=features_store.open_db()
        with conn:conn.execute("UPDATE feature_engine_state SET state='{}'")
        conn.close()
        self.assertEqual(volume_profile.snapshot('ETHUSDT','1m',self.latest,'0:0')['bins'],[])

    def test_generation_change_invalidates_cached_bins_even_when_levels_match(self):
        conn=features_store.open_db()
        with conn:conn.execute('INSERT INTO feature_calculation_versions(symbol,interval,signature,generation) VALUES (?,?,?,?)',('ETHUSDT','1m','same',0))
        conn.close()
        before=volume_profile.snapshot('ETHUSDT','1m',self.latest,'0:0')
        saved=json.loads(checkpoint.dump(self.engine,(0,0)))
        saved['state']['persistent']['vpVolumeBins']=[2*v for v in saved['state']['persistent']['vpVolumeBins']]
        conn=features_store.open_db()
        with conn:
            conn.execute('UPDATE feature_engine_state SET state=?',(json.dumps(saved),))
            conn.execute('UPDATE feature_calculation_versions SET generation=1')
        conn.close()
        after=volume_profile.snapshot('ETHUSDT','1m',self.latest,'0:0')
        self.assertEqual(after['status'],'ready')
        self.assertEqual([b['volume'] for b in after['bins']],[2*b['volume'] for b in before['bins']])

    def test_waiting_explains_checkpoint_and_repair_and_state_mismatch(self):
        wrong=volume_profile.snapshot('ETHUSDT','1m',dict(self.latest,open_time=120000),'0:0')
        self.assertIn('newer than the requested candle',wrong['reason'])
        self.assertEqual(wrong['checkpoint_time'],180000)
        saved=json.loads(checkpoint.dump(self.engine,(0,0)));saved['state']['last_time']=0
        conn=features_store.open_db()
        with conn:conn.execute('UPDATE feature_engine_state SET state=?',(json.dumps(saved),))
        conn.close()
        self.assertIn('state timestamp',volume_profile.snapshot('ETHUSDT','1m',self.latest,'0:0')['reason'])

    def test_last_completed_histogram_survives_a_new_candle_without_relabeling_it(self):
        conn=features_store.open_db();features_store.insert_rows(conn,[self.result]);conn.close()
        current=volume_profile.snapshot('ETHUSDT','1m',self.latest,'0:0')
        behind=volume_profile.snapshot('ETHUSDT','1m',{'open_time':240000,'features':{}},'0:0')
        self.assertEqual(behind['status'],'ready');self.assertTrue(behind['stale'])
        self.assertEqual(behind['as_of'],180000);self.assertEqual(behind['requested_time'],240000)
        self.assertEqual(behind['bins'],current['bins']);self.assertEqual(behind['levels'],current['levels'])
        fresh=volume_profile.snapshot('ETHUSDT','1m',self.latest,'0:0')
        self.assertFalse(fresh['stale']);self.assertFalse(current['stale'])
        # Wrong epochs and active VP repairs remain blocked, even for fallback.
        self.assertNotEqual(volume_profile.snapshot('ETHUSDT','1m',{'open_time':240000},'1:0')['status'],'ready')
        conn=features_store.open_db()
        with conn:conn.execute('INSERT INTO feature_replay_jobs VALUES (?,?,?,?,?,?,?,?)',('ETHUSDT','1m','test',180000,0,'[]',None,json.dumps(['vp_poc'])))
        conn.close()
        self.assertNotEqual(volume_profile.snapshot('ETHUSDT','1m',{'open_time':240000},'0:0')['status'],'ready')

    def test_read_only_node_diagnostic_reports_nonzero_hvn_and_lvn(self):
        from Section_1_Global_Core.memory_storage.Storage import klines_store
        import check_volume_profile
        raw=Path(self.temp.name)/'klines.db';conn=sqlite3.connect(raw)
        with conn:
            conn.execute('CREATE TABLE klines(symbol TEXT,interval TEXT,open_time INTEGER,close_time INTEGER)')
            conn.execute('INSERT INTO klines VALUES (?,?,?,?)',('ETHUSDT','1m',180000,239999))
        conn.close();conn=features_store.open_db();features_store.insert_rows(conn,[self.result]);conn.close()
        paths=(raw,features_store.DB_PATH);before=[hashlib.sha256(p.read_bytes()).hexdigest() for p in paths]
        with patch.object(klines_store,'DB_PATH',raw),patch.object(check_volume_profile.data_policy,'enabled',return_value=True),patch.object(check_volume_profile.data_policy,'read',return_value={'epochs':{}}):
            result=check_volume_profile.report('ETHUSDT',['1m'],now_ms=240000)
        row=result['frames'][0]
        self.assertEqual(row['status'],'ready');self.assertEqual(row['high_volume_nodes'],2);self.assertEqual(row['low_volume_nodes'],1)
        self.assertEqual(row['bins'],4);self.assertEqual(before,[hashlib.sha256(p.read_bytes()).hexdigest() for p in paths])
