"""Same-candle EMA distances; preserve the live EMA-structure formulas exactly."""
from . import runtime as rt

PERIODS = (7,25,50,100,200,300)
FIELDS = {
    'ema50_distance_pct':'ema50DistancePct',
    'ema200_distance_pct':'ema200DistancePct',
    'ema300_distance_pct':'ema300DistancePct',
    'ema50_200_gap_pct':'ema50_200GapPct',
    'nearest_buy_ema':'nearestBuyEMA',
    'nearest_buy_ema_distance':'nearestBuyEMADistance',
    'nearest_buy_ema_distance_pct':'nearestBuyEMADistancePct',
    'nearest_sell_ema':'nearestSellEMA',
    'nearest_sell_ema_distance':'nearestSellEMADistance',
    'nearest_sell_ema_distance_pct':'nearestSellEMADistancePct',
}
INPUTS = ('c',*(f'ema{period}' for period in PERIODS))


def values(row):
    price=row.get('c')
    out={}
    for period in (50,200,300):
        out[f'ema{period}_distance_pct']=rt.binary('*',rt.binary('/',
            rt.math_abs(rt.binary('-',price,row.get(f'ema{period}'))),price),100)
    base=row.get('ema200')
    out['ema50_200_gap_pct']=(0.0 if rt.is_na(base) or base==0 else
        rt.binary('*',rt.binary('/',rt.math_abs(rt.binary('-',row.get('ema50'),base)),base),100))
    for side,operator in (('buy','>'),('sell','<')):
        nearest=distance=pct=rt.NA
        for period in PERIODS:
            ema=row.get(f'ema{period}')
            if rt.is_na(ema) or not rt.truth(rt.binary(operator,ema,price)):
                continue
            candidate=rt.math_abs(rt.binary('-',ema,price))
            if rt.is_na(distance) or rt.truth(rt.binary('<',candidate,distance)):
                nearest=ema;distance=candidate
                pct=rt.binary('*',rt.binary('/',distance,price),100)
        out[f'nearest_{side}_ema']=nearest
        out[f'nearest_{side}_ema_distance']=distance
        out[f'nearest_{side}_ema_distance_pct']=pct
    return rt.clean(out)
