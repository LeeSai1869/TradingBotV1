import copy
import unittest
from Section_8_Decision_Engine.btc_research import simulate
from Section_1_Global_Core import btc_strategy_history

def bar(n,o=100,h=100.2,l=99.8,c=100,plus=20,minus=30,**features):
    return dict(open_time=n*300000,close_time=(n+1)*300000-1,open=o,high=h,low=l,close=c,features=dict(di_plus=plus,di_minus=minus,atr=.2,**features))

def setup():
    return [bar(0,candidate_pivot=-1,candidate_pivot_low_price=99.8,candidate_pivot_low_time=0),bar(1,h=100.5,c=100.4,plus=25,minus=25)]

class BTCVisualStrategy(unittest.TestCase):
    def test_next_open_entry_stop_gap_and_costs(self):
        rows=setup()+[bar(2,o=100.4,h=100.5,l=100.3,c=100.4),bar(3,o=99,h=99.2,l=98.9,c=99)]
        original=copy.deepcopy(rows)
        result=simulate(rows);trade=result['trades'][0]
        self.assertEqual(trade['entry_time'],600000)
        self.assertAlmostEqual(trade['entry'],100.4*1.0002)
        self.assertAlmostEqual(trade['exit'],99*.9998)
        self.assertLess(trade['net_pct'],-.5) # gaps are not falsely capped
        self.assertEqual(trade['status'],'CLOSED')
        self.assertEqual(rows,original)

    def test_trail_not_retroactive_and_profit_not_fixed_target(self):
        rows=setup()+[bar(2,o=100.4,h=102,l=100.3,c=101.8)]
        first=simulate(rows);self.assertEqual(first['trades'][0]['status'],'OPEN')
        self.assertEqual(first['levels'][0]['stop'],first['trades'][0]['hard_stop'])
        later=simulate(rows+[bar(3,o=101.8,h=102,l=101.6,c=101.9)])
        self.assertEqual(later['trades'][0]['status'],'CLOSED')
        self.assertEqual(later['trades'][0]['reason'],'Trailing stop')
        self.assertEqual(first['levels'],later['levels'][:1])

    def test_di_without_price_confirmation_does_not_buy(self):
        result=simulate(setup()[:1]+[bar(1,plus=40,minus=10)])
        self.assertEqual(result['trades'],[])

    def test_gap_censors_position_without_invented_fill(self):
        result=simulate(setup()+[bar(2,o=100.4,h=100.5,l=100.3,c=100.4),bar(4)])
        trade=result['trades'][0]
        self.assertEqual(trade['status'],'CENSORED');self.assertNotIn('net_pct',trade)
        self.assertEqual(result['gaps'],1)

    def test_only_requested_symbol_timeframes(self):
        for symbol,tf in [('ETHUSDT','5m'),('BTCUSDT','1m'),('BTCUSDT','4h')]:
            with self.assertRaises(ValueError):btc_strategy_history.history(symbol,tf)
