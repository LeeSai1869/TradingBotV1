"""Endpoint scheduling, calendar boundaries and request deadlines without network."""
from datetime import datetime,timezone
import sqlite3
import unittest
from unittest.mock import patch,MagicMock
from Section_1_Global_Core.memory_storage.market_data import update_klines as updater

class CurrentCandles(unittest.TestCase):
    def setUp(self):
        self.conn=sqlite3.connect(':memory:');self.addCleanup(self.conn.close)
        self.conn.execute('CREATE TABLE klines(symbol TEXT,interval TEXT,open_time INTEGER,close_time INTEGER,PRIMARY KEY(symbol,interval,open_time))')
    def test_only_fully_closed_next_candle_is_due(self):
        self.conn.execute('INSERT INTO klines VALUES (?,?,?,?)',('BTC','5m',0,299999))
        self.assertFalse(updater._current_due(self.conn,'BTC','5m',599999))
        self.assertTrue(updater._current_due(self.conn,'BTC','5m',600000))
        self.assertFalse(updater._current_due(self.conn,'NEW','5m',600000))
    def test_monthly_boundary_uses_calendar_in_leap_year(self):
        ms=lambda month:int(datetime(2024,month,1,tzinfo=timezone.utc).timestamp()*1000)
        self.conn.execute('INSERT INTO klines VALUES (?,?,?,?)',('BTC','1M',ms(1),ms(2)-1))
        self.assertFalse(updater._current_due(self.conn,'BTC','1M',ms(3)-1))
        self.assertTrue(updater._current_due(self.conn,'BTC','1M',ms(3)))
    def test_each_request_rechecks_remaining_budget_and_restores_context(self):
        clock=[10.]
        response=MagicMock();response.__enter__.return_value.read.return_value=b'[]'
        def update(*args,**kwargs):
            updater._fetch('BTC','5m',None)
            clock[0]=10.4
            updater._fetch('BTC','5m',None)
            clock[0]=10.6
            with self.assertRaises(TimeoutError):updater._fetch('BTC','5m',None)
            return 1
        with patch.object(updater.time,'monotonic',side_effect=lambda:clock[0]),patch.object(updater,'update_one',side_effect=update),patch.object(updater.urllib.request,'urlopen',return_value=response) as network:
            self.assertEqual(updater._bounded_update('BTC','5m',self.conn,10.5),1)
            self.assertEqual(network.call_count,2)
            self.assertAlmostEqual(network.call_args_list[0].kwargs['timeout'],.5)
            self.assertAlmostEqual(network.call_args_list[1].kwargs['timeout'],.1)
        self.assertEqual(updater._REQUEST_TIMEOUT.get(),15)
        self.assertIsNone(updater._REQUEST_DEADLINE.get())
