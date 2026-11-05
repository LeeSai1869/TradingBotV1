import copy
import json
import sqlite3
import unittest
from Section_1_Global_Core import pivot_context_audit as a
from audit_pivot_context import dashboard

class ContextAudit(unittest.TestCase):
    def test_closed_higher_timeframes_never_use_forming_bar(self):
        self.assertEqual(a.closed_open(15*a.DURATIONS['1h']+30*60000,'4h'),8*a.DURATIONS['1h'])
        self.assertEqual(a.closed_open(16*a.DURATIONS['1h'],'4h'),12*a.DURATIONS['1h'])
        self.assertEqual(a.closed_open(a.DURATIONS['1d']+60000,'1d'),0)

    def test_exact_run_binding_and_asof_no_stale_fallback(self):
        conn=sqlite3.connect(':memory:');conn.execute('CREATE TABLE engine_results(run_id TEXT,candle_time INTEGER,payload TEXT)')
        meta=dict(identity={'symbol':'BTCUSDT'},engine='TREND',engine_version='v',config_hash='c',input_signature='s')
        payload=dict(**meta,mode='CONFIRMED',candle_open_time=0,candle_close_time=59999,as_of=60000,available_at=999999,data_quality='VALID',classification={'direction':'BULLISH'})
        conn.execute('INSERT INTO engine_results VALUES (?,?,?)',('run',0,json.dumps(payload)));run=dict(run_id='run',metadata=meta)
        self.assertEqual(a.engine_point(conn,run,'1m',60000)['classification']['direction'],'BULLISH')
        self.assertIsNone(a.engine_point(conn,run,'1m',120000)['classification'])
        payload['as_of']=60001;conn.execute('UPDATE engine_results SET payload=?',(json.dumps(payload),))
        self.assertEqual(a.engine_point(conn,run,'1m',60000)['status'],'INVALID_AS_OF')
        conn.close()

    def test_band_gaps_censor_missing_and_dont_invent_touch_from_jump(self):
        bar=lambda t,lo,hi:dict(open_time=t,close_time=t+59999,open=lo,low=lo,high=hi,close=hi)
        area=dict(low=105,high=106)
        self.assertEqual(a.band_outcome(area,[bar(0,100,102)],0,60000,60000)['status'],'CENSORED')
        out=a.band_outcome(area,[bar(0,100,102),bar(60000,110,112)],0,60000,60000)
        self.assertEqual(out['status'],'NO_TOUCH');self.assertEqual(out['gap_crossings'],1)
        out=a.band_outcome(area,[bar(0,100,106),bar(120000,110,112)],0,120000,60000)
        self.assertEqual(out['status'],'TOUCHED');self.assertFalse(out['complete_window']);self.assertTrue(out['gap'])

    def report(self):
        f=dict(formula_version=3,measurement_version='shared-v1',measurement_config_id='test',atr=1,rsi=35,di_plus=10,di_minus=30,adx=30,
               ema50=103,ema200=104,vwap=102,atr_ma_ratio=1,current_structure='STRUCTURE_BULL',bullish_structure_active=1,bearish_structure_active=0)
        bars=[dict(client=dict(open_time=t,close_time=t+59999,open=100,close=101,high=102,low=99),features=f.copy()) for t in (0,60000,120000,180000)]
        c=dict(id='one',side='BUY_SIDE',pivot=dict(origin_time=60000,known_time=180000),origin=dict(status='HIT'),after_known=dict(status='NO_HIT'),next_opposite=dict(origin_time=180000))
        return dict(version='pivot-moves-v1',symbol='BTCUSDT',timeframe='1m',source_id='s',observed_as_of=240000,config=dict(horizon_bars=None),summary=dict(pivots=1),cases=[c],contexts={'one':dict(bars=bars)})

    def test_point_uses_recognition_candle_prior_only_and_missing_engine_is_explicit(self):
        report=self.report();before=copy.deepcopy(report)
        output=a.audit(report,a.EmbeddedReader(report),embedded_only=True)
        row=output['cases'][0];self.assertEqual(row['status'],'READY');self.assertEqual(row['alignment'],'UNKNOWN')
        self.assertIsNotNone(row['confidence']['score']);self.assertEqual(report,before)
        altered=copy.deepcopy(report);altered['contexts']['one']['bars'][-1]['features']['rsi']=99
        result=a.audit(altered,a.EmbeddedReader(altered),embedded_only=True)
        self.assertEqual(row['confidence'],result['cases'][0]['confidence'])
        html=dashboard(output);self.assertIn('SELECTED_EMBEDDED_EXAMPLES',html);self.assertIn('not actual BUY/SELL',html)

    def test_warmup_and_censored_cases_are_not_zero_scores_or_failures(self):
        report=self.report();report['contexts']['one']['bars'][2]['features']['measurement_version']=None
        report['cases'][0]['after_known']['status']='CENSORED'
        output=a.audit(report,a.EmbeddedReader(report),embedded_only=True)
        self.assertIsNone(output['cases'][0]['confidence'])
        group=next(g for g in output['summary']['groups'] if g['dimension']=='all' and g['year']=='ALL')
        self.assertEqual(group['resolved'],0);self.assertIsNone(group['hit_rate_pct'])

    def test_conflicting_embedded_features_rejected_but_case_relative_offsets_allowed(self):
        report=self.report();report['contexts']['two']=copy.deepcopy(report['contexts']['one'])
        report['contexts']['two']['bars'][0]['relative_to_origin']=-100
        a.EmbeddedReader(report)
        report['contexts']['two']['bars'][0]['features']['rsi']=99
        with self.assertRaises(ValueError):a.EmbeddedReader(report)

    def test_saved_decisions_keep_exact_original_scores_and_inventory_bands(self):
        from unittest.mock import patch
        report=self.report();report['config']['threshold_pct']=2
        report['cases'][0]['pivot']['type']='PIVOT_LOW'
        report['cases'].append(dict(id='high',side='SELL_SIDE',pivot=dict(type='PIVOT_HIGH',origin_time=180000,known_time=240000)))
        report['summary']['pivots']=2;report['requested_since']=0
        reader=a.EmbeddedReader(report)
        point=reader.point(120000)
        conf=a.confidence.evaluate(101,point['features'],previous={**reader.point(60000)['features'],'close':101},candle=point['client'])
        conf=copy.deepcopy(conf);conf['buy_score']=78
        opp=a.opportunity.evaluate(101,point['features'],candle=point['client'])
        opp=copy.deepcopy(opp);opp['areas']['resistance']=[dict(low=101.5,high=102,modeled=False,families=['sr'])]
        saved=dict(side='BUY',open_time=120000,entry=101,confidence=conf,opportunity=opp,storage=dict(provenance='historical reconstruction'))
        conn=sqlite3.connect(':memory:');conn.execute('CREATE TABLE decision_evidence(symbol TEXT,interval TEXT,epoch TEXT,open_time INTEGER,signal_type TEXT,payload TEXT)')
        conn.execute('INSERT INTO decision_evidence VALUES (?,?,?,?,?,?)',('BTCUSDT','1m','epoch',120000,'BUY',json.dumps(saved)))
        # Old epochs must never substitute for missing current evidence.
        conn.execute('INSERT INTO decision_evidence VALUES (?,?,?,?,?,?)',('BTCUSDT','1m','old',60000,'SELL',json.dumps(saved)))
        with patch('Section_1_Global_Core.decision_evidence.epoch_key',return_value='epoch'):
            output=a.audit_saved_decisions(report,reader,conn)
        row=output['cases'][0];self.assertEqual(row['confidence']['score'],78)
        self.assertEqual(row['opportunity']['scope'],'PERSISTED_DECISION_SNAPSHOT')
        self.assertEqual(row['opportunity']['areas'][0]['low'],101.5)
        self.assertEqual(row['opportunity']['areas'][0]['outcome']['status'],'TOUCHED')
        self.assertIsNone(row['confidence']['structure_sensitivity_points'])
        self.assertEqual(output['evidence_coverage']['stored_snapshots'],1)
        conn.close()

    def test_di_events_are_independent_three_candle_sequences(self):
        report=self.report();bars=report['contexts']['one']['bars']
        for row,plus,minus in zip(bars,(5,20,10,99),(35,30,25,1)):
            row['features'].update(di_plus=plus,di_minus=minus)
        output=a.audit(report,a.EmbeddedReader(report),embedded_only=True);di=output['cases'][0]['di_sequence']
        self.assertEqual(di['di_plus']['event'],'PEAK_CONFIRMED');self.assertEqual(di['di_minus']['event'],'NO_TURN')

    def test_reaction_excludes_touch_candle_and_does_not_claim_intrabar_order(self):
        area=dict(low=105,high=106)
        rows=[dict(open_time=0,close_time=59999,open=100,low=90,high=106,close=105),
              dict(open_time=60000,close_time=119999,open=105,low=104,high=108,close=106)]
        out=a.band_outcome(area,rows,0,60000,60000,direction='resistance')
        self.assertAlmostEqual(out['post_touch_max_rejection_pct'],(1-104/105)*100)
        self.assertAlmostEqual(out['post_touch_max_breakthrough_pct'],(108/106-1)*100)
