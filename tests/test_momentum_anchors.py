"""Causal Momentum-only DI anchors; unchanged legacy fields and selective replay."""
import copy
import json
import math
import unittest
from Section_4_Features.features import momentum_anchors as m


def client(i,**kw):
    return dict(symbol='TESTUSDT',interval='1m',open_time=i*60000,close_time=(i+1)*60000-1,
                open=100,high=102,low=98,close=100,volume=10,**kw)


def step(state,i,plus,minus=10,*,parameters=None,confirmed=True,high=(None,None,None),low=(None,None,None),candle=None):
    p={**m.DEFAULTS,**(parameters or {})};m.validate(p);bar=candle or client(i)
    state=m.detect(state,bar,i,plus,minus,confirmed,p['diAnchorReversal'],p['diAnchorConfirmBars'],p['diAnchorConfirmSpacing'],p['diAnchorHistory'],p['diAnchorSourceHistory'])
    state,values=m.link(state,bar,i,confirmed,high,low,2.,f'R{i}',f'S{i}',p)
    return state,values


class MomentumAnchorTests(unittest.TestCase):
    def test_confirms_all_cycles_without_replacing_previous_highs(self):
        state=m.new_state();records=[]
        for i,value in enumerate((20,30,20,25,18,28,17)):
            state,result=step(state,i,value);records+=json.loads(result['di_anchor_events'])
        highs=[e for e in records if e.get('channel')=='di_plus' and e['type']=='di_high']
        self.assertEqual([e['value'] for e in highs],[30,25,28])
        self.assertEqual([e['classification'] for e in highs],[None,'LH','HH'])
        self.assertEqual([e['value'] for e in state['channels']['di_plus']['highs']],[30,25,28])
        self.assertTrue(all(e['confirmed_time']>e['time'] for e in highs))
        self.assertEqual(state['channels']['di_plus']['highs'][0],highs[0])

    def test_qualification_never_changes_geometry_or_blocks_the_next_turn(self):
        state=m.new_state();events=[]
        for i,value in enumerate((30,45,42,20,23)):
            state,result=step(state,i,value,parameters={'diAnchorPlusHighMax':40.})
            events+=json.loads(result['di_anchor_events'])
        high=next(e for e in events if e.get('channel')=='di_plus' and e['type']=='di_high')
        self.assertEqual(high['value'],45);self.assertFalse(high['qualified'])
        self.assertTrue(any(e.get('channel')=='di_plus' and e['type']=='di_low' and e['value']==20 for e in events))
        state=m.new_state()
        for i,value in enumerate((10,12,9)):state,result=step(state,i,value)
        self.assertEqual(result['di_plus_local_high'],12);self.assertFalse(result['di_plus_local_high_qualified'])

    def test_negative_signed_spread_extrema_and_noise_filters(self):
        state=m.new_state();events=[]
        for i,value in enumerate((10,5,8,3,7)):
            state,result=step(state,i,value,minus=20);events+=json.loads(result['di_anchor_events'])
        lows=[e for e in events if e.get('channel')=='di_signed_spread' and e['type']=='di_low']
        self.assertEqual([e['value'] for e in lows],[-15,-17]);self.assertTrue(all(e['qualified'] for e in lows))
        state=m.new_state()
        for i,value in enumerate((20,20.2,20.1,20.3,20.2)):
            state,result=step(state,i,value);self.assertEqual(result['di_anchor_events'],'[]')

    def test_plateaus_use_first_origin_and_delayed_confirmation_keeps_intervening_extreme(self):
        state=m.new_state()
        for i,value in enumerate((20,20,23,23,20)):state,result=step(state,i,value)
        self.assertEqual(result['di_plus_local_high_bar'],2)
        state=m.new_state()
        for i,value in enumerate((30,25,35,30,29)):state,result=step(state,i,value,parameters={'diAnchorConfirmBars':2})
        self.assertEqual(result['di_plus_local_low'],25);self.assertEqual(result['di_plus_local_high'],35)
        self.assertEqual(result['di_plus_local_high_bar'],2);self.assertEqual(result['di_plus_local_high_confirmed_time'],300000)

    def test_unconfirmed_and_duplicate_bars_do_not_mutate_state_or_emit_events(self):
        state=m.new_state()
        for i,value in enumerate((20,30,20)):state,result=step(state,i,value)
        before=copy.deepcopy(state)
        state,preview=step(state,3,50,confirmed=False)
        self.assertEqual(state,before);self.assertEqual(preview['di_anchor_events'],'[]')
        state,duplicate=step(state,2,20)
        self.assertEqual(state,before);self.assertEqual(duplicate['di_anchor_events'],'[]')

    def test_missing_data_or_raw_gap_starts_a_new_segment(self):
        for invalid in (float('nan'),None):
            state=m.new_state()
            for i,value in enumerate((20,30,20)):state,_=step(state,i,value)
            state,result=step(state,3,invalid)
            self.assertFalse(result['di_anchor_continuous']);self.assertIsNone(result['di_plus_local_high'])
        state=m.new_state()
        for i,value in enumerate((20,30,20)):state,_=step(state,i,value)
        state,result=step(state,5,18)
        self.assertFalse(result['di_anchor_continuous']);self.assertIsNone(result['di_plus_local_high'])

    def test_price_links_are_causal_and_origin_and_confirmation_momentum_are_separate(self):
        state=m.new_state();saved=None
        for i,value in enumerate((20,30,25,24)):
            bar=client(i)
            if i==3:bar.update(low=90.1,high=92,close=91)
            state,result=step(state,i,value,low=(90,0,0) if i>=2 else (None,None,None),candle=bar)
            if i==2:saved=result['di_anchor_events']
        self.assertEqual(result['di_plus_at_price_low'],20)
        self.assertEqual(result['di_plus_at_price_low_confirmation'],25)
        self.assertEqual(result['di_plus_from_price_low'],-1)
        self.assertEqual(result['di_price_low_known_time'],180000)
        self.assertEqual(result['di_price_low_regime'],'R2')
        self.assertTrue(result['di_price_low_retest_rejection']);self.assertFalse(result['di_price_low_broken'])
        event=next(e for e in json.loads(saved) if e.get('channel')=='di_plus' and e['type']=='di_high')
        self.assertEqual(event['origin_regime'],'R1');self.assertEqual(event['confirmation_regime'],'R2')
        self.assertEqual(event['price_anchors']['low']['known_time'],event['confirmed_time'])
        state,result=step(state,4,23,low=(90,0,0),candle={**client(4),'low':89,'high':91,'close':89.5})
        self.assertTrue(result['di_price_low_broken']);self.assertEqual(result['di_price_low_tolerance'],.2)
        before=copy.deepcopy(state['prices'])
        state,result=step(state,5,25,high=(110,999,99999999))
        self.assertEqual(state['prices']['high'],before['high'])

    def test_history_is_bounded_and_missing_origin_is_unknown(self):
        state=m.new_state();p=dict(diAnchorHistory=3,diAnchorSourceHistory=8)
        for i in range(40):state,result=step(state,i,20 if i%2==0 else 30,parameters=p)
        self.assertLessEqual(len(state['history']),8)
        self.assertEqual(len(state['channels']['di_plus']['highs']),3)
        state,result=step(state,40,20,parameters=p,low=(90,0,0))
        self.assertIsNone(result['di_plus_at_price_low'])
        self.assertEqual(result['di_plus_at_price_low_confirmation'],20)

    def test_configuration_validation(self):
        for change in ({'diAnchorPlusHighMin':101},{'diAnchorReversal':-1},{'diAnchorHistory':1000},{'diAnchorPlusHighMin':50,'diAnchorPlusHighMax':40},{'diAnchorConfirmBars':256}):
            with self.assertRaises(ValueError):m.validate({**m.DEFAULTS,**change})


class MomentumIntegrationTests(unittest.TestCase):
    def test_addition_replays_only_new_columns_and_belongs_to_momentum(self):
        from Section_4_Features.execution.components import Catalog,desired_parameters
        from Section_4_Features.features.registry import load
        c=Catalog();old={k:v for k,v in c.source.items() if '.momentum_anchors:' not in k and 'diAnchorsState' not in k}
        old_parameters={k:v for k,v in desired_parameters().items() if k not in m.DEFAULTS}
        plan=c.plan(c.changed(old,old_parameters,desired_parameters()))
        self.assertEqual(plan.columns,set(m.EXPORTS))
        from Section_1_Global_Core.memory_storage.Storage.features_store import decision_fields
        self.assertFalse(set(m.EXPORTS)&set(decision_fields()))
        self.assertEqual({c.by_id[k].module for k in plan.execute},{'Section_4_Features.features.momentum','Section_4_Features.features.momentum_anchors'})
        owners={r['name']:r for r in load()};self.assertTrue(set(m.EXPORTS)<=set(owners['momentum']['output_fields']))
        changed=c.plan(c.changed(c.source,desired_parameters(),{**desired_parameters(),'diAnchorPlusHighMin':35.}))
        self.assertTrue(changed.columns);self.assertTrue(changed.columns<=set(m.EXPORTS))

    def test_selective_replay_and_checkpoint_match_full_engine(self):
        from Section_4_Features.execution.engine import Engine
        from Section_4_Features.execution.selective import PartialEngine
        from Section_4_Features.execution.components import Catalog,desired_parameters
        from Section_4_Features.execution import checkpoint
        c=Catalog();old={k:v for k,v in c.source.items() if '.momentum_anchors:' not in k and 'diAnchorsState' not in k}
        plan=c.plan(c.changed(old,desired_parameters(),desired_parameters()))
        full=Engine('TESTUSDT','1m');partial=PartialEngine('TESTUSDT','1m',plan,desired_parameters())
        for i in range(150):
            price=100+math.sin(i/5)*8;bar=client(i);bar.update(open=price-.2,high=price+1,low=price-1,close=price,volume=10+i%5)
            expected=full.step(bar);actual=partial.step(bar,{k:v for k,v in expected.items() if k not in m.EXPORTS})
            actual.pop('open_time')
            self.assertEqual(actual,{k:expected[k] for k in m.EXPORTS},i)
            if i==74:
                partial.context=checkpoint.restore('TESTUSDT','1m',checkpoint.dump(partial,[0,0]),[0,0]).context
