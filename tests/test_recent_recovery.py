"""Latest prices must not leave recent feature/decision progress frozen."""
import sqlite3
import unittest
from unittest.mock import patch
import test_regime_history as fixtures
from Section_1_Global_Core import work_priority
from Section_1_Global_Core.memory_storage.Storage import db,features_store,klines_store
from Section_1_Global_Core.memory_storage.market_data import update_klines as updater
from Section_4_Features import processor
from Section_11_UI_UX.server import auth


class RecentRecovery(unittest.TestCase):
    setUp=fixtures.RegimeHistory.setUp

    def extend(self):
        rows=[dict(self.clients[-1],open_time=i*60000,close_time=(i+1)*60000-1) for i in range(65,85)]
        db.write_klines(rows)
        conn=klines_store.open_db()
        klines_store.ensure_history_progress(conn)
        with conn:conn.execute('INSERT OR REPLACE INTO history_progress VALUES (?,?,?)',('BTCUSDT','1m',64*60000+1))
        conn.close()
        work_priority._live_cursors.clear();work_priority._service_phases.clear()
        self.addCleanup(processor.reset_pair,'BTCUSDT','1m')

    def test_contiguous_latest_page_releases_stale_cursor_and_recovers_more_than_twelve_features(self):
        self.extend();conn=klines_store.open_db()
        try:
            auth.SESSIONS['recovery-test']=('admin','admin',10**12)
            auth.logout('recovery-test')
            self.assertEqual(auth.identity('recovery-test')['role'],'guest')
            with patch.object(updater.time,'time',return_value=86*60),patch.object(updater,'_LAST_UPDATE_MS',{}),patch.object(updater,'_LATEST_UPDATE_MS',{}),patch.object(updater,'_fetch',return_value=[]):
                updater.update_one('BTCUSDT','1m',conn,latest_only=True)
                self.assertIsNone(klines_store.history_cursor(conn,'BTCUSDT','1m'))
                self.assertEqual(processor.maintain_recent(['BTCUSDT'],['1m'],time_budget=5),20)
            with sqlite3.connect(features_store.DB_PATH) as source:
                self.assertEqual(source.execute("SELECT last_open_time FROM feature_engine_state WHERE symbol='BTCUSDT' AND interval='1m'").fetchone()[0],84*60000)
        finally:conn.close()

    def test_a_real_hole_keeps_the_cursor_and_never_admits_later_features(self):
        self.extend();conn=klines_store.open_db()
        try:
            with conn:conn.execute("DELETE FROM klines WHERE symbol='BTCUSDT' AND interval='1m' AND open_time=?",(70*60000,))
            with patch.object(updater.time,'time',return_value=86*60),patch.object(updater,'_LAST_UPDATE_MS',{}),patch.object(updater,'_LATEST_UPDATE_MS',{}),patch.object(updater,'_fetch',return_value=[]):
                updater.update_one('BTCUSDT','1m',conn,latest_only=True)
                cursor=klines_store.history_cursor(conn,'BTCUSDT','1m')
                self.assertEqual(cursor,69*60000+1)
                self.assertEqual(processor.maintain_recent(['BTCUSDT'],['1m'],time_budget=5),5)
            with sqlite3.connect(features_store.DB_PATH) as source:
                self.assertEqual(source.execute("SELECT last_open_time FROM feature_engine_state WHERE symbol='BTCUSDT' AND interval='1m'").fetchone()[0],69*60000)
        finally:conn.close()

    def test_deep_source_backfill_stays_with_owner_and_is_not_fast_forwarded(self):
        self.extend();conn=klines_store.open_db()
        try:
            with conn:conn.execute("UPDATE history_progress SET next_open_time=1 WHERE symbol='BTCUSDT' AND interval='1m'")
            with patch.object(updater.time,'time',return_value=40*86400),patch.object(updater,'_LAST_UPDATE_MS',{}),patch.object(updater,'_LATEST_UPDATE_MS',{}),patch.object(updater,'_fetch',return_value=[]) as fetch:
                updater.update_one('BTCUSDT','1m',conn,latest_only=True)
                self.assertEqual(klines_store.history_cursor(conn,'BTCUSDT','1m'),1)
                self.assertEqual([c.args[2] for c in fetch.call_args_list],[None])
                self.assertEqual(processor.maintain_recent(['BTCUSDT'],['1m'],time_budget=5),0)
        finally:conn.close()


if __name__=='__main__':unittest.main()
