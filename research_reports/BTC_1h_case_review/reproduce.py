"""Three origin-centered BTC 1h examples from the uploaded frozen study."""
import gzip
import hashlib
import json
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/'research_reports/BTC_1pct/BTCUSDT_1h_all-history_1pct_pivots_v1.json.gz'
IDS=('cf2cb3a663781cd64ef23d1c49902c93b4bc2e3675387d5d393497ffd928356c','low-selected-by-origin','0351f8d8677b3848e1d8ea295308ede773d3dc89944270ac6f267a6e5adbfa75')

def main():
 data=SOURCE.read_bytes();p=json.loads(gzip.decompress(data));rows={}
 for context in p['contexts'].values():
  for row in context['bars']:
   t=row['client']['open_time']
   if t in rows and any(rows[t][key]!=row[key] for key in ('client','features')):raise ValueError('Inconsistent overlapping snapshots')
   rows[t]=row
 target=int(datetime(2026,11,4,8,tzinfo=ZoneInfo('Asia/Karachi')).timestamp()*1000)
 choices=[next(c for c in p['cases'] if c['id']==IDS[0]),next(c for c in p['cases'] if c['side']=='BUY_SIDE' and c['pivot']['origin_time']==target),next(c for c in p['cases'] if c['id']==IDS[2])]
 packets=[]
 fields=('di_plus','di_minus','adx','rsi','relative_volume','atr','ema50','candidate_pivot')
 for case in choices:
  origin=case['pivot']['origin_time'];selected=[]
  for offset in range(-3,7):
   row=rows.get(origin+offset*3600000)
   if row:selected.append(dict(offset=offset,client=row['client'],features={k:row['features'].get(k) for k in fields}))
  row=next(r for r in selected if r['offset']==0)
  edge=row['client']['low' if case['side']=='BUY_SIDE' else 'high']
  assert abs(edge-case['pivot']['price'])<1e-8
  packets.append(dict(case=case,origin_pkt=datetime.fromtimestamp(origin/1000,ZoneInfo('Asia/Karachi')).isoformat(),bars=selected,
                      confirmation_delay_hours=(case['pivot']['known_time']-origin)/3600000))
 out=Path(__file__).resolve().parent
 (out/'cases.json').write_text(json.dumps(dict(source_file=SOURCE.name,source_sha256=hashlib.sha256(data).hexdigest(),cutoff=p['observed_as_of'],timezone='Asia/Karachi',cases=packets,note='Three descriptive examples from frozen uploaded contexts, not a representative or predictive validation sample. Measurements are shown at their candle closes, never at candle open. Native known_time is reconstructed event recognition, not actual live delivery.'),indent=2,allow_nan=False)+'\n')
 import matplotlib
 matplotlib.use('Agg')
 import matplotlib.pyplot as plt
 from matplotlib.patches import Rectangle
 fig,axes=plt.subplots(4,3,figsize=(17,12),sharex='col',gridspec_kw=dict(height_ratios=[3,2,1.5,1.5]))
 titles=('Weak low: <1% before next high','Strong low: 1% reached','High after strong upward expansion')
 for col,packet in enumerate(packets):
  case=packet['case'];pivot=case['pivot'];direction=1 if case['side']=='BUY_SIDE' else -1;bars=packet['bars']
  for row in bars:
   c=row['client'];x=row['offset']+.5;color='#2c996b' if c['close']>=c['open'] else '#c45350'
   axes[0,col].vlines(x,c['low'],c['high'],color=color)
   axes[0,col].add_patch(Rectangle((x-.3,min(c['open'],c['close'])),.6,max(abs(c['close']-c['open']),.01),facecolor=color,edgecolor=color))
  axes[0,col].axhline(pivot['price'],color='#8a5bb5',label='Retrospective pivot extreme')
  axes[0,col].axhline(pivot['price']*(1+direction*.01),color='#2889aa',linestyle=':',label='1% from extreme')
  for field,color in (('di_plus','#2c996b'),('di_minus','#c45350')):
   axes[1,col].plot([r['offset']+1 for r in bars],[r['features'][field] for r in bars],marker='.',color=color,label=field)
  for field,color in (('rsi','#5f63b5'),('adx','#b08b30')):
   axes[2,col].plot([r['offset']+1 for r in bars],[r['features'][field] for r in bars],color=color,label=field)
  axes[3,col].bar([r['offset']+1 for r in bars],[r['features']['relative_volume'] or 0 for r in bars],width=.6,color='#5c87a5')
  for ax in axes[:,col]:
   ax.axvspan(0,1,color='#9670b5',alpha=.1);ax.axvline(1,color='#9670b5',linestyle='--');ax.grid(alpha=.15);ax.set_xlim(-3,7)
   if packet['confirmation_delay_hours']<=7:ax.axvline(packet['confirmation_delay_hours'],color='#c49a34',linestyle=':')
  opposite=case.get('next_opposite')
  if opposite:
   measured_end=(opposite['origin_time']-pivot['origin_time'])/3600000+1
   if measured_end<7:
    for ax in axes[:,col]:ax.axvspan(measured_end,7,color='#777777',alpha=.08)
    axes[0,col].axvline(measured_end,color='#777777',linestyle=':',label='After this: context only')
  axes[0,col].set_title(titles[col]+'\n'+packet['origin_pkt'][:16].replace('T',' ')+' PKT · bar opens',fontsize=10)
  axes[0,col].legend(fontsize=7);axes[1,col].legend(fontsize=8);axes[2,col].legend(fontsize=8)
  axes[3,col].set_xlabel('Hours from pivot bar open\nPurple dashed = origin close; native confirmation +'+str(int(packet['confirmation_delay_hours']))+'h')
  axes[0,col].set_ylabel('BTCUSDT price');axes[1,col].set_ylabel('DI');axes[2,col].set_ylabel('RSI / ADX');axes[3,col].set_ylabel('Relative volume')
 fig.suptitle('BTC 1h historical case inspection — candle features are placed at their CLOSES\nPurple shading = origin candle; later information cannot justify an earlier entry',fontsize=12)
 fig.tight_layout();fig.savefig(out/'three_pivots.png',dpi=160);plt.close(fig)
 print('Verified raw extremes and saved three 1h examples; feature timestamps use candle closes.')

if __name__=='__main__':main()
