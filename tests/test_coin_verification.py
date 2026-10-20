"""Read-only historical candle comparison, never comparing old ETH to current price."""
import sqlite3
from pathlib import Path
import tempfile
import unittest
from urllib.parse import parse_qs,urlparse
from check_coin import verify_latest


class CoinVerificationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'candles.db'
        with sqlite3.connect(self.path) as conn:
            conn.execute('CREATE TABLE klines(symbol,interval,open_time,open,high,low,close,volume,close_time)')
            conn.execute('INSERT INTO klines VALUES(?,?,?,?,?,?,?,?,?)',('ETHUSDT','1h',1500000000000,140,145,139,143,25,1500003599999))
        self.remote=[1500000000000,'140','145','139','143','25',1500003599999]

    def test_old_low_price_is_checked_against_same_symbol_interval_and_time(self):
        before=self.path.read_bytes()
        def fetch(request):
            query=parse_qs(urlparse(request.full_url).query)
            self.assertEqual(query['symbol'],['ETHUSDT']);self.assertEqual(query['interval'],['1h'])
            self.assertEqual(query['startTime'],['1500000000000']);self.assertEqual(query['limit'],['1'])
            return [self.remote]
        status,detail=verify_latest('ETHUSDT','1h',self.path,fetch)
        self.assertEqual(status,'MATCH');self.assertIn('local close=143',detail)
        self.assertEqual(before,self.path.read_bytes())

    def test_wrong_price_or_wrong_timestamp_is_not_accepted(self):
        self.remote[4]='300'
        self.assertEqual(verify_latest('ETHUSDT','1h',self.path,lambda _:[self.remote])[0],'MISMATCH')
        self.remote[0]+=3600000
        self.assertEqual(verify_latest('ETHUSDT','1h',self.path,lambda _:[self.remote])[0],'UNVERIFIED')

    def test_missing_pair_is_not_reported_as_matching(self):
        self.assertEqual(verify_latest('ETHUSDT','1m',self.path,lambda _:[])[0],'NO DATA')
