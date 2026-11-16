from contextlib import closing
from copy import deepcopy
from pathlib import Path
import tempfile
import sqlite3
import unittest
from unittest.mock import patch
from Section_1_Global_Core.memory_storage.Storage import features_store as store
from Section_4_Features.execution import components,selective
from Section_4_Features.execution.engine import Engine
from Section_4_Features.execution.derived_features import trend_values
from Section_4_Features.features import trend


class TrendStorage(unittest.TestCase):
    def test_online_cleanup_preserves_unreconstructable_legacy_values(self):
        from retire_trend_storage import clear_batch
        with closing(sqlite3.connect(':memory:')) as c:
            fields=list(store.FORMULA_COLUMNS)
            c.execute('CREATE TABLE features(formula_version INTEGER,c REAL,ema7 REAL,ema25 REAL,ema50 REAL,ema100 REAL,'+','.join(f+' REAL' for f in fields)+')')
            row=dict(c=10.,ema7=7.,ema25=5.,ema50=3.,ema100=2.)
            values=trend_values(row)
            with c:
                c.execute('INSERT INTO features VALUES ('+','.join('?' for _ in range(13))+')',[3,10.,7.,5.,3.,2.,*[values[f] for f in fields]])
                c.execute('INSERT INTO features(formula_version,ema_compression) VALUES (1,999)')
            result=clear_batch(c,0)
            self.assertEqual(result['values_cleared'],7)
            self.assertEqual(result['legacy_values_retained'],1)
            self.assertEqual(c.execute('SELECT '+','.join(fields)+' FROM features WHERE rowid=1').fetchone(),(None,)*7)
            self.assertEqual(c.execute('SELECT ema_compression FROM features WHERE rowid=2').fetchone()[0],999)
            projected=c.execute('SELECT '+','.join(store.read_expression(f) for f in fields)+' FROM features f WHERE rowid=1').fetchone()
            self.assertEqual(dict(zip(fields,projected)),values)
            with c:c.execute('INSERT INTO features(formula_version,ema_compression) VALUES (3,999)')
            with self.assertRaisesRegex(ValueError,'formula mismatch'):clear_batch(c,2)
            self.assertEqual(c.execute('SELECT ema_compression FROM features WHERE rowid=3').fetchone()[0],999)

    def test_sql_and_python_formulas_match_including_missing_and_zero(self):
        with tempfile.TemporaryDirectory() as d,patch.object(store,'DB_PATH',Path(d)/'features.db'),closing(store.open_db()) as c:
            self.assertTrue(set(store.FORMULA_COLUMNS).isdisjoint(store.storage_columns(c)))
            for i,price in enumerate((100.,0.,None)):
                row=dict(symbol='BTCUSDT',interval='1m',open_time=i,formula_version=3,c=price,ema7=101.,ema25=99.,ema50=98.,ema100=97.)
                store.insert_rows(c,[row]);expected=trend_values(row)
                fields=list(store.FORMULA_COLUMNS)
                actual=c.execute('SELECT '+','.join(store.read_expression(f) for f in fields)+' FROM features f WHERE open_time=?',(i,)).fetchone()
                self.assertEqual(dict(zip(fields,actual)),expected)
                self.assertEqual({f:store.read_row(c,'BTCUSDT','1m',i)[f] for f in fields},expected)

    def test_selective_transition_ignores_poisoned_gap_and_compression_memory(self):
        engine=Engine('BTCUSDT','1m')
        for i in range(40):
            close=100+(i%7)*.3
            engine.step(dict(open_time=i*60000,close_time=(i+1)*60000-1,open=close-.1,high=close+1,low=close-1,close=close,volume=10.))
        context=deepcopy(engine.context)
        bar=dict(open_time=40*60000,close_time=41*60000-1,open=101.,high=102.,low=100.,close=101.5,volume=10.)
        expected=engine.step(bar);stored=dict(expected)
        for field in store.FORMULA_COLUMNS:stored[field]=-1e99
        catalog=components.catalog()
        changed={u.id for u in catalog.units if u.module.endswith('.transition')}
        plan=catalog.plan(changed)
        self.assertIn('emaCompression',plan.state_writes)
        partial=selective.PartialEngine('BTCUSDT','1m',plan,context.parameters,context)
        with patch.object(trend,'calculate_ema',side_effect=AssertionError('Must reuse EMA inputs, not replay recursive EMA')):
            result=partial.step(bar,stored)
        self.assertEqual(partial.context['emaCompression'],expected['ema_compression'])
        self.assertEqual(result['transition_state'],expected['transition_state'])


if __name__=='__main__':unittest.main()
