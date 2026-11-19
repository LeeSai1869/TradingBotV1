from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from Section_1_Global_Core import data_policy
from Section_1_Global_Core.memory_storage.Storage import features_store as store


class AliasStorage(unittest.TestCase):
    def setUp(self):
        folder=self.enterContext(tempfile.TemporaryDirectory())
        self.enterContext(patch.object(data_policy,'LOCK_FILE',Path(folder)/'policy.lock'))
        self.enterContext(patch.object(store,'DB_PATH',Path(folder)/'features.db'))
        self.conn=store.open_db();self.addCleanup(self.conn.close)

    def test_only_verified_aliases_are_virtual(self):
        info={r[1]:r[6] for r in self.conn.execute('PRAGMA table_xinfo(features)')}
        self.assertEqual(len(store.STORAGE_ALIASES),24)
        for alias in store.STORAGE_ALIASES:self.assertEqual(info[alias],2)
        for name in ('swing_pivot_high_confirmed','swing_pivot_low_confirmed'):self.assertEqual(info[name],0)
        self.assertEqual(len(store.storage_columns(self.conn)),len(store.COLUMNS)-24-len(store.FORMULA_COLUMNS))

    def test_legacy_name_writes_canonical_once_and_all_readers_see_value(self):
        store.insert_rows(self.conn,[dict(symbol='BTCUSDT',interval='1m',open_time=0,formula_version=3,prev_close=123.)])
        self.assertEqual(tuple(self.conn.execute('SELECT c1,prev_close FROM features').fetchone()),(123.,123.))
        self.assertEqual(store.read_row(self.conn,'BTCUSDT','1m',0)['prev_close'],123.)
        values=store.read_replay_inputs(self.conn,'BTCUSDT','1m',0,1,['prev_close'])
        self.assertEqual(values[0]['prev_close'],123.)
        with self.conn:self.conn.execute('UPDATE features SET c1=124')
        self.assertEqual(self.conn.execute('SELECT prev_close FROM features').fetchone()[0],124.)

    def test_conflicting_inputs_cannot_be_silently_discarded(self):
        with self.assertRaisesRegex(ValueError,'Conflicting'):
            store.insert_rows(self.conn,[dict(symbol='BTCUSDT',interval='1m',open_time=0,c1=1,prev_close=2)])

    def test_rebuild_preserves_alias_only_legacy_values_and_checkpoints(self):
        from contextlib import closing,redirect_stdout
        import io,sqlite3
        from Section_14_Operations.storage.retire_feature_aliases import migrate
        info=self.conn.execute('PRAGMA table_xinfo(features)').fetchall()
        with self.conn:
            self.conn.execute('DROP TABLE features')
            definition=','.join(r[1]+' '+r[2] for r in info)
            self.conn.execute('CREATE TABLE features('+definition+',PRIMARY KEY(symbol,interval,open_time))')
            self.conn.execute("INSERT INTO features(symbol,interval,open_time,formula_version,prev_close) VALUES ('BTCUSDT','1m',0,1,123)")
            self.conn.execute("INSERT INTO feature_engine_state VALUES ('BTCUSDT','1m',0,'{}')")
        self.conn.close()
        with redirect_stdout(io.StringIO()):migrate(store.DB_PATH,report=store.DB_PATH.parent/'report.json')
        with closing(store.open_db()) as conn:
            self.assertEqual(conn.execute('SELECT c1,prev_close,formula_version FROM features').fetchone(),(123.,123.,1))
            self.assertEqual(conn.execute('SELECT state FROM feature_engine_state').fetchone()[0],'{}')
            self.assertEqual(len(store.storage_columns(conn)),len(store.COLUMNS)-24-len(store.FORMULA_COLUMNS))


if __name__=='__main__':unittest.main()
