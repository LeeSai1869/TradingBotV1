"""Compact result checksums preserve immutable history and reject divergence."""
from contextlib import redirect_stdout
from copy import deepcopy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import deduplicate_intelligence as cleanup
from Section_1_Global_Core.memory_storage.Storage import engine_store as store


class IntelligenceStorage(unittest.TestCase):
    def setUp(self):
        folder=self.enterContext(tempfile.TemporaryDirectory())
        self.path=Path(folder)/'intelligence.db'
        self.enterContext(patch.object(store,'DB_PATH',self.path))
        self.conn=store.open_db();self.addCleanup(self.conn.close)
        identity=dict(venue='binance',market_type='spot',instrument_id='BTCUSDT',
            symbol='BTCUSDT',timeframe='1m',dataset_generation='test')
        self.metadata=dict(identity=identity,engine='REGIME',engine_version='1.0.0',
            state_schema_version='1.0.0',config_hash='config',input_signature='inputs')
        self.run_id=store.digest(self.metadata)

    def candle(self,opened=0):
        binding=deepcopy(self.metadata)
        times=dict(candle_open_time=opened,candle_close_time=opened+59999,as_of=opened+60000)
        snapshot=dict(identity=binding['identity'],input_signature='inputs',**times,
            computed_at=10**9,closed=True,features=dict(adx=25.))
        result=dict(**binding,**times,computed_at=10**9,available_at=10**9,
            mode='CONFIRMED',confidence=.5,classification=dict(primary='TRENDING'),
            evidence=[dict(description='source evidence '*200)])
        state={key:binding[key] for key in ('identity','config_hash','input_signature','state_schema_version')}
        state.update(last_open=opened,last_close=opened+59999)
        return snapshot,result,state

    def write(self,opened=0):
        snapshot,result,state=self.candle(opened)
        store.commit_batch(self.conn,self.metadata,opened-60000 if opened else -1,[(snapshot,result)],state)
        return snapshot,result,state

    def rewind(self):
        with self.conn:self.conn.execute('UPDATE engine_runs SET cursor=-1,state=NULL WHERE run_id=?',(self.run_id,))

    def legacy(self,opened=0):
        result=json.loads(self.conn.execute('SELECT payload FROM engine_results WHERE candle_time=?',(opened,)).fetchone()[0])
        with self.conn:self.conn.execute('UPDATE engine_results SET deterministic=? WHERE candle_time=?',
            (store.encode(store.stable_result(result)),opened))

    def test_new_writes_keep_one_full_result_and_small_checksum(self):
        snapshot,result,state=self.write()
        row=self.conn.execute('SELECT deterministic,payload FROM engine_results').fetchone()
        self.assertEqual(row['deterministic'],store.result_checksum(result))
        self.assertEqual(len(row['deterministic']),71)
        self.assertGreater(len(row['payload']),len(row['deterministic'])*10)
        self.assertEqual(store.latest(self.conn,self.run_id),result)
        self.assertEqual(store.input_bundle(self.conn,self.run_id,0),{k:v for k,v in snapshot.items() if k!='computed_at'})
        self.assertEqual(store.load(self.conn,self.run_id),(0,state))

    def test_legacy_and_checksum_retries_ignore_only_execution_timestamps(self):
        snapshot,result,state=self.write()
        for legacy in (True,False):
            with self.subTest(legacy=legacy):
                check=store.encode(store.stable_result(result)) if legacy else store.result_checksum(result)
                with self.conn:self.conn.execute('UPDATE engine_results SET deterministic=?',(check,))
                self.rewind()
                retry=deepcopy(result);retry.update(computed_at=10**9+1,available_at=10**9+1)
                source=deepcopy(snapshot);source['computed_at']=10**9+1
                store.commit_batch(self.conn,self.metadata,-1,[(source,retry)],state)
                self.assertEqual(store.latest(self.conn,self.run_id),result)
                self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM engine_results').fetchone()[0],1)

    def test_both_formats_reject_changed_result_or_input_and_roll_back(self):
        snapshot,result,state=self.write()
        for legacy in (True,False):
            for change in ('result','input'):
                with self.subTest(legacy=legacy,change=change):
                    check=store.encode(store.stable_result(result)) if legacy else store.result_checksum(result)
                    with self.conn:self.conn.execute('UPDATE engine_results SET deterministic=?',(check,))
                    self.rewind()
                    source=deepcopy(snapshot);changed=deepcopy(result)
                    if change=='result':changed['confidence']=.6
                    else:source['features']['adx']=26.
                    with self.assertRaisesRegex(ValueError,'divergence'):
                        store.commit_batch(self.conn,self.metadata,-1,[(source,changed)],state)
                    self.assertEqual(store.load(self.conn,self.run_id),(-1,None))
                    self.assertEqual(store.latest(self.conn,self.run_id),result)
                    self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM engine_input_bundles').fetchone()[0],1)

    def test_cleanup_is_bounded_resumable_and_preserves_history(self):
        for opened in (0,60000,120000):self.write(opened)
        self.legacy(0);self.legacy(60000)
        results=[tuple(r) for r in self.conn.execute('SELECT run_id,candle_time,bundle_id,payload FROM engine_results ORDER BY rowid')]
        runs=[tuple(r) for r in self.conn.execute('SELECT * FROM engine_runs')]
        bundles=[tuple(r) for r in self.conn.execute('SELECT * FROM engine_input_bundles')]
        preview=cleanup.compact_batch(self.conn,limit=1)
        self.assertEqual((preview['scanned'],preview['duplicates'],preview['updated']),(1,1,0))
        self.assertTrue(self.conn.execute('SELECT deterministic FROM engine_results WHERE rowid=1').fetchone()[0].startswith('{'))
        first=cleanup.compact_batch(self.conn,limit=1,apply=True)
        self.assertEqual(first['updated'],1);self.assertGreater(first['json_bytes_removed'],0)
        second=cleanup.compact_batch(self.conn,after_rowid=first['last_rowid'],limit=2,apply=True)
        self.assertEqual((second['scanned'],second['updated']),(2,1))
        self.assertEqual(cleanup.compact_batch(self.conn,apply=True)['updated'],0)
        self.assertEqual(results,[tuple(r) for r in self.conn.execute('SELECT run_id,candle_time,bundle_id,payload FROM engine_results ORDER BY rowid')])
        self.assertEqual(runs,[tuple(r) for r in self.conn.execute('SELECT * FROM engine_runs')])
        self.assertEqual(bundles,[tuple(r) for r in self.conn.execute('SELECT * FROM engine_input_bundles')])
        self.assertEqual(cleanup.compact_batch(self.conn,after_rowid=second['last_rowid'])['scanned'],0)

    def test_cleanup_rolls_back_entire_batch_if_duplicate_disagrees(self):
        self.write();self.write(60000);self.legacy(0);self.legacy(60000)
        with self.conn:self.conn.execute("UPDATE engine_results SET deterministic='{}' WHERE rowid=2")
        before=[tuple(r) for r in self.conn.execute('SELECT * FROM engine_results ORDER BY rowid')]
        with self.assertRaisesRegex(ValueError,'mismatch'):
            cleanup.compact_batch(self.conn,limit=2,apply=True)
        self.assertEqual(before,[tuple(r) for r in self.conn.execute('SELECT * FROM engine_results ORDER BY rowid')])

    def test_cli_preview_does_not_write_and_apply_keeps_full_results(self):
        self.write();self.legacy()
        before=self.path.read_bytes();output=io.StringIO()
        with redirect_stdout(output):cleanup.main(['--database',str(self.path),'--max-rows','1'])
        self.assertEqual(self.path.read_bytes(),before)
        preview=json.loads(output.getvalue().splitlines()[0])
        self.assertEqual((preview['mode'],preview['duplicates'],preview['updated']),('preview',1,0))
        output=io.StringIO()
        with redirect_stdout(output):cleanup.main(['--database',str(self.path),'--apply','--max-rows','1'])
        report=json.loads(output.getvalue().splitlines()[0])
        self.assertEqual((report['updated'],report['last_rowid']),(1,1))
        self.assertEqual(self.conn.execute('SELECT length(deterministic) FROM engine_results').fetchone()[0],71)
        self.assertEqual(self.conn.execute('PRAGMA integrity_check').fetchone()[0],'ok')


if __name__=='__main__':unittest.main()
