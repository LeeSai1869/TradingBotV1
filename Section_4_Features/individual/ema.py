"""Ema. Generated main-feature implementation.
Stages execute in manifest dependency order; see individual/README.md."""
from . import runtime as rt

def update_ema(e):
    # Pine 809
    e['ema7'] = e.ta('ema', '809', e['c'], e['ema7Len'])
    # Pine 810
    e['ema25'] = e.ta('ema', '810', e['c'], e['ema25Len'])
    # Pine 811
    e['ema50'] = e.ta('ema', '811', e['c'], e['ema50Len'])
    # Pine 812
    e['ema100'] = e.ta('ema', '812', e['c'], e['ema100Len'])
    # Pine 813
    e['ema200'] = e.ta('ema', '813', e['c'], e['ema200Len'])
    # Pine 814
    e['ema300'] = e.ta('ema', '814', e['c'], e['ema300Len'])
    # Pine 815
    e['emaGap7_25'] = rt.math_abs(rt.binary('-', e['ema7'], e['ema25']))
    # Pine 816
    e['emaGap25_50'] = rt.math_abs(rt.binary('-', e['ema25'], e['ema50']))
    # Pine 817
    e['emaGap50_100'] = rt.math_abs(rt.binary('-', e['ema50'], e['ema100']))
    # Pine 818
    e['emaGap7_25Pct'] = rt.binary('/', e['emaGap7_25'], e['c'])
    # Pine 819
    e['emaGap25_50Pct'] = rt.binary('/', e['emaGap25_50'], e['c'])
    # Pine 820
    e['emaGap50_100Pct'] = rt.binary('/', e['emaGap50_100'], e['c'])
    # Pine 821
    e['emaCompression'] = rt.binary('/', rt.binary('+', rt.binary('+', e['emaGap7_25Pct'], e['emaGap25_50Pct']), e['emaGap50_100Pct']), 3)

def calculate(state,value,length):
    if not rt.is_na(value):
        alpha=2/(length+1)
        state['value']=value if 'value' not in state else alpha*value+(1-alpha)*state['value']
    return state.get('value',rt.NA)

def update_ema_structure(e):
    # Pine 826
    e['emaBullStructure'] = (rt.truth((rt.truth(rt.binary('>', e['ema7'], e['ema25'])) and rt.truth(rt.binary('>', e['ema25'], e['ema50'])))) and rt.truth(rt.binary('>', e['ema50'], e['ema100'])))
    # Pine 827
    e['emaBearStructure'] = (rt.truth((rt.truth(rt.binary('<', e['ema7'], e['ema25'])) and rt.truth(rt.binary('<', e['ema25'], e['ema50'])))) and rt.truth(rt.binary('<', e['ema50'], e['ema100'])))
    # Pine 828
    e['ema50DistancePct'] = (rt.binary('*', rt.binary('/', rt.math_abs(rt.binary('-', e['c'], e['ema50'])), e['c']), 100) if rt.truth((not rt.truth(rt.is_na(e['ema50'])))) else rt.NA)
    # Pine 831
    e['ema200DistancePct'] = (rt.binary('*', rt.binary('/', rt.math_abs(rt.binary('-', e['c'], e['ema200'])), e['c']), 100) if rt.truth((not rt.truth(rt.is_na(e['ema200'])))) else rt.NA)
    # Pine 832
    e['ema300DistancePct'] = (rt.binary('*', rt.binary('/', rt.math_abs(rt.binary('-', e['c'], e['ema300'])), e['c']), 100) if rt.truth((not rt.truth(rt.is_na(e['ema300'])))) else rt.NA)
    # Pine 836
    e['ema50SlopePct'] = (rt.binary('*', rt.binary('/', rt.binary('-', e['ema50'], e.previous('ema50', 1)), e.previous('ema50', 1)), 100) if rt.truth((not rt.truth(rt.is_na(e.previous('ema50', 1))))) else 0.0)
    # Pine 837
    e['ema200SlopePct'] = (rt.binary('*', rt.binary('/', rt.binary('-', e['ema200'], e.previous('ema200', 1)), e.previous('ema200', 1)), 100) if rt.truth((not rt.truth(rt.is_na(e.previous('ema200', 1))))) else 0.0)
    # Pine 838
    e['ema300SlopePct'] = (rt.binary('*', rt.binary('/', rt.binary('-', e['ema300'], e.previous('ema300', 1)), e.previous('ema300', 1)), 100) if rt.truth((not rt.truth(rt.is_na(e.previous('ema300', 1))))) else 0.0)
    # Pine 842
    e['ema50_200GapPct'] = (rt.binary('*', rt.binary('/', rt.math_abs(rt.binary('-', e['ema50'], e['ema200'])), e['ema200']), 100) if rt.truth((rt.truth((not rt.truth(rt.is_na(e['ema200'])))) and rt.truth(rt.binary('!=', e['ema200'], 0)))) else 0.0)
    # Pine 845
    e['emaValues'] = rt.arr_from_values(e['ema7'], e['ema25'], e['ema50'], e['ema100'], e['ema200'], e['ema300'])
    # Pine 847
    e['nearestBuyEMA'] = rt.NA
    # Pine 848
    e['nearestBuyEMADistance'] = rt.NA
    # Pine 849
    e['nearestBuyEMADistancePct'] = rt.NA
    # Pine 851
    e['nearestSellEMA'] = rt.NA
    # Pine 852
    e['nearestSellEMADistance'] = rt.NA
    # Pine 853
    e['nearestSellEMADistancePct'] = rt.NA
    # Pine 855
    for e['i'] in rt.inclusive(0, rt.binary('-', rt.arr_size(e['emaValues']), 1)):
        # Pine 856
        e['emaValue'] = rt.arr_get(e['emaValues'], e['i'])
        # Pine 858
        if rt.truth((not rt.truth(rt.is_na(e['emaValue'])))):
            # Pine 859
            e['emaDistance'] = rt.math_abs(rt.binary('-', e['emaValue'], e['c']))
            # Pine 860
            e['emaDistancePct'] = (rt.binary('*', rt.binary('/', e['emaDistance'], e['c']), 100) if rt.truth(rt.binary('!=', e['c'], 0)) else rt.NA)
            # Pine 861
            if rt.truth(rt.binary('>', e['emaValue'], e['c'])):
                # Pine 862
                if rt.truth((rt.truth(rt.is_na(e['nearestBuyEMADistance'])) or rt.truth(rt.binary('<', e['emaDistance'], e['nearestBuyEMADistance'])))):
                    # Pine 863
                    e['nearestBuyEMA'] = e['emaValue']
                    # Pine 864
                    e['nearestBuyEMADistance'] = e['emaDistance']
                    # Pine 865
                    e['nearestBuyEMADistancePct'] = e['emaDistancePct']
            # Pine 867
            if rt.truth(rt.binary('<', e['emaValue'], e['c'])):
                # Pine 868
                if rt.truth((rt.truth(rt.is_na(e['nearestSellEMADistance'])) or rt.truth(rt.binary('<', e['emaDistance'], e['nearestSellEMADistance'])))):
                    # Pine 869
                    e['nearestSellEMA'] = e['emaValue']
                    # Pine 870
                    e['nearestSellEMADistance'] = e['emaDistance']
                    # Pine 871
                    e['nearestSellEMADistancePct'] = e['emaDistancePct']

def update_ema_position(e):
    # Pine 962
    e['priceAboveVWAP'] = rt.binary('>', e['c'], e['vwapValue'])
    # Pine 963
    e['priceBelowVWAP'] = rt.binary('<', e['c'], e['vwapValue'])
    # Pine 964
    e['priceAboveEMA50'] = rt.binary('>', e['c'], e['ema50'])
    # Pine 965
    e['priceBelowEMA50'] = rt.binary('<', e['c'], e['ema50'])
    # Pine 966
    e['priceAboveEMA200'] = rt.binary('>', e['c'], e['ema200'])
    # Pine 967
    e['priceBelowEMA200'] = rt.binary('<', e['c'], e['ema200'])
    # Pine 968
    e['priceAboveEMA300'] = rt.binary('>', e['c'], e['ema300'])
    # Pine 969
    e['priceBelowEMA300'] = rt.binary('<', e['c'], e['ema300'])

def update_ema_extension(e):
    # Pine 5101
    e['atrExtensionEMA50'] = (rt.binary('/', rt.binary('-', e['c'], e['ema50']), e['atr']) if rt.truth(rt.binary('>', e['atr'], 0)) else rt.NA)
    # Pine 5102
    e['atrExtensionEMA200'] = (rt.binary('/', rt.binary('-', e['c'], e['ema200']), e['atr']) if rt.truth(rt.binary('>', e['atr'], 0)) else rt.NA)

def update(e):
    update_ema(e)
    update_ema_structure(e)
    update_ema_position(e)
    update_ema_extension(e)
