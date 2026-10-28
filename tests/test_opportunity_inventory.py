"""Stored lifetime projection is as-of, bounded and honest about missing data."""
import json
import sqlite3
import unittest
from unittest.mock import patch
from Section_1_Global_Core.opportunity_inventory import Inventory
from Section_1_Global_Core.memory_storage.Storage.opportunity_inventory import read_seed,COLUMNS
from Section_1_Global_Core.analysis import annotate


def candle(i,close=100):
    return dict(open_time=i*60000,close_time=(i+1)*60000-1,open=close,high=close+.1,low=close-.1,close=close)


def fields(**extra):
    return dict(formula_version=3,atr=1,sr_zone_events='[]',ob_zone_events='[]',qualified_bull_fvg=False,qualified_bear_fvg=False,**extra)


class InventoryTests(unittest.TestCase):
    def test_non_nearest_stored_zone_enters_decision_but_later_birth_cannot(self):
        events=[dict(id='first',side='support',low=94,high=94.2,before=None),
                dict(id='second',side='support',low=96,high=96.2,before=None)]
        first=fields();first['sr_zone_events']=json.dumps(events)
        later=fields();later['sr_zone_events']=json.dumps([dict(id='later',side='support',low=98,high=98.2,before=None)])
        rows=[dict(interval='4h',open_time=i*60000,client=candle(i),features=f,momentum={'signal_type':'BUY' if i==0 else None}) for i,f in enumerate((first,later))]
        annotate(rows,now_ms=200000)
        areas=rows[-1]['opportunity']['areas']['support']
        self.assertEqual([a['low'] for a in areas],[96,94])
        self.assertEqual(rows[0]['opportunity'],rows[-1]['opportunity'])
        self.assertTrue(all(c['timeframe']=='4h' for a in areas for c in a['contributors']))

    def test_fvg_failure_and_gaps_do_not_leave_stale_levels(self):
        inventory=Inventory();f=fields(bull_fvg_low=94,bull_fvg_high=94.2);f['qualified_bull_fvg']=True
        inventory.advance(candle(0),f);self.assertEqual(len(inventory.zones),1)
        invalid=candle(1,94);invalid.update(low=93,high=95,close=93.5)
        inventory.advance(invalid,fields());self.assertEqual(inventory.zones,{})
        inventory.advance(candle(2),f);inventory.advance(candle(4),fields())
        self.assertEqual(inventory.zones,{})
        self.assertIn('gap',inventory.coverage['fvg'])

    def test_checkpoint_is_reversed_and_future_birth_is_not_backdated(self):
        raw=sqlite3.connect(':memory:');derived=sqlite3.connect(':memory:')
        self.addCleanup(raw.close);self.addCleanup(derived.close)
        raw.execute('CREATE TABLE klines(symbol,interval,open_time,high,low,close,close_time)')
        derived.execute('CREATE TABLE features(symbol,interval,open_time,formula_version,'+','.join(COLUMNS)+')')
        derived.execute('CREATE TABLE feature_engine_state(symbol,interval,last_open_time,state)')
        original=dict(side='support',low=94,high=94.2,institutional=False)
        upgraded={**original,'institutional':True};future=dict(side='support',low=96,high=96.2,institutional=False)
        changes=[[],[dict(id='old',**upgraded,before=original)],[dict(id='future',**future,before=None)]]
        for i,events in enumerate(changes):
            c=candle(i);raw.execute('INSERT INTO klines VALUES(?,?,?,?,?,?,?)',('X','4h',c['open_time'],c['high'],c['low'],c['close'],c['close_time']))
            values=['X','4h',c['open_time'],3,json.dumps(events),'[]',0,0,None,None,None,None]
            derived.execute('INSERT INTO features VALUES('+','.join('?' for _ in values)+')',values)
        state=dict(version=3,epoch=[0,0],state=dict(persistent=dict(srDisplayPrevious=dict(old=upgraded,future=future),obDisplayZones={})))
        derived.execute('INSERT INTO feature_engine_state VALUES(?,?,?,?)',('X','4h',120000,json.dumps(state)))
        seed=read_seed(raw,derived,'X','4h',60000,(0,0))
        self.assertEqual(set(seed['zones']),{'sr:old'})
        self.assertFalse(seed['zones']['sr:old']['institutional'])
        self.assertEqual(seed['coverage']['sr'],'checkpoint reversed to reference')
        # Masked replay output must block use of the newer checkpoint.
        derived.execute('CREATE TABLE feature_replay_jobs(symbol,interval,last_time,target,columns)')
        derived.execute('INSERT INTO feature_replay_jobs VALUES(?,?,?,?,?)',('X','4h',0,120000,'["sr_zone_events"]'))
        masked=read_seed(raw,derived,'X','4h',60000,(0,0))
        self.assertNotIn('sr:future',masked['zones'])
        self.assertNotIn('checkpoint',masked['coverage']['sr'])

    def test_bounded_history_does_not_claim_complete_coverage(self):
        raw=sqlite3.connect(':memory:');derived=sqlite3.connect(':memory:')
        self.addCleanup(raw.close);self.addCleanup(derived.close)
        raw.execute('CREATE TABLE klines(symbol,interval,open_time,high,low,close,close_time)')
        derived.execute('CREATE TABLE features(symbol,interval,open_time,formula_version,'+','.join(COLUMNS)+')')
        for i in range(3):
            c=candle(i);raw.execute('INSERT INTO klines VALUES(?,?,?,?,?,?,?)',('X','1m',c['open_time'],c['high'],c['low'],c['close'],c['close_time']))
            values=['X','1m',c['open_time'],3,'[]','[]',0,0,None,None,None,None]
            derived.execute('INSERT INTO features VALUES('+','.join('?' for _ in values)+')',values)
        with patch('Section_1_Global_Core.memory_storage.Storage.opportunity_inventory.LIMIT',2):
            seed=read_seed(raw,derived,'X','1m',180000,(0,0))
        self.assertEqual(seed['coverage']['fvg'],'partial: bounded history')
