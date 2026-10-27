"""Display metadata comes from existing committed arrays, without replay."""
import json
import sqlite3
import unittest
from unittest.mock import patch
from Section_1_Global_Core.memory_storage.Storage import db,features_store
from Section_1_Global_Core import data_policy


class SnapshotDisplayTests(unittest.TestCase):
    def test_identity_lookup_retains_origin_score_and_tests(self):
        conn=sqlite3.connect(':memory:')
        conn.execute('CREATE TABLE feature_engine_state(symbol,interval,last_open_time,state)')
        arrays=dict(srDisplayPrevious={'7':dict(side='support',low=10,high=12,institutional=True)},
            supportZoneIDArray=[9,7],supportOriginTimeArray=[1000,0],supportScoreArray=[0,40],
            supportTouchArray=[0,12],supportStrongRejectArray=[0,4],instSupportZoneIDArray=[7],instSupportScoreArray=[56])
        saved=dict(epoch=[0,0],state=dict(persistent=arrays))
        conn.execute('INSERT INTO feature_engine_state VALUES (?,?,?,?)',('BTCUSDT','4h',14400000,json.dumps(saved)))
        candles=sqlite3.connect(':memory:')
        candles.execute('CREATE TABLE klines(symbol,interval,open_time,close_time)')
        candles.execute('INSERT INTO klines VALUES (?,?,?,?)',('BTCUSDT','4h',14400000,28799999))
        with patch.object(features_store.DB_PATH.__class__,'exists',return_value=True),patch.object(db,'_read_connection',side_effect=[conn,candles]),patch.object(features_store,'pending_replay',return_value=None),patch.object(data_policy,'read',return_value={'epochs':{}}),patch.object(data_policy,'enabled',return_value=True):
            snapshot=db.read_sr_snapshot('BTCUSDT','4h')
        zone=snapshot['zones']['7']
        self.assertEqual(zone['origin_time'],0);self.assertEqual(zone['score'],56)
        self.assertEqual(zone['touches'],12);self.assertEqual(zone['strong_rejections'],4)
        self.assertTrue(snapshot['current']);self.assertEqual(snapshot['valid_until'],28800)
        self.assertEqual(snapshot['status'],'ready')
