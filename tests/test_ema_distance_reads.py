"""Parity with live EMA structure, including nulls, ties and signed units."""
from contextlib import closing,redirect_stdout
import io
import json
from pathlib import Path
import random
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from Section_4_Features.execution import runtime as rt
from Section_4_Features.execution.ema_distances import FIELDS,INPUTS,values
from Section_4_Features.features import ema_structure
from Section_1_Global_Core.memory_storage.Storage import features_store as s


class Context(dict):
    def previous(self,key,index):return None
    def ta(self,*args):return rt.NA


def live(row):
    context=Context({key:row.get(key) for key in INPUTS})
    ema_structure.update(context)
    return rt.clean({field:context[name] for field,name in FIELDS.items()})


class EMADistanceReads(unittest.TestCase):
    def setUp(self):
        self.root=Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.enterContext(patch.object(s,'DB_PATH',self.root/'features.db'))
        self.conn=self.enterContext(closing(s.open_db()))

    def row(self,price=100.,emas=(95.,105.,90.,110.,85.,120.)):
        return dict(c=price,**dict(zip(INPUTS[1:],emas)))

    def insert(self,row,time=0,version=3,outputs=None):
        stored=dict(symbol='BTCUSDT',interval='1m',open_time=time,
                    formula_version=version,**row,**(outputs or live(row)))
        s.insert_rows(self.conn,[stored])
        return stored

    def projected(self,time=0):
        row=self.conn.execute('SELECT '+','.join(s.read_expression(f) for f in FIELDS)+
            ' FROM features f WHERE open_time=?',(time,)).fetchone()
        return dict(zip(FIELDS,row))

    def test_exact_live_and_sql_parity_across_edge_cases(self):
        cases=[self.row(),self.row(100.,(100.,)*6),self.row(0.),self.row(None),
               self.row(-100.),self.row(100.,(None,)*6),
               self.row(100.,(105.,105.,None,95.,0.,95.)),
               self.row(50.,(None,None,None,None,0.,None)),
               self.row(float('inf')),
               self.row(1.7e308,(-1e308,-.9e308,None,None,None,None)),
               self.row(100.,(float('inf'),)*6),
               self.row(float('nan'))]
        for i,row in enumerate(cases):
            with self.subTest(row=row):
                expected=live(row)
                self.assertEqual(values(row),expected)
                self.insert(row,i)
                self.assertEqual(self.projected(i),expected)

    def test_randomized_live_python_sql_parity(self):
        rng=random.Random(42)
        for i in range(250):
            price=rng.uniform(-300,300)
            emas=tuple(None if rng.random()<.2 else rng.uniform(-300,300) for _ in range(6))
            row=self.row(price,emas)
            self.insert(row,i)
            self.assertEqual(values(row),live(row))
            self.assertEqual(self.projected(i),live(row),i)

    def test_selection_sides_equality_and_percentage_units(self):
        actual=values(self.row())
        self.assertEqual(actual['nearest_buy_ema'],105.)
        self.assertEqual(actual['nearest_sell_ema'],95.)
        self.assertEqual(actual['nearest_buy_ema_distance_pct'],5.)
        self.assertEqual(actual['ema50_distance_pct'],10.)
        self.assertIsNone(values(self.row(100.,(100.,)*6))['nearest_buy_ema'])
        self.assertEqual(values(self.row(100.,(95.,105.,90.,110.,0.,120.)))['ema50_200_gap_pct'],0.)

    def test_normal_range_and_replay_ignore_poisoned_derivatives(self):
        row=self.row();self.insert(row,outputs=dict.fromkeys(FIELDS,999.))
        expected=live(row)
        normal=s.read_row(self.conn,'BTCUSDT','1m',0)
        ranged=s.read_range(self.conn,'BTCUSDT','1m',0,1)[0]
        replay=s.read_replay_inputs(self.conn,'BTCUSDT','1m',0,1,FIELDS)[0]
        for result in (normal,ranged,replay):
            self.assertEqual({f:result[f] for f in FIELDS},expected)
        # Read-only phase: storage policy and physical values are unchanged.
        self.assertTrue(set(FIELDS)<=set(s.storage_columns(self.conn)))
        self.assertEqual(tuple(self.conn.execute('SELECT '+','.join(FIELDS)+' FROM features').fetchone()),(999.,)*10)

    def test_legacy_versions_preserve_nulls_as_well_as_populated_values(self):
        for version in (1,2):
            for offset,outputs in enumerate((dict.fromkeys(FIELDS,777.),dict.fromkeys(FIELDS))):
                time=version*10+offset
                self.insert(self.row(),time,version,outputs)
                normal=s.read_row(self.conn,'BTCUSDT','1m',time)
                self.assertEqual({f:normal[f] for f in FIELDS},outputs)
                self.assertEqual(self.projected(time),outputs)

    def test_real_engine_exports_match_formula_reads_without_recalculating_emas(self):
        from Section_4_Features.execution.engine import Engine
        engine=Engine('BTCUSDT','1m')
        outputs=[]
        for i in range(330):
            price=100+(i%17)*.3
            outputs.append(engine.step(dict(open_time=i*60000,close_time=(i+1)*60000-1,
                open=price,high=price+1,low=price-1,close=price+.1,volume=10.)))
        s.insert_rows(self.conn,outputs)
        with patch('Section_4_Features.features.trend.calculate_ema',side_effect=AssertionError('Reuse retained EMAs')):
            actual=s.read_range(self.conn,'BTCUSDT','1m',0,330*60000)
        for expected,row in zip(outputs,actual):
            self.assertEqual({f:row[f] for f in FIELDS},{f:expected[f] for f in FIELDS})

    def test_bounded_and_full_audits_are_read_only_and_report_mismatches(self):
        import check_ema_distance_readers as check
        self.insert(self.row(),0);self.insert(self.row(90.),60000)
        self.insert(self.row(),120000,version=1,outputs=dict.fromkeys(FIELDS,777.))
        for args in ([],['--full','--batch-size','1']):
            output=io.StringIO()
            with patch('sys.argv',['check_ema_distance_readers.py',*args]),redirect_stdout(output):check.main()
            report=json.loads(next(line[7:] for line in output.getvalue().splitlines() if line.startswith('FINAL: ')))
            self.assertEqual(report['rows_checked'],2)
            self.assertEqual(report['stored_formula_mismatches'],0)
            self.assertEqual(report['sql_python_mismatches'],0)
        with self.conn:self.conn.execute('UPDATE features SET nearest_buy_ema=999 WHERE open_time=0')
        output=io.StringIO()
        with patch('sys.argv',['check_ema_distance_readers.py']),redirect_stdout(output),self.assertRaises(SystemExit):check.main()
        report=json.loads(next(line[7:] for line in output.getvalue().splitlines() if line.startswith('FINAL: ')))
        self.assertEqual(report['mismatches_by_field'],{'nearest_buy_ema':1})
        self.assertEqual(self.conn.execute('SELECT nearest_buy_ema FROM features WHERE open_time=0').fetchone()[0],999.)


if __name__=='__main__':unittest.main()
