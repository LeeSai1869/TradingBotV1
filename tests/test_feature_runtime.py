"""Recovery preferences change scheduling only; actual replay remains chronological."""
from contextlib import contextmanager
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from Section_1_Global_Core import feature_runtime as runtime,work_priority
from Section_4_Features import processor

class RuntimeConfig(unittest.TestCase):
    def test_defaults_bounds_and_local_atomic_config(self):
        with tempfile.TemporaryDirectory() as temp,patch.object(runtime,'CONFIG_FILE',Path(temp)/'runtime.json'):
            self.assertEqual(runtime.read(),runtime.DEFAULTS);self.assertFalse(runtime.CONFIG_FILE.exists())
            cfg=dict(time_budget=3.,max_bars=3000,priority=dict(symbol='BTCUSDT',timeframe='5m'))
            runtime.write(cfg);self.assertEqual(runtime.read(),cfg)
            for change in (dict(time_budget=float('nan')),dict(time_budget=11),dict(max_bars=True),dict(max_bars=0),dict(priority=dict(symbol='BTC',timeframe='bad')),dict(extra=1)):
                with self.assertRaises(ValueError):runtime.validate(change)
            self.assertEqual(runtime.read(),cfg)

    def test_priority_gets_bulk_turn_and_other_frames_get_background_turns(self):
        config=dict(time_budget=3.,max_bars=3000,priority=dict(symbol='BTC',timeframe='5m'))
        calls=[]
        def advance(symbol,interval,cap,deadline):calls.append((symbol,interval,cap));return 10
        with patch.object(runtime,'read',return_value=config),patch.object(processor,'_recover_runtime_format_job'),patch.object(work_priority,'pending_feature_pair',return_value=True),patch.object(work_priority,'work_symbol') as bulk,patch.object(work_priority,'service_pair',return_value=('BTC','1h')) as background,patch.object(processor,'_advance',side_effect=advance),patch.object(processor,'_repair_daily'):
            processor.maintenance(['BTC','ENA'],['5m','1h'])
            self.assertEqual([row[:2] for row in calls],[('BTC','1h'),('BTC','5m')]);self.assertEqual(calls[0][2],750)
            self.assertEqual(background.call_args.kwargs,dict(owner_interval='5m'));bulk.assert_not_called()

    def test_completed_or_inactive_priority_returns_to_normal_owner(self):
        config=dict(time_budget=1.,max_bars=1000,priority=dict(symbol='BTC',timeframe='5m'))
        with patch.object(runtime,'read',return_value=config),patch.object(processor,'_recover_runtime_format_job'),patch.object(work_priority,'pending_feature_pair',return_value=False),patch.object(work_priority,'work_symbol',return_value='ENA') as bulk,patch.object(work_priority,'service_pair',return_value=None),patch.object(processor,'_advance',return_value=0) as advance,patch.object(processor,'_repair_daily'):
            processor.maintenance(['BTC','ENA'],['5m']);self.assertEqual(advance.call_args.args[:2],('ENA','5m'))
            processor.maintenance(['ENA'],['5m']);self.assertEqual(bulk.call_count,2)


class CheckpointSerialization(unittest.TestCase):
    def raw_features(self):
        from test_selective_features import SelectiveFeatures
        return SelectiveFeatures.raw_features(self)

    def setUp(self):
        from test_selective_features import SelectiveFeatures
        SelectiveFeatures.setUp(self)

    def test_full_batch_serializes_outside_writer_lock_and_restores_identically(self):
        from test_complete_conversion import bar
        from Section_1_Global_Core.memory_storage.Storage import db,features_store
        from Section_4_Features.execution import checkpoint
        flags=[];held=[False];original=checkpoint.dump
        @contextmanager
        def locked(**kwargs):
            previous=held[0];held[0]=True
            try:yield
            finally:held[0]=previous
        def dump(*args):flags.append(held[0]);return original(*args)
        # Finish any metadata initialization before recording the write-stage dump.
        processor.catch_up('ETHUSDT','1m')
        new=bar(220,114);db.write_klines([new])
        with patch.object(processor.data_policy,'locked',side_effect=locked),patch.object(checkpoint,'dump',side_effect=dump):processor.catch_up('ETHUSDT','1m')
        self.assertTrue(flags);self.assertFalse(flags[-1])
        conn=features_store.open_db()
        try:row=conn.execute('SELECT state FROM feature_engine_state WHERE symbol=? AND interval=?',('ETHUSDT','1m')).fetchone()
        finally:conn.close()
        restored=checkpoint.restore('ETHUSDT','1m',row[0],(0,0));self.assertEqual(restored.context.last_time,new['open_time'])
        following=bar(221,115)
        expected=self.engine.step(new);expected_next=self.engine.step(following)
        self.assertEqual(restored.step(following)['rsi'],expected_next['rsi'])

    def test_targeted_serialization_failure_cannot_advance_stored_checkpoint(self):
        from Section_4_Features.execution import checkpoint
        from Section_1_Global_Core.memory_storage.Storage import features_store
        from test_selective_features import SelectiveFeatures
        SelectiveFeatures.config(self,rsiLen=11)
        engine=processor._load('ETHUSDT','1m',(0,0));processor._prepare_engine('ETHUSDT','1m',engine,(0,0))
        conn=features_store.open_db()
        try:before=conn.execute('SELECT last_time,state FROM feature_replay_jobs').fetchone()
        finally:conn.close()
        with patch.object(checkpoint,'dump',side_effect=RuntimeError('serialize failed')):
            with self.assertRaises(RuntimeError):processor.catch_up('ETHUSDT','1m')
        conn=features_store.open_db()
        try:self.assertEqual(tuple(conn.execute('SELECT last_time,state FROM feature_replay_jobs').fetchone()),tuple(before))
        finally:conn.close()
