"""Retrospective native 1h pivot alignment of executed research trades.
Uses existing confirmed event lineage only; never feeds pivot labels into entries.
"""
from bisect import bisect_right
from collections import Counter
from datetime import datetime,timezone,timedelta
import gzip,hashlib,json,math,statistics,time
from pathlib import Path

P=Path(__file__).parent
HOUR=3600000

def read(path):return json.loads(gzip.decompress(path.read_bytes()) if path.suffix=='.gz' else path.read_bytes())
def stamp(t):return datetime.fromtimestamp(t/1000,timezone(timedelta(hours=5))).isoformat()
def policy_key(p):return json.dumps(p,sort_keys=True,separators=(',',':'))
def full_candle(row):
    if row is None or row['close_time']!=row['open_time']+HOUR-1:return False
    values=[row[k] for k in ('open','high','low','close')]
    return all(isinstance(v,(int,float)) and math.isfinite(v) and v>0 for v in values) and row['low']<=min(row['open'],row['close'])<=max(row['open'],row['close'])<=row['high']

def placement(t,by_origin,*,basis='origin_time'):
    bucket=t//HOUR*HOUR
    exact=[e for e in by_origin.get(bucket,[]) if basis=='origin_time' or e['known_time']<=t]
    following=[e for e in by_origin.get(bucket-HOUR,[]) if basis=='origin_time' or e['known_time']<=t]
    # Categories are disjoint, even if adjacent native pivots share a window.
    category='pivot_candle' if exact else 'next_candle' if following else 'elsewhere'
    matches=exact or following
    return dict(category=category,hour_open=bucket,matches=matches,already_known=any(e['known_time']<=t for e in matches))

def summarize_side(items,field):
    counts=Counter(x[field]['category'] for x in items);near=counts['pivot_candle']+counts['next_candle'];n=len(items)
    return dict(total=n,pivot_candle=counts['pivot_candle'],next_candle=counts['next_candle'],combined=near,pct=100*near/n if n else None,elsewhere=counts['elsewhere'],matched_pivot_already_known=sum(x[field]['already_known'] for x in items if x[field]['category']!='elsewhere'),unique_matched_pivots=len({e['id'] for x in items for e in x[field]['matches']}))

def load_events():
    old=read(P.parent/'BTC_1h_sequences/source_v1.json.gz');pivots={c['pivot']['id']:c['pivot'] for c in old['pivots']};old_meta=old['source_metadata'];old_id=old['source_id'];old_last=old['coverage']['last'];del old
    source=read(P.parent/'BTC_1h_di_spread_reversal/source.json.gz');metadata=source['source_metadata'];source_signature=source['source_signature'];hours={r['open_time']:{k:r[k] for k in ('open_time','close_time','open','high','low','close')} for r in source['rows']};first=min(hours);last=max(hours);last_close=hours[last]['close_time'];del source
    from Section_1_Global_Core import regime_inputs,pivot_research
    from Section_1_Global_Core.memory_storage.Storage import engine_store
    from research_reports.BTC_1h_di_spread_reversal import export_source
    from Section_5_Market_Regime.engines import regime,trend,structure
    fields=tuple(sorted(set(export_source.EXTRA).union(regime.FIELDS,trend.FIELDS,structure.FIELDS)))
    conn=regime_inputs.open_sources();now=int(time.time()*1000)
    try:
        current,cap=pivot_research.metadata(conn,'BTCUSDT','1h')
        if current!=old_meta or engine_store.digest(current)!=old_id:raise ValueError('Archived native-pivot generation differs; do not mix labels')
        if regime_inputs.source_metadata(conn,'BTCUSDT','1h','initial',fields)!=metadata:raise ValueError('Trade-source generation differs from pivot source')
        sql='''SELECT k.open_time,k.close_time,f.formula_version,f.measurement_version,f.measurement_config_id,
        f.structure_events,f.structure_events_version,f.structure_event_status FROM features f JOIN raw.klines k
        ON f.symbol=k.symbol AND f.interval=k.interval AND f.open_time=k.open_time
        WHERE f.symbol=? AND f.interval=? AND f.open_time>? AND f.open_time<=? AND k.close_time<? ORDER BY f.open_time'''
        tail=conn.execute(sql,('BTCUSDT','1h',old_last,cap,now)).fetchall()
    finally:conn.close()
    tail_added=0;invalid_rows=0
    for row in tail:
        if row[2]!=3 or row[3]!='shared-v1' or not row[4] or row[6]!='structure-events-v1' or row[7]!='READY':invalid_rows+=1;continue
        for event in pivot_research.pivot_events(row[5],row[0],row[1]):
            if event['id'] not in pivots:tail_added+=1
            pivots[event['id']]=event
    events=sorted((e for e in pivots.values() if first<=e['origin_time']<=last),key=lambda e:(e['origin_time'],e['known_time'],e['id']))
    for e in events:
        row=hours[e['origin_time']];reference=row['low' if e['type']=='PIVOT_LOW' else 'high']
        if not math.isclose(e['price'],reference,rel_tol=0,abs_tol=1e-8):raise ValueError('Native event price disagrees with frozen OHLC')
    quality=dict(feature_metadata_matches=True,archived_pivots_reused=len(pivots)-tail_added,new_event_rows_read=len(tail),new_pivots_added=tail_added,invalid_tail_rows=invalid_rows,label_observation_ms=now,label_read_cap=cap,trade_first=first,trade_last=last,trade_last_close=last_close,labels_confirmed_after_trade_cutoff=sum(e['known_time']>last_close+1 for e in events),origin_prices_checked=len(events))
    return events,hours,source_signature,quality

def analyze(events,hours,results,source_signature,quality):
    if source_signature!=results['source_signature']:raise ValueError('Trade/pivot input binding mismatch')
    by_type={k:{} for k in ('PIVOT_LOW','PIVOT_HIGH')};by_known={k:{} for k in by_type}
    for e in events:
        by_type[e['type']].setdefault(e['origin_time'],[]).append(e);by_known[e['type']].setdefault(e['known_time']//HOUR*HOUR,[]).append(e)
    highs=sorted((e for e in events if e['type']=='PIVOT_HIGH'),key=lambda e:e['origin_time']);high_times=[e['origin_time'] for e in highs]
    pairs={};qualified=set()
    for low in (e for e in events if e['type']=='PIVOT_LOW'):
        j=bisect_right(high_times,low['origin_time'])
        if j>=len(highs):continue
        high=highs[j];path=[hours.get(t) for t in range(low['origin_time'],high['origin_time']+HOUR,HOUR)]
        complete=all(full_candle(x) for x in path)
        gain=(high['price']/low['price']-1)*100
        pairs[low['id']]=dict(high_id=high['id'],high_origin=high['origin_time'],gain_pct=gain,complete=complete)
        if complete and gain>=1-1e-10:qualified.add(low['id'])
    policy=policy_key(results['policies']['new_exit'])
    wanted={t for v in results['variants'].values() for t in v['replays']['new_exit']['low_first']['accepted_entry_times']}
    cases={c['entry_time']:next(t for t in c['traces'] if t['order']=='low_first') for c in results['entry_cases'] if policy_key(c['policy'])==policy and c['entry_time'] in wanted}
    entry_prices={e['entry_time']:e['entry_open'] for e in results['entry_catalog']}
    details={}
    for t,tr in cases.items():
        buy=placement(t,by_type['PIVOT_LOW']);signal=placement(tr['signal_time'],by_type['PIVOT_LOW']);known=placement(t,by_known['PIVOT_LOW'],basis='known_time')
        item=dict(entry_time=t,signal_time=tr['signal_time'],status=tr['status'],net_pct=tr.get('net_pct'),buy=buy,buy_signal=signal,buy_after_confirmation=known,qualified_buy=any(e['id'] in qualified for e in buy['matches']))
        if buy['matches']:
            item['entry_above_pivot_low_pct']=(tr.get('entry_open',entry_prices[t])/buy['matches'][0]['price']-1)*100
        if tr['status']=='CLOSED':
            # The fill is inside this minute/5m bar. Its upper time bound may
            # equal the NEXT hourly open and must not shift the sell into it.
            item['sell_bar_time']=tr['exit_bar_time'];item['sell']=placement(tr['exit_bar_time'],by_type['PIVOT_HIGH'])
            item['sell_previous_candle']=bool(by_type['PIVOT_HIGH'].get(item['sell']['hour_open']+HOUR))
            item['both_near_any_pivots']=buy['category']!='elsewhere' and item['sell']['category']!='elsewhere'
            item['same_immediate_swing']=any(e['id'] in pairs and item['sell']['hour_open'] in (pairs[e['id']]['high_origin'],pairs[e['id']]['high_origin']+HOUR) for e in buy['matches'])
        details[t]=item
    variants={}
    for key,v in results['variants'].items():
        s=v['replays']['new_exit']['low_first'];entries=[details[t] for t in s['accepted_entry_times']];closed=[x for x in entries if x['status']=='CLOSED']
        buy_summary=summarize_side(entries,'buy');sell_summary=summarize_side(closed,'sell')
        near=[x for x in closed if x['buy']['category']!='elsewhere'];other=[x for x in closed if x['buy']['category']=='elsewhere']
        captured={e['id'] for x in entries for e in x['buy']['matches']};dist=[x['entry_above_pivot_low_pct'] for x in entries if 'entry_above_pivot_low_pct' in x]
        variants[key]=dict(buys=buy_summary,sells=sell_summary,buy_signal=summarize_side(entries,'buy_signal'),first_confirmed_candle_or_next=summarize_side(entries,'buy_after_confirmation'),both_near_any_pivots=sum(x['both_near_any_pivots'] for x in closed),same_low_to_immediate_high=sum(x['same_immediate_swing'] for x in closed),near_qualified_1pct_low_trades=sum(x['qualified_buy'] for x in entries),distinct_qualified_lows_captured=len(captured&qualified),sell_previous_high_candle=sum(x['sell_previous_candle'] for x in closed),near_low_win_pct=100*sum(x['net_pct']>0 for x in near)/len(near) if near else None,other_entry_win_pct=100*sum(x['net_pct']>0 for x in other)/len(other) if other else None,median_entry_above_low_pct=statistics.median(dist) if dist else None,accepted_entry_times=s['accepted_entry_times'])
    delays=[(e['known_time']-e['origin_time'])/HOUR for e in events]
    return dict(version='btc-native-pivot-placement-v1',source_signature=source_signature,quality=quality,pivot_timeframe='1h',trade_policy=results['policies']['new_exit'],scenario='low_first, matching the latest reported table',definitions=dict(buy='Entry timestamp falls within confirmed native LOW origin hourly candle, or the immediately following hourly candle.',sell='Exit execution bar falls within confirmed native HIGH origin hourly candle, or the immediately following hourly candle.',confirmation='Origin-candle alignment is retrospective. known_time is separately checked; later confirmations are labels only, never entry inputs.',qualified='Native LOW to first strictly later native HIGH endpoint >=1%, with complete frozen hourly path. Gross swing label, not executable net trade return.',price='Candle alignment does not mean fill exactly at its low/high.'),native_low_count=sum(e['type']=='PIVOT_LOW' for e in events),native_high_count=sum(e['type']=='PIVOT_HIGH' for e in events),qualified_1pct_low_count=len(qualified),confirmation_delay_hours=dict(min=min(delays),median=statistics.median(delays),max=max(delays)),variants=variants,trade_details={str(t):x for t,x in details.items()},pivots=events)

def write_report(result):
    def pct(s):return f"{s['combined']}/{s['total']} ({s['pct']:.2f}%)" if s['total'] else '—'
    def table(head,rows):return '\n'.join(['| '+' | '.join(head)+' |','| '+' | '.join('---' for _ in head)+' |']+['| '+' | '.join(map(str,row))+' |' for row in rows])
    lines=['# Buy/sell placement against confirmed native BTC 1h pivots','',
    '14 November 2026 (Asia/Karachi). This is a retrospective alignment audit of the executed trades in the fixed bearish +1% target / unchanged bullish trailing study. It does not replay entries or use hindsight pivots as new signals.','',
    'An entry is classified by the hourly candle containing its actual BUY time. A SELL is classified by its execution minute/5m bar, rather than an upper timestamp bound that could fall at the next hourly open. The pivot origin candle and the time when that pivot became known are different.','',
    '## Main comparison','',
    'No optional RSI gate; same low-first execution scenario as the latest headline table. Counts in “next candle” exclude already-counted origin matches. SELL placement uses native pivot HIGHs.','']
    rows=[]
    main=[('DI− >40, immediate','forming_hour_drop_with_5m_peak_di40_rsi_none_immediate'),('DI− >45, immediate','forming_hour_drop_with_5m_peak_di45_rsi_none_immediate'),('DI− >50, immediate','forming_hour_drop_with_5m_peak_di50_rsi_none_immediate'),('DI− >45, avoid recent crash','forming_hour_drop_with_5m_peak_di45_rsi_none_avoid_recent_crash'),('DI− >45, wait micro-high reclaim','forming_hour_drop_with_5m_peak_di45_rsi_none_wait_micro_reclaim'),('DI− >45 + RSI <20, immediate','forming_hour_drop_with_5m_peak_di45_rsi_signal_immediate')]
    for label,key in main:
        v=result['variants'][key];b=v['buys'];s=v['sells'];rows.append([label,b['total'],b['pivot_candle'],b['next_candle'],pct(b),s['pivot_candle'],s['next_candle'],pct(s)])
    lines += [table(['Strategy','Trades','BUY low candle','BUY next candle','BUY combined','SELL high candle','SELL next candle','SELL combined'],rows),'',
    '## DI− >45 baseline detail','']
    v=result['variants']['forming_hour_drop_with_5m_peak_di45_rsi_none_immediate'];b=v['buys'];s=v['sells']
    lines += [f"- Executed BUYs near a LOW: **{pct(b)}**. Of these, **{b['matched_pivot_already_known']}** matched lows had already become confirmed at the BUY time.",f"- SELLs near a HIGH: **{pct(s)}**. Another {v['sell_previous_high_candle']} sells fall in the hour immediately before a confirmed high; this is separate from the requested high/next category.",f"- Both ends near any appropriate native pivot: **{v['both_near_any_pivots']}** trades. BUY near a native low and SELL near its first strictly later native high: **{v['same_low_to_immediate_high']}** trades.",f"- BUYs near lows that subsequently had a complete native low→immediate-high move ≥1% gross: **{v['near_qualified_1pct_low_trades']}** trades, capturing **{v['distinct_qualified_lows_captured']}** distinct qualifying lows.",f"- There are {result['native_low_count']:,} native lows / {result['native_high_count']:,} native highs in the frozen trade-origin window, including {result['qualified_1pct_low_count']:,} complete ≥1% low→immediate-high swings. These are market-opportunity labels, not trade counts.",f"- Matched-origin/next entries have median reference entry price **{v['median_entry_above_low_pct']:.3f}% above** the final hourly pivot low. Being inside that candle does not establish a fill at the bottom.",f"- Win rate for entries near a native low: {v['near_low_win_pct']:.2f}%; other entries: {v['other_entry_win_pct']:.2f}%. Both retain their original protective stops and exits.",'',
    '## Confirmation timing','',
    f"Native pivots in this audit have median origin-open→known delay {result['confirmation_delay_hours']['median']:.2f} hours. Main placement counts use where the eventual confirmed pivot is drawn. A trade can align with that origin while the confirmation is still in the future. It must not be described as buying an already-known confirmed low.",'',
    f"As a separate definition, the DI− >45 baseline has {pct(v['first_confirmed_candle_or_next'])} buys in the first hourly candle when a native low is already known or its following candle. This measures post-confirmation placement, not origin/next placement.",'',
    '## Provenance','',
    f"The archived native pivots and frozen trade source matched current feature metadata exactly. {result['quality']['archived_pivots_reused']:,} archived native events were reused; only {result['quality']['new_event_rows_read']} newer hourly event rows were read. No pivot algorithm or parameter was changed.",
    f"Pivot labels are observed as of **{stamp(result['quality']['label_observation_ms'])}**. Trade prices/outcomes remain frozen through **{stamp(result['quality']['trade_last_close'])}**. {result['quality']['labels_confirmed_after_trade_cutoff']} origin-window pivots were confirmed after the trade cutoff and are used only as retrospective labels.",
    'All event prices were checked against frozen hourly highs/lows. Per-trade origin/confirmation matches and all 72 entry variants are retained in pivot_alignment.json. The setup-candle versus actual-fill placement is retained separately; no filter, signal, stop or winning label was changed.','']
    (P/'PIVOT_ALIGNMENT.md').write_text('\n'.join(lines))

if __name__=='__main__':
    events,hours,signature,quality=load_events();results=read(P/'results.json');report=analyze(events,hours,results,signature,quality)
    report['code_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    (P/'pivot_alignment.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n');write_report(report)
    for key in ['forming_hour_drop_with_5m_peak_di45_rsi_none_immediate','forming_hour_drop_with_5m_peak_di45_rsi_none_avoid_recent_crash','forming_hour_drop_with_5m_peak_di45_rsi_none_wait_micro_reclaim']:
        v=report['variants'][key];print(key,json.dumps({k:v[k] for k in ('buys','sells','both_near_any_pivots','same_low_to_immediate_high','near_qualified_1pct_low_trades','median_entry_above_low_pct','near_low_win_pct','other_entry_win_pct')}),flush=True)
