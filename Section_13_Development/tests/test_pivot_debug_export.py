import importlib.util
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

PATH=Path(__file__).resolve().parents[1]/'diagnostics/export_pivot_debug.py'
spec=importlib.util.spec_from_file_location('pivot_debug',PATH);export=importlib.util.module_from_spec(spec);spec.loader.exec_module(export)


class PivotExport(unittest.TestCase):
    def test_bounded_pair_scoped_readonly_export_keeps_raw_fields_and_checkpoint(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);storage=root/'storage';storage.mkdir()
            feature=storage/'features.db';raw=storage/'klines.db'
            with sqlite3.connect(raw) as c:
                c.execute('CREATE TABLE klines(symbol,interval,open_time,close_time,open,high,low,close,volume,PRIMARY KEY(symbol,interval,open_time))')
                c.executemany('INSERT INTO klines VALUES (?,?,?,?,?,?,?,?,?)',[('ENAUSDT','15m',i*900000,(i+1)*900000-1,1,2,.5,1,10) for i in range(4)])
            with sqlite3.connect(feature) as c:
                c.execute('CREATE TABLE features(symbol,interval,open_time,candidate_pivot,structure_events,secret_other_column,PRIMARY KEY(symbol,interval,open_time))')
                c.executemany('INSERT INTO features VALUES (?,?,?,?,?,?)',[('ENAUSDT','15m',i*900000,1,'[]' if i==2 else None,'not included') for i in range(4)])
                c.execute('CREATE TABLE feature_engine_state(symbol,interval,last_open_time,state)')
                state=json.dumps({'version':3,'state':{'index':3,'persistent':{'candidatePivot':1,'swingHighPriceArray':[2],'otherPrivateField':'exclude'}}})
                c.execute('INSERT INTO feature_engine_state VALUES (?,?,?,?)',('ENAUSDT','15m',2700000,state))
            before=[p.read_bytes() for p in (feature,raw)]
            result=export.collect(root,'ENAUSDT','15m',2,data_dir=root)
            self.assertEqual(result['summary']['candles'],2)
            self.assertEqual(result['summary']['event_rows'],dict(missing=1,empty=1,nonempty=0,invalid=0))
            self.assertNotIn('secret_other_column',result['fields'])
            saved=result['metadata']['feature_engine_state'][0]['state']['state']['persistent']
            self.assertEqual(saved,dict(candidatePivot=1,swingHighPriceArray=[2]))
            self.assertEqual(before,[p.read_bytes() for p in (feature,raw)])
    def test_missing_sources_are_not_created(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            with self.assertRaisesRegex(ValueError,'not found'):export.collect(root,'ENAUSDT','15m',data_dir=root)
            self.assertEqual(list(root.iterdir()),[])
