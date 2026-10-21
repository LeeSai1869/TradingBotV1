"""Sparse histogram boundaries must not trap the feature runner in a loop."""
import json
import subprocess
import sys
import unittest
from Section_4_Features.execution.engine import Engine


def profile(highs,lows,volumes,bins):
    engine=Engine('ETHUSDT','1m',{'vpLookback':len(highs),'vpBins':bins,'vpValueAreaPct':70})
    for i,(high,low,volume) in enumerate(zip(highs,lows,volumes)):
        close=(high+low)/2
        result=engine.step(dict(symbol='ETHUSDT',interval='1m',open_time=i*60000,
                               close_time=(i+1)*60000-1,open=close,close=close,
                               high=high,low=low,volume=volume))
    return result['vp_poc'],result['vp_vah'],result['vp_val']


class VolumeProfileProgressTests(unittest.TestCase):
    def test_left_edge_poc_with_empty_neighbors_finishes(self):
        # Run in a child with a deadline: the original bug loops forever.
        code="""
import json
import sys
sys.path.insert(0,"tests")
from test_volume_profile_progress import profile
print(json.dumps(profile([.1,3.1],[0.,3.],[60.,40.],4)))
"""
        result=subprocess.run([sys.executable,'-c',code],capture_output=True,text=True,timeout=10,check=True)
        result=json.loads(result.stdout)
        self.assertAlmostEqual(result[2],0.)
        self.assertAlmostEqual(result[1],3.1)
        self.assertGreater(result[0],0.)

    def test_right_edge_and_single_bin_stay_inside_price_range(self):
        for volumes,bins in (([40.,60.],4),([60.,40.],1)):
            result=profile([.1,3.1],[0.,3.],volumes,bins)
            self.assertGreaterEqual(result[2],0.)
            self.assertLessEqual(result[1],3.1+1e-12)
            self.assertLessEqual(result[2],result[1])

    def test_dense_histogram_retains_expected_value_area(self):
        result=profile([.1,1.1,2.1,3.1],[0.,1.,2.,3.],[10.,40.,30.,20.],4)
        self.assertAlmostEqual(result[2],.775)
        self.assertAlmostEqual(result[1],2.325)

    def test_full_feature_builder_finishes_with_sparse_volume_profile(self):
        code="""
import pandas as pd
from Section_4_Features.feature_builder import build_feature_packet
frame=pd.DataFrame({'time':[i*60000 for i in range(500)],'open':[100.01]*499+[103.01],
                    'high':[100.1]*499+[103.1],'low':[100.]*499+[103.],
                    'close':[100.05]*499+[103.05],'volume':[1.]*499+[150.]})
packet=build_feature_packet(tf='1m',symbol='ETHUSDT',df=frame,bar_index=499,is_confirmed=True)
assert packet.valid
assert packet.features['ema50'] is not None
print('FEATURE_PACKET_COMPLETE')
"""
        result=subprocess.run([sys.executable,'-c',code],capture_output=True,text=True,timeout=10,check=True)
        self.assertIn('FEATURE_PACKET_COMPLETE',result.stdout)
