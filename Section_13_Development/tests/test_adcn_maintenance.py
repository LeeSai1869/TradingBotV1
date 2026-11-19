"""Retirement and obsolete-history cleanup protect live state and other memories."""
import unittest
import test_data_admin as fixtures
from Section_1_Global_Core import adcn_maintenance as cleanup
from Section_1_Global_Core.memory_storage.Storage import db,adcn_store

class AdcnMaintenance(unittest.TestCase):
    setUp=fixtures.DataAdminTests.setUp

    def test_retire_requires_preview_and_confirmation_then_blocks_repopulation(self):
        db.write_adcn([dict(symbol='BTCUSDT',interval='1m',open_time=120000,signal_type='BUY',trigger='DI_TURNING_POINT_V3',final_score=88)])
        data={'fields':['final_score']};plan=cleanup.preview(data)
        self.assertEqual(plan['clear_values'],{'final_score':1})
        with self.assertRaises(ValueError):cleanup.apply(plan)
        cleanup.apply({**plan,'confirmation':cleanup.CONFIRMATION})
        row=db.read_adcn('BTCUSDT','1m',120000)
        self.assertIsNone(row['final_score']);self.assertEqual(row['signal_type'],'BUY')
        db.write_adcn([dict(symbol='BTCUSDT',interval='1m',open_time=180000,final_score=99)])
        self.assertIsNone(db.read_adcn('BTCUSDT','1m',180000)['final_score'])
        cleanup.restore('final_score')
        db.write_adcn([dict(symbol='BTCUSDT',interval='1m',open_time=240000,final_score=77)])
        self.assertEqual(db.read_adcn('BTCUSDT','1m',240000)['final_score'],77)
        self.assertIsNone(db.read_adcn('BTCUSDT','1m',120000)['final_score'])

    def test_protected_fields_cannot_be_retired_and_stale_preview_fails(self):
        for field in cleanup.PROTECTED:
            with self.assertRaises(ValueError):cleanup.preview({'fields':[field]})
        plan=cleanup.preview({'fields':['final_score']})
        db.write_adcn([dict(symbol='BTCUSDT',interval='1m',open_time=120000,final_score=9)])
        with self.assertRaisesRegex(ValueError,'Preview changed'):cleanup.apply({**plan,'confirmation':cleanup.CONFIRMATION})
        self.assertEqual(db.read_adcn('BTCUSDT','1m',120000)['final_score'],9)

    def test_history_cleanup_preserves_current_signals_checkpoints_evidence_and_permanent_data(self):
        # Fixture has legacy BUY records on multiple pairs.
        db.write_adcn([dict(symbol='BTCUSDT',interval='1m',open_time=120000,signal_type='SELL',trigger='DI_TURNING_POINT_V3')])
        with adcn_store.open_db() as conn:
            conn.execute('INSERT INTO decision_rule_state VALUES (?,?,?,?)',('SUIUSDT','1m',60000,'{}'))
            conn.execute('INSERT INTO decision_evidence(symbol,interval,open_time,epoch,signal_type,signal_price,payload,recorded_ms,provenance) VALUES (?,?,?,?,?,?,?,?,?)',('BTCUSDT','1m',60000,'0','BUY',11,'{}',1,'test'))
        db.write_adcn([dict(symbol='BTCUSDT',interval='1m',open_time=180000,signal_type='BUY',trigger='OLD')])
        before=db.count_klines();features=db.read_state_range('BTCUSDT','1m',60000,120000)[0]['features']
        plan=cleanup.preview({'delete_legacy':True,'interval':'1m'})
        self.assertEqual(plan['obsolete_rows'],1)
        cleanup.apply({**plan,'confirmation':cleanup.CONFIRMATION})
        self.assertIsNone(db.read_adcn('BTCUSDT','1m',180000))
        self.assertIsNotNone(db.read_adcn('BTCUSDT','1m',60000))
        self.assertIsNotNone(db.read_adcn('SUIUSDT','1m',60000))
        self.assertIsNotNone(db.read_adcn('BTCUSDT','1m',120000))
        self.assertEqual(db.count_klines(),before)
        self.assertEqual(db.read_state_range('BTCUSDT','1m',60000,120000)[0]['features'],features)

if __name__=='__main__':unittest.main()
