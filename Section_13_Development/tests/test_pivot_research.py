import json
import unittest
from Section_1_Global_Core import pivot_research,regime_inputs
from Section_1_Global_Core.memory_storage.Storage import features_store,klines_store
import test_regime_history as fixtures


class PivotCohort(unittest.TestCase):
    def setUp(self):
        fixtures.RegimeHistory.setUp(self)
        self.pivots=[];conn=features_store.open_db()
        with conn:
            conn.execute("UPDATE features SET structure_events='[]',structure_events_version='structure-events-v1',structure_event_status='READY'")
            for index,(kind,origin,detection,price) in enumerate([('LOW',0,3,99.),('HIGH',5,7,102.5),('LOW',10,12,100.)]):
                event=dict(id=f'{index+1:064x}',type='PIVOT_'+kind,origin_time=origin*60000,
                           confirmation_time=detection*60000,known_time=(detection+1)*60000,price=price)
                self.pivots.append(event)
                conn.execute('UPDATE features SET structure_events=? WHERE open_time=?',(json.dumps([event]),detection*60000))
        conn.close()

    def study(self,**kwargs):return pivot_research.scan('BTCUSDT','1m',now_ms=10**9,**kwargs)

    def test_complete_cohort_separates_retrospective_and_after_known_outcomes(self):
        report=self.study()
        self.assertEqual(len(report['cases']),3)
        low=report['cases'][0]
        self.assertEqual(low['next_opposite']['origin_time'],5*60000)
        self.assertTrue(low['origin_hit_by_confirmation'])
        self.assertEqual(low['origin']['first_hit']['bars'],1)
        self.assertEqual(low['after_known']['reference'],100.4)
        self.assertEqual(low['after_known']['first_hit']['bars'],2)
        high=report['cases'][1]
        self.assertEqual(high['side'],'SELL_SIDE')
        self.assertEqual(high['origin']['status'],'HIT')
        self.assertEqual(high['after_known']['status'],'NO_HIT')
        self.assertFalse(report['cases'][-1]['origin']['complete'])
        json.dumps(report,allow_nan=False)

    def test_no_post_confirmation_window_and_no_future_confirmed_pivots(self):
        conn=features_store.open_db();event=self.pivots[0].copy();event.update(confirmation_time=6*60000,known_time=7*60000)
        with conn:
            conn.execute("UPDATE features SET structure_events='[]' WHERE open_time=?",(3*60000,))
            conn.execute('UPDATE features SET structure_events=? WHERE open_time=?',(json.dumps([event]),6*60000))
        conn.close()
        report=self.study()
        self.assertEqual(report['cases'][0]['after_known']['status'],'NO_POST_CONFIRMATION_WINDOW')
        early=self.study(until=6*60000)
        self.assertFalse(early['cases']) # event is not yet known

    def test_context_exports_all_columns_with_cutoff_and_source_guard(self):
        report=self.study();event=self.pivots[0]
        packet=pivot_research.case_context('BTCUSDT','1m',event['id'],event['known_time'],source_id=report['source_id'],before=2,after=3,as_of=6*60000)
        self.assertEqual(packet['status'],'READY')
        self.assertTrue(all(r['client']['close_time']<6*60000 for r in packet['bars']))
        self.assertIn('ema200',packet['bars'][0]['features'])
        self.assertTrue(any(r['availability']=='DETECTION_CANDLE' for r in packet['bars']))
        with self.assertRaises(regime_inputs.InputsUnavailable):
            pivot_research.case_context('BTCUSDT','1m',event['id'],event['known_time'],source_id='wrong')

    def test_replay_blocks_scan_and_stores_remain_unchanged(self):
        conn=features_store.open_db();before=conn.execute('SELECT COUNT(*),MAX(open_time) FROM features').fetchone();conn.close()
        self.study()
        conn=features_store.open_db();self.assertEqual(before,conn.execute('SELECT COUNT(*),MAX(open_time) FROM features').fetchone())
        with conn:conn.execute("UPDATE feature_calculation_versions SET signature='old'")
        conn.close()
        with self.assertRaises(regime_inputs.InputsUnavailable):self.study()

    def test_missing_raw_bar_is_visible_not_fabricated(self):
        conn=klines_store.open_db()
        with conn:conn.execute("DELETE FROM klines WHERE symbol='BTCUSDT' AND interval='1m' AND open_time=?",(4*60000,))
        conn.close();report=self.study()
        self.assertEqual(report['cases'][0]['after_known']['status'],'CENSORED')

    def test_scan_is_not_limited_to_a_recent_thousand_candles(self):
        from Section_1_Global_Core.memory_storage.Storage import db
        clients=[dict(symbol='BTCUSDT',interval='1m',open_time=n*60000,close_time=(n+1)*60000-1,
                      open=100,high=101,low=99,close=100,volume=10) for n in range(1105)]
        db.write_klines(clients)
        event=dict(id='f'*64,type='PIVOT_HIGH',origin_time=1100*60000,confirmation_time=1102*60000,known_time=1103*60000,price=101)
        conn=features_store.open_db()
        with conn:
            conn.execute("UPDATE features SET structure_events='[]'")
            low=self.pivots[0]
            conn.execute('UPDATE features SET structure_events=? WHERE open_time=?',(json.dumps([low]),3*60000))
            conn.execute('''INSERT INTO features(symbol,interval,open_time,formula_version,measurement_version,measurement_config_id,structure_events_version,structure_event_status,structure_events)
                         VALUES ('BTCUSDT','1m',?,3,'shared-v1','test','structure-events-v1','READY',?)''',(1102*60000,json.dumps([event])))
            conn.execute("UPDATE feature_engine_state SET last_open_time=?",(1104*60000,))
        conn.close()
        packet=self.study()
        self.assertEqual(packet['coverage']['candles'],1105)
        self.assertEqual(packet['cases'][0]['pivot']['origin_time'],0)
        self.assertEqual(packet['cases'][0]['next_opposite']['origin_time'],1100*60000)
        self.assertEqual(len(packet['cases']),2)
