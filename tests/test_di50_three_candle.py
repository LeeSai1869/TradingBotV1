"""Three-candle DI rules, threshold timing, missing context and fixed targets."""
import copy
import unittest

from research_reports.DI50_15m_three_candle_reversal import study
from Section_8_Decision_Engine import strategy_analyzer as a
from test_strategy_trailing import source as prices,config


def fixture(plus=(8,5,6,7),minus=(40,60,55,50)):
    p=prices([(100,100.1,99.9,100)]*4,plus=plus)
    for i,row in enumerate(p['candles']):
        row['features']['di_minus']=minus[i]
        row['context']={name:dict(candle_open_time=row['open_time'],candle_close_time=row['close_time'],as_of=row['close_time']+1,
                                  data_quality='VALID',classification=dict(direction='BEARISH')) for name in ('TREND','REGIME')}
    return p


class ThreeCandle(unittest.TestCase):
    def test_peak_and_current_thresholds_are_distinct(self):
        p=fixture();groups,_,counts,_=study.setups(p['candles'])
        self.assertEqual(groups['peak_thresholds_with_plus'],[2])
        self.assertEqual(groups['current_thresholds_with_plus'],[])
        m=a.Memory(p)
        self.assertTrue(m.evaluate(study.configuration()['branches'][0]['when'],2,set()))
        self.assertFalse(m.evaluate(study.configuration('current_thresholds_with_plus')['branches'][0]['when'],2,set()))

    def test_plus_must_form_reverse_trough_not_merely_rise(self):
        p=fixture(plus=(3,5,6,7));groups,*_=study.setups(p['candles'])
        self.assertEqual(groups['peak_thresholds_with_plus'],[])
        self.assertEqual(groups['peak_thresholds_without_plus'],[2])

    def test_plateaus_missing_history_and_non_bearish_trend_do_not_buy(self):
        for plus in [(5,5,6,7),(8,5,5,7)]:
            self.assertFalse(study.setups(fixture(plus=plus)['candles'])[0]['peak_thresholds_with_plus'])
        p=fixture();p['candles'][2]['context']['TREND']['data_quality']='UNAVAILABLE'
        self.assertFalse(study.setups(p['candles'])[0]['peak_thresholds_with_plus'])
        p=fixture();p['candles'][2]['context']['TREND']['classification']['direction']='BULLISH'
        self.assertFalse(study.setups(p['candles'])[0]['peak_thresholds_with_plus'])

    def test_trend_and_regime_have_distinct_roles(self):
        p=fixture();p['candles'][2]['context']['REGIME']['classification']['direction']='NEUTRAL'
        groups,_,counts,_=study.setups(p['candles'])
        self.assertEqual(counts['peak_thresholds_with_plus']['bearish_trend_setups'],1)
        self.assertEqual(counts['peak_thresholds_with_plus']['neutral_or_unknown_exit_regime'],1)
        self.assertFalse(groups['peak_thresholds_with_plus'])

    def test_fixed_target_is_net_of_costs(self):
        p=prices([(100,100.1,99.9,100),(100,102,99.8,101.5)])
        c=config(fee=4,slip=2);c['branches'][1]=dict(id='profit',side='SELL',action='TAKE_PROFIT',target_profit_pct=1,when=dict(field='price.close',op='available'))
        t=a.analyze(p,c)['trades'][0]
        self.assertEqual(t['exit_reason'],'TAKE_PROFIT');self.assertAlmostEqual(t['net_pct'],1)

    def test_same_bar_target_and_stop_follow_selected_price_path(self):
        p=prices([(100,100.1,99.9,100),(100,102,99,100)])
        c=config();c['branches'][1]=dict(id='profit',side='SELL',action='TAKE_PROFIT',target_profit_pct=1,when=dict(field='price.close',op='available'))
        self.assertEqual(a.analyze(p,c)['trades'][0]['exit_reason'],'HARD_STOP')
        c['execution']['intrabar_path']='high_first'
        self.assertEqual(a.analyze(p,c)['trades'][0]['exit_reason'],'TAKE_PROFIT')

    def test_new_target_condition_cannot_see_an_earlier_high(self):
        p=prices([(100,100.1,99.9,100),(100,102,99.8,100.5),(100.5,100.8,100.3,100.5)],plus=[10,55,55])
        c=config();c['branches'][1]=dict(id='profit',side='SELL',action='TAKE_PROFIT',target_profit_pct=1,when=dict(field='di.di_plus',op='gt',value=50))
        self.assertEqual(a.analyze(p,c)['trades'][0]['status'],'OPEN')

    def test_previous_spread_uses_stored_previous_measurements(self):
        memory=a.Memory(fixture())
        self.assertEqual(memory.value(2,'di.abs_spread',1),(55,None))
        self.assertEqual(memory.value(2,'di.di_minus',2),(40,None))

    def test_literal_non_decrease_is_a_separate_rule(self):
        p=fixture(plus=(5,5,5,7));groups,*_=study.setups(p['candles'])
        self.assertFalse(groups['peak_thresholds_with_plus'])
        self.assertEqual(groups['peak_thresholds_plus_non_decreasing'],[2])
        expression=study.configuration('peak_thresholds_plus_non_decreasing')['branches'][0]['when']
        self.assertTrue(a.Memory(p).evaluate(expression,2,set()))

    def test_research_and_workspace_execute_the_same_fixed_target(self):
        p=fixture();p['candles'][3].update(open=100,high=102,low=99.8,close=101.6)
        class Execution:
            until=p['candles'][-1]['close_time']
            def bars(self,start,tf):
                for row in p['candles']:
                    if row['open_time']>=start:yield [row[k] for k in ('open_time','close_time','open','high','low','close')]
        trace=study.replay_one(p['candles'],2,Execution(),study.Context(p['candles']),study.Policy(),'low_first','15m')
        browser=a.analyze(p,study.configuration())['trades'][0]
        self.assertEqual(trace['reason'],browser['exit_reason'])
        self.assertAlmostEqual(trace['net_pct'],browser['net_pct'])


if __name__=='__main__':unittest.main()
