"""Sparse histogram boundaries must not trap the feature runner in a loop."""
import json
import subprocess
import sys
import unittest
import numpy as np
from Section_4_Features.features.market_location import _calculate_volume_profile


class VolumeProfileProgressTests(unittest.TestCase):
    def test_left_edge_poc_with_empty_neighbors_finishes(self):
        # Run in a child with a deadline: the original bug loops forever.
        code='''
import json
import numpy as np
from Section_4_Features.features.market_location import _calculate_volume_profile
result=_calculate_volume_profile(np.array([.1,3.1]),np.array([0.,3.]),np.array([60.,40.]),2,4,70.)
print(json.dumps(result))
'''
        result=subprocess.run([sys.executable,'-c',code],capture_output=True,text=True,timeout=10,check=True)
        profile=json.loads(result.stdout)
        self.assertAlmostEqual(profile[2],0.)
        self.assertAlmostEqual(profile[1],3.1)
        self.assertGreater(profile[0],0.)

    def test_right_edge_and_single_bin_stay_inside_price_range(self):
        for volumes,bins in (([40.,60.],4),([60.,40.],1)):
            profile=_calculate_volume_profile(np.array([.1,3.1]),np.array([0.,3.]),np.array(volumes),2,bins,70.)
            self.assertGreaterEqual(profile[2],0.)
            self.assertLessEqual(profile[1],3.1+1e-12)
            self.assertLessEqual(profile[2],profile[1])

    def test_dense_histogram_retains_expected_value_area(self):
        profile=_calculate_volume_profile(np.array([.1,1.1,2.1,3.1]),np.array([0.,1.,2.,3.]),np.array([10.,40.,30.,20.]),4,4,70.)
        self.assertAlmostEqual(profile[2],.775)
        self.assertAlmostEqual(profile[1],2.325)

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
