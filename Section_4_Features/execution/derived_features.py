"""Cheap read-time derivatives; live calculations remain in trend.update."""
from . import runtime as rt


def trend_values(row):
    out={}
    for a,b in ((7,25),(25,50),(50,100)):
        key=f'ema_gap{a}_{b}'
        out[key]=rt.math_abs(rt.binary('-',row.get(f'ema{a}'),row.get(f'ema{b}')))
        out[key+'_pct']=rt.binary('/',out[key],row.get('c'))
    out['ema_compression']=rt.binary('/',rt.binary('+',rt.binary('+',out['ema_gap7_25_pct'],out['ema_gap25_50_pct']),out['ema_gap50_100_pct']),3)
    return rt.clean(out)
