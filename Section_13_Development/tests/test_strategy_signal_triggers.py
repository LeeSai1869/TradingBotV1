"""Trigger/Activate latches, missing history and the supplied lagged rule."""
import copy
import unittest
from test_strategy_analyzer import source,config
from Section_8_Decision_Engine import strategy_analyzer as a, strategy_stages

class SignalTriggers(unittest.TestCase):
    def staged(self,activation_at=2):
        p=source()
        for i,row in enumerate(p['candles']):row['features'].update(buy=int(i==0),rsi=50 if i==activation_at else 10)
        c=config();c['branches'][0]['when']={'all':[
            dict(field='feature.buy',op='eq',value=1,stage='trigger'),
            dict(field='feature.rsi',op='gte',value=40,stage='activate')]}
        return p,c
    def test_unmarked_configs_retain_ordinary_close_matching(self):
        p=source();c=config();old=a.analyze(p,c)
        for branch in c['branches']:branch['when']['stage']='activate'
        new=a.analyze(p,c)
        self.assertEqual(old['signals'],new['signals']);self.assertEqual(old['trades'],new['trades'])
    def test_trigger_latches_and_later_activation_does_not_retest_trigger(self):
        p,c=self.staged();r=a.analyze(p,c)
        signal=r['signals'][0]
        self.assertEqual(signal['candle_open_time'],p['candles'][2]['open_time'])
        self.assertEqual(signal['trigger_known_time'],p['candles'][0]['close_time']+1)
        self.assertEqual(signal['trigger_inputs']['feature.buy@lag0']['value'],1)
        self.assertEqual(signal['inputs']['feature.buy@lag0']['value'],0)
        self.assertEqual(r['branch_diagnostics']['buy']['setups_armed'],1)
    def test_setup_has_no_automatic_expiry(self):
        p,c=self.staged(activation_at=6);r=a.analyze(p,c)
        self.assertEqual(r['signals'][0]['candle_open_time'],p['candles'][6]['open_time'])
        self.assertEqual(r['signals'][0]['trigger_known_time'],p['candles'][0]['close_time']+1)
    def test_unknown_activation_keeps_setup_pending(self):
        p,c=self.staged();p['candles'][1]['features']['rsi']=None
        r=a.analyze(p,c);self.assertEqual(r['signals'][0]['candle_open_time'],p['candles'][2]['open_time'])
    def test_gap_resets_setup_and_cannot_activate_an_unobserved_trigger(self):
        p,c=self.staged();p['candles'].pop(1);r=a.analyze(p,c)
        self.assertFalse(r['signals']);self.assertTrue(any(e['type']=='RESET' for e in r['setup_events']))
    def test_pending_setup_is_reported_without_inventing_a_signal(self):
        p,c=self.staged(activation_at=99);r=a.analyze(p,c)
        self.assertFalse(r['signals']);self.assertEqual(len(r['pending_setups']),1)
        self.assertEqual(r['pending_setups'][0]['branch_id'],'buy')
    def test_activation_timing_is_explicit(self):
        p,c=self.staged(activation_at=0)
        self.assertEqual(a.analyze(p,c)['signals'][0]['candle_open_time'],0)
        c['branches'][0]['activation_timing']='later'
        self.assertFalse(a.analyze(p,c)['signals'])
    def test_waiting_evidence_accounts_for_every_waiting_evaluation(self):
        p,c=self.staged();p['candles'][1]['features']['rsi']=None
        r=a.analyze(p,c);waits=r['waiting_evaluations']
        self.assertEqual(len(waits),r['branch_diagnostics']['buy']['waiting_activation'])
        self.assertEqual([w['candle_open_time'] for w in waits],[0,p['candles'][1]['open_time']])
        self.assertEqual(waits[0]['reason'],'ACTIVATION_FALSE')
        self.assertEqual(waits[0]['conditions'][0]['value'],10)
        self.assertEqual(waits[0]['conditions'][0]['other_value'],40)
        self.assertEqual(waits[0]['conditions'][0]['result'],'FAIL')
        self.assertEqual(waits[1]['reason'],'ACTIVATION_UNKNOWN')
        self.assertEqual(waits[1]['conditions'][0]['result'],'UNKNOWN')
        self.assertTrue(waits[1]['conditions'][0]['missing_reason'])
        self.assertEqual(waits[1]['trigger_known_time'],p['candles'][0]['close_time']+1)

    def test_later_only_wait_explains_timing_even_if_conditions_pass(self):
        p,c=self.staged(activation_at=0);c['branches'][0]['activation_timing']='later'
        first=a.analyze(p,c)['waiting_evaluations'][0]
        self.assertEqual(first['reason'],'LATER_CLOSE_REQUIRED')
        self.assertEqual(first['conditions'][0]['result'],'PASS')

    def test_all_trigger_conditions_must_match_their_group(self):
        p,c=self.staged();c['branches'][0]['when']['all'].insert(1,dict(field='feature.rsi',op='gt',value=100,stage='trigger'))
        self.assertFalse(a.analyze(p,c)['signals'])
    def test_trigger_only_branch_and_invalid_roles_are_rejected(self):
        c=config();c['branches'][0]['when']['stage']='trigger'
        with self.assertRaisesRegex(ValueError,'Activate'):a.validate_config(c)
        c['branches'][0]['when']['stage']='other'
        with self.assertRaisesRegex(ValueError,'Condition role'):a.validate_config(c)
    def test_logical_groups_are_projected_within_each_stage(self):
        p,c=self.staged();c['branches'][0]['when']={'any':c['branches'][0]['when']['all']}
        r=a.analyze(p,c);self.assertEqual(r['signals'][0]['candle_open_time'],p['candles'][2]['open_time'])

    def test_supplied_di_rsi_rule_compares_both_lagged_operands(self):
        p=source()
        for i,(minus,plus,rsi) in enumerate(((55,10,20),(65,10,15),(60,11,18))):
            p['candles'][i]['features'].update(di_minus=minus,di_plus=plus,rsi=rsi)
        def literal(field,op,value,lag=0):return dict(field=field,op=op,value=value,lag=lag)
        def compare(left,right,lag=0,other_lag=0):return dict(field=left,op='gt',other_field=right,lag=lag,other_lag=other_lag)
        minus='di.di_minus';plus='di.di_plus';spread='di.abs_spread';rsi='feature.rsi'
        rule={'all':[
            literal(minus,'gte',50,1),compare(minus,spread,2,2),compare(spread,plus,2,2),
            compare(minus,spread,1,1),compare(spread,plus,1,1),compare(minus,spread),compare(spread,plus),
            literal(spread,'gte',40,1),literal(rsi,'lte',20,1),compare(rsi,rsi,2,1),compare(rsi,rsi,0,1),
            compare(minus,minus,1,2),compare(minus,minus,1,0),compare(spread,spread,1,2),compare(spread,spread,1,0)]}
        c=config();c['branches'][0]['when']=rule;a.validate_config(c)
        missing=set();self.assertIs(a.Memory(p).evaluate(rule,2,missing),True);self.assertFalse(missing)
        p['candles'][1]['features']['rsi']=25
        self.assertIs(a.Memory(p).evaluate(rule,2,set()),False)

    def test_staged_trailing_exit_uses_remembered_setup_with_original_inputs(self):
        from test_strategy_trailing import source as trailing_source,config as trailing_config,branch
        p=trailing_source([(100,100.1,99.9,100),(100,102,99.8,101.8),(101.8,103,101.4,102)],plus=[55,55,10])
        exit_rule=branch({'all':[dict(field='di.di_plus',op='gt',value=50,stage='trigger'),dict(field='price.close',op='available',stage='activate')]})
        r=a.analyze(p,trailing_config(sell=exit_rule))
        signal=r['signals'][-1]
        self.assertEqual(signal['reason'],'TRAILING_STOP')
        self.assertEqual(signal['trigger_known_time'],p['candles'][1]['close_time']+1)
        self.assertEqual(signal['trigger_inputs']['di.di_plus@lag0']['value'],55)


class BlockedInputReport(__import__('unittest').TestCase):
    def test_all_unknown_buy_is_blocked_but_valid_no_match_is_completed(self):
        from test_strategy_analyzer import source, config
        from Section_8_Decision_Engine import strategy_analyzer as analyzer
        data=source()
        for row in data['candles']:row['feature_valid']=False
        report=analyzer.analyze(data,config())
        self.assertEqual(report['test_status'],'BLOCKED_INPUTS')
        self.assertEqual(report['branch_diagnostics']['buy']['unknown'],len(data['candles']))
        for row in data['candles']:
            row['feature_valid']=True
            row['features']['buy']=0
        self.assertEqual(analyzer.analyze(data,config())['test_status'],'COMPLETED')
