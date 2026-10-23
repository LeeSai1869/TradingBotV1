import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
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

    def test_wrong_candle_epoch_or_inconsistent_levels_withholds_histogram(self):
        for latest,epoch in [({'open_time':240000,'features':self.result},'0:0'),(self.latest,'1:0'),({'open_time':180000,'features':{**self.result,'vp_poc':99}},'0:0')]:
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
