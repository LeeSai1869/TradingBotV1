"""Canonical storage names and explicit legacy aliases for the Pine contract."""
import re
from functools import lru_cache
from .context import MANIFEST


@lru_cache(maxsize=4096)
def snake(name):
    name=re.sub(r'([A-Z]+)([A-Z][a-z])',r'\1_\2',name)
    name=re.sub(r'([a-z0-9])([A-Z])',r'\1_\2',name)
    return name.lower()

REGIMES=('controlState','energyState','regimeState','fatigueState','trendState','transitionState')
FIELDS={snake(name):kind for name,kind in MANIFEST['contract']}
FIELDS.update({snake(name):'string' for name in REGIMES})
ALIASES={
 'ema_gap_7_25':'ema_gap7_25','ema_gap_25_50':'ema_gap25_50','ema_gap_50_100':'ema_gap50_100',
 'ema_gap_7_25_pct':'ema_gap7_25_pct','ema_gap_25_50_pct':'ema_gap25_50_pct','ema_gap_50_100_pct':'ema_gap50_100_pct',
 'distance_to_poc_atr':'distance_to_pocatr',
 'prev_close':'c1','current_price':'current_price','prev_candle_range':'prev_candle_range',
 'newyork_high':'new_york_high','newyork_low':'new_york_low',
 'vp_vah':'vp_va_high','vp_val':'vp_va_low',
 'nearest_support_price':'nearest_support','nearest_resistance_price':'nearest_resistance',
 'swing_candidate_pivot':'candidate_pivot','swing_candidate_high_price':'candidate_pivot_high_price','swing_candidate_low_price':'candidate_pivot_low_price',
 'swing_pivot_high_confirmed':'pivot_high_confirmed_this_bar','swing_pivot_low_confirmed':'pivot_low_confirmed_this_bar',
 'swing_direction':'current_swing_direction','swing_latest_confirmed_high':'latest_confirmed_pivot_high','swing_latest_confirmed_low':'latest_confirmed_pivot_low',
 'swing_nearest_high':'nearest_swing_high','swing_nearest_low':'nearest_swing_low',
 'swing_distance_to_high_pct':'distance_to_swing_high_pct','swing_distance_to_low_pct':'distance_to_swing_low_pct',
}
for key,source in ALIASES.items():FIELDS[key]=FIELDS.get(source,'float')
for p in (7,25,50,100,200,300):FIELDS[f'prev_ema{p}']='float'
FIELDS['prev_atr']='float'
FIELDS['daily_source_ready']='bool'
for side in ('support','resistance','inst_support','inst_resistance'):
    for edge in ('low','high'):FIELDS[f'{side}_zone_{edge}']='float'


def canonical(values,context):
    result={snake(name):value for name,value in values.items()}
    for side,prefix,identifier in [('support','support','nearestSupportZoneID'),('resistance','resistance','nearestResistanceZoneID'),('inst_support','instSupport','nearestInstSupportZoneID'),('inst_resistance','instResistance','nearestInstResistanceZoneID')]:
        ids=context.persistent.get(prefix+'ZoneIDArray',[])
        identity=context.values.get(identifier)
        index=ids.index(identity) if identity in ids else None
        for edge in ('low','high'):
            levels=context.persistent.get(prefix+edge.title()+'Array',[])
            result[f'{side}_zone_{edge}']=levels[index] if index is not None and index<len(levels) else None
    # Calculated in 4.2.12 but omitted from the Pine constructor's type fields.
    result['prev_candle_range']=context['prevCandleRange']
    for key,source in ALIASES.items():
        if source in result:result[key]=result[source]
    for name in ['atr',*[f'ema{p}' for p in (7,25,50,100,200,300)]]:
        result['prev_'+name]=context.previous(name,1)
    result.update(symbol=context.symbol,interval=context.timeframe,open_time=context.current_client['open_time'],formula_version=3)
    return result

# Read compatibility for feature columns written by formula versions 1/2.
LEGACY_FIELDS = ('c', 'o', 'h', 'l', 'c1', 'o1', 'h1', 'l1', 'current_price', 'prev_close', 'ema7', 'ema25', 'ema50', 'ema100', 'ema200', 'ema300', 'prev_ema7', 'prev_ema25', 'prev_ema50', 'prev_ema100', 'prev_ema200', 'prev_ema300', 'ema_gap_7_25', 'ema_gap_25_50', 'ema_gap_50_100', 'ema_gap_7_25_pct', 'ema_gap_25_50_pct', 'ema_gap_50_100_pct', 'ema_compression', 'ema_bull_structure', 'ema_bear_structure', 'ema50_distance_pct', 'ema200_distance_pct', 'ema300_distance_pct', 'ema50_slope_pct', 'ema200_slope_pct', 'ema300_slope_pct', 'ema50_200_gap_pct', 'nearest_buy_ema', 'nearest_buy_ema_distance', 'nearest_buy_ema_distance_pct', 'nearest_sell_ema', 'nearest_sell_ema_distance', 'nearest_sell_ema_distance_pct', 'price_above_ema50', 'price_below_ema50', 'price_above_ema200', 'price_below_ema200', 'price_above_ema300', 'price_below_ema300', 'wma50', 'wma50_distance', 'wma50_distance_pct', 'rsi', 'prev_rsi', 'rsi_change', 'bull_momentum_divergence', 'bear_momentum_divergence', 'adx', 'prev_adx', 'di_plus', 'prev_di_plus', 'di_minus', 'prev_di_minus', 'di_direction', 'di_spread', 'di_dominance', 'bull_momentum_weakening', 'bear_momentum_weakening', 'atr', 'prev_atr', 'atr_percent', 'atr_ma', 'atr_ma_ratio', 'atr_change', 'volume', 'prev_volume', 'volume_ma', 'volume_ratio', 'prev_volume_ratio', 'candle_range', 'prev_candle_range', 'body', 'prev_body', 'body_percent', 'prev_body_percent', 'upper_wick', 'lower_wick', 'wick_ratio', 'close_location', 'prev_close_location', 'candle_direction', 'prev_candle_direction', 'displacement_atr', 'prev_displacement_atr', 'candle_range_atr', 'change', 'change_percent', 'directional_displacement', 'candle_efficiency', 'bull_engulfing', 'bear_engulfing', 'bull_rejection', 'bear_rejection', 'vwap', 'vwap_distance', 'vwap_distance_pct', 'price_above_vwap', 'price_below_vwap', 'vwap_upper1', 'vwap_lower1', 'vwap_upper2', 'vwap_lower2', 'nearest_buy_vwap', 'nearest_buy_vwap_distance', 'nearest_buy_vwap_distance_pct', 'nearest_buy_vwap_type', 'nearest_sell_vwap', 'nearest_sell_vwap_distance', 'nearest_sell_vwap_distance_pct', 'nearest_sell_vwap_type')
