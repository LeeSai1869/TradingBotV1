from copy import deepcopy
import unittest
from unittest.mock import patch
from Section_8_Decision_Engine.sequence import alternate
from Section_8_Decision_Engine.presentation import annotate
from Section_8_Decision_Engine.rules import di_turning_point as rule
from evaluate_strategy import study


def decision(signal):return {'signal_type':signal,'decision_state':signal or 'WAIT','trigger':rule.RULE_ID if signal else None}

def record(i,plus,minus,close,adx):
    return dict(open_time=i*60000,close_time=(i+1)*60000-1,open=close,close=close,adx=adx,di_plus=plus,di_minus=minus,di_spread=abs(plus-minus))


def records():
    # BUY, BUY, SELL, SELL, BUY with WAIT bars between the raw candidates.
    values=[(10,30,99,20),(11,35,100,21),(15,27,101,22),
            (10,30,99,20),(11,35,100,21),(15,27,101,22),
            (30,10,103,20),(35,11,102,21),(27,15,101,22),
            (30,10,103,20),(35,11,102,21),(27,15,101,22),
            (10,30,99,20),(11,35,100,21),(15,27,101,22)]
    return [record(i,*v) for i,v in enumerate(values)]


def bars():
    return [dict(open_time=r['open_time'],time=r['open_time']//1000,
                 client={k:r[k] for k in ('open','close','close_time')},
                 features={**{k:r[k] for k in rule.FIELDS if k!='close'},'formula_version':3}) for r in records()]


class AlternationTests(unittest.TestCase):
    def test_shared_guard_wait_and_missing_data_never_reset_direction(self):
        last=None;accepted=[]
        for candidate in ['BUY',None,'BUY',None,'SELL','SELL','BUY','BUY']:
            result,last=alternate(decision(candidate),last)
            if result['signal_type']:accepted.append(result['signal_type'])
        self.assertEqual(accepted,['BUY','SELL','BUY'])
        self.assertEqual(alternate(decision('SELL'),None)[0]['signal_type'],'SELL')

    def test_chart_and_historical_study_use_same_alternation(self):
        projected=annotate(bars())
        self.assertEqual([b['momentum']['signal_type'] for b in projected if b['momentum']['signal_type']],['BUY','SELL','BUY'])
        self.assertEqual(projected[5]['momentum']['decision_state'],'SUPPRESSED')
        result=study(records(),(1,))
        self.assertEqual((result['buy_signals'],result['sell_signals']),(2,1))

    def test_gap_and_unavailable_rows_do_not_allow_same_side_again(self):
        rows=bars();rows[3]['features']=None
        for b in rows[3:]:b['open_time']+=60000;b['client']['close_time']+=60000
        projected=annotate(rows)
        self.assertEqual([b['momentum']['signal_type'] for b in projected if b.get('momentum') and b['momentum']['signal_type']],['BUY','SELL','BUY'])

    def test_hidden_previous_candidate_seeds_visible_chart_page(self):
        page=deepcopy(bars()[3:6])
        self.assertIsNone(annotate(page,last_signal='BUY')[-1]['momentum']['signal_type'])
        self.assertEqual(annotate(page,last_signal='SELL')[-1]['momentum']['signal_type'],'BUY')
