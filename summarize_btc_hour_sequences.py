"""Summarize complete BTC 1h sequence results without market database access."""
import argparse,gzip,json,statistics,collections
from pathlib import Path
from datetime import datetime,timezone
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--input',type=Path,default=Path('research_reports/BTC_1h_sequences/analysis_v1.json.gz'))
parser.add_argument('--output',type=Path,default=Path('research_reports/BTC_1h_sequences/findings_v1.json'))
args=parser.parse_args()
p=json.load(gzip.open(args.input,'rt'))
sn=p['snapshots'];out={'version':'btc-hour-findings-v1','source_id':p['source_id'],'observed_as_of':p['observed_as_of'],'counts':p['counts'],'discrepancies':p['outcome_discrepancies'],'coverage':p['engine_coverage']}
def stats(values):
 v=sorted(x for x in values if x is not None)
 return dict(n=len(v),mean=statistics.mean(v) if v else None,median=statistics.median(v) if v else None,p10=v[int((len(v)-1)*.1)] if v else None,p90=v[int((len(v)-1)*.9)] if v else None)
def forward(records,h='12',side='BUY'):
 os=[r['future'][h] for r in records];good=[r for r in os if r['complete']];fac=1 if side=='BUY' else -1
 return dict(n=len(os),complete=len(good),censored=len(os)-len(good),close_return_pct=stats(r['close_return_pct']*fac for r in good),positive=sum(r['close_return_pct']*fac>0 for r in good),favorable_1pct=sum(r['up_1pct' if side=='BUY' else 'down_1pct'] is True for r in good),adverse_1pct=sum(r['down_1pct' if side=='BUY' else 'up_1pct'] is True for r in good),both=sum(r['up_1pct'] and r['down_1pct'] for r in good))
out['native']={}
for side in ['BUY','SELL']:
 cases=[c for c in p['cases'] if c['side']==side];hits=[c for c in cases if c['outcome']['status']=='HIT']
 d=dict(n=len(cases),outcomes=dict(collections.Counter(c['outcome']['status'] for c in cases)),hit_stages={})
 for stage in ['candidate_start','final_extreme_first_recorded','origin_close','native_confirmation']:
  key='known_offset_hours';d[stage+'_timing']=stats(c['recognition'].get(stage,{}).get(key) for c in cases)
  d['hit_stages'][stage]=dict(target_already_passed=sum(c['recognition'].get(stage,{}).get('close_already_1pct_from_pivot') is True for c in hits),n=len(hits))
  d[stage+'_values']={}
  for label in ['HIT','NO_HIT']:
   group=[sn[str(c['stages'][stage])]['di'] for c in cases if c['outcome']['status']==label and c['stages'][stage] is not None];group=[s for s in group if s]
   d[stage+'_values'][label]={k:stats(s[k] for s in group) for k in ['di_plus','di_minus','abs_spread','adx','dominance']}
 d['sequential']=dict(both=sum(bool(c['pressure_peaks']) and bool(c['spread_peaks']) for c in cases),same_first=sum(c['spread_peak_lag_bars']==0 for c in cases),lag=stats(c['spread_peak_lag_bars'] for c in cases))
 out['native'][side]=d
out['candidate_groups']=[]
for side in ['BUY','SELL']:
 records=[r for r in p['candidate_observations'] if r['side']==side]
 groups={'ALL':records}
 for event in ['STARTED','UPDATED','CARRIED_FORWARD']:groups['event:'+event]=[r for r in records if r['event']==event]
 for value in ['[0,5)','[5,10)','[10,20)','[20,35)','[35,40)','[40,+inf)']:groups['spread:'+value]=[r for r in records if (sn[str(r['snapshot'])]['di'] or {}).get('spread_bin')==value]
 for flag in ['di_only_buy_turn' if side=='BUY' else 'di_only_sell_turn','di_minus_peak' if side=='BUY' else 'di_plus_peak','spread_peak']:
  for b in [True,False]:groups[flag+':'+str(b)]=[r for r in records if sn[str(r['snapshot'])]['events'][flag] is b]
 for key,rs in groups.items():out['candidate_groups'].append(dict(side=side,condition=key,horizons={h:forward(rs,h,side) for h in ['1','3','6','12']}))
out['recovery_groups']=[]
for path in ['ALL','STAYED_ABOVE_BOTH','LOST_MINUS_ONLY','LOST_BOTH','NOT_ABOVE_BOTH_AT_START']:
 ds=[r for r in p['di_plus_recoveries'] if path=='ALL' or r['comparison_path']==path]
 groups={'ALL':ds,'brief':[r for r in ds if r['brief']]}
 for year in range(2017,2027):groups[str(year)]=[r for r in ds if datetime.fromtimestamp(sn[str(r['recovery'])]['open_time']/1000,timezone.utc).year==year]
 for key,rs in groups.items():out['recovery_groups'].append(dict(path=path,period=key,**forward(rs),regain=dict(collections.Counter(r['regained_pre_dip_level_status'] for r in rs))))
out['post_sell']={}
for anchor in ['candidate_start','origin_close']:
 for window in ['until_next_opposite_pivot','within_12_hours']:
  ids={i for c in p['cases'] if c['side']=='SELL' for i in c['post_sell_recovery_ids'][anchor][window]};rs=[p['di_plus_recoveries'][i] for i in sorted(ids)]
  out['post_sell'][anchor+':'+window]={path:forward([r for r in rs if r['comparison_path']==path]) for path in ['STAYED_ABOVE_BOTH','LOST_MINUS_ONLY','LOST_BOTH','NOT_ABOVE_BOTH_AT_START']}
# All hourly observations: not limited to eventual successful pivots.
out['all_hourly_baseline']=forward(p['candidate_observations'])
out['native_groups']=[g for g in p['groups'] if g['year']=='ALL' and g['stage']=='candidate_start' and g['dimension'] in ['spread_bin','dominant','independent_pressure_peak_now','spread_peak_now']]
args.output.parent.mkdir(parents=True,exist_ok=True)
args.output.write_text(json.dumps(out,indent=2,allow_nan=False)+'\n')
print("Saved:",args.output)
