"""Real stored-feature read-only projection, safe paging and replay blockers."""
import json
import unittest
from Section_1_Global_Core import event_history,regime_inputs
from Section_1_Global_Core.memory_storage.Storage import features_store
import test_regime_history as fixtures

class EventHistory(unittest.TestCase):
    def setUp(self):fixtures.RegimeHistory.setUp(self)

    def test_paging_matches_whole_prefix_and_does_not_write_stores(self):
        source=regime_inputs.open_sources()
        try:before=source.execute('SELECT COUNT(*),MAX(open_time) FROM features').fetchone()
        finally:source.close()
        whole=event_history.history('BTCUSDT','1m',limit=65,now_ms=10**9)
        self.assertEqual(whole['status'],'READY');self.assertEqual(whole['scanned'],65)
        self.assertTrue(whole['events'])
        pages=[];cursor=None
        for _ in range(10):
            packet=event_history.history('BTCUSDT','1m',limit=10,before=cursor,now_ms=10**9)
            pages.extend(packet['events'])
            if not packet['has_more']:break
            self.assertIsNotNone(packet['next_before']);cursor=packet['next_before']
        self.assertEqual({event['id'] for event in pages},{event['id'] for event in whole['events']})
        self.assertEqual(len(pages),len({event['id'] for event in pages}))
        source=regime_inputs.open_sources()
        try:self.assertEqual(source.execute('SELECT COUNT(*),MAX(open_time) FROM features').fetchone(),before)
        finally:source.close()
        json.dumps(whole,allow_nan=False)

    def test_future_raw_candles_not_admitted_and_replay_blocks_history(self):
        result=event_history.history('BTCUSDT','1m',limit=65,now_ms=600000)
        self.assertTrue(all(event['known_time']<=600000 for event in result['events']))
        bounded=event_history.history('BTCUSDT','1m',limit=65,before=650000,now_ms=10**9)
        self.assertTrue(all(event['known_time']<=650000 for event in bounded['events']))
        self.assertLessEqual(bounded['window_end'],9*60000)
        conn=features_store.open_db()
        with conn:conn.execute("UPDATE feature_calculation_versions SET signature='outdated'")
        conn.close()
        result=event_history.history('BTCUSDT','1m',now_ms=10**9)
        self.assertEqual(result['status'],'UNAVAILABLE');self.assertEqual(result['events'],[])

    def test_validation_and_missing_rows_suppress_false_transitions(self):
        for kwargs in (dict(interval='4h'),dict(interval='5m',limit=1001),dict(interval='1m',before=-1)):
            with self.assertRaises(ValueError):event_history.history('BTCUSDT',**kwargs)
        conn=features_store.open_db()
        with conn:conn.execute('DELETE FROM features WHERE open_time=?',(30*60000,))
        conn.close()
        result=event_history.history('BTCUSDT','1m',limit=65,now_ms=10**9)
        self.assertTrue(result['warnings']);self.assertFalse(any(event['stage']=='CANDIDATE' and event['observed_open']==31*60000 for event in result['events']))

    def test_event_cap_pages_whole_candles_without_losing_source_events(self):
        conn=features_store.open_db();expected=set()
        with conn:
            for client in self.clients:
                events=[]
                for index in range(64):
                    identifier=str(client['open_time'])+'-'+str(index);expected.add(identifier)
                    events.append(dict(type='BOS',id=identifier,origin_time=0,known_time=client['close_time']+1))
                conn.execute('UPDATE features SET structure_events=? WHERE open_time=?',(json.dumps(events),client['open_time']))
        conn.close();found=[];ids=[];before=None;trimmed=False
        for _ in range(5):
            packet=event_history.history('BTCUSDT','1m',limit=65,before=before,now_ms=10**9)
            self.assertLessEqual(len(packet['events']),2000);trimmed|=packet['events_trimmed']
            ids.extend(event['id'] for event in packet['events'])
            found.extend(event['source_id'] for event in packet['events'] if event['type']=='STRUCTURE_BOS')
            if not packet['has_more']:break
            before=packet['next_before']
        self.assertTrue(trimmed);self.assertEqual(set(found),expected);self.assertEqual(len(found),len(expected));self.assertEqual(len(ids),len(set(ids)))
