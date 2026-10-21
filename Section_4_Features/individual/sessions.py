"""Sessions. Generated main-feature implementation.
Stages execute in manifest dependency order; see individual/README.md."""
from . import runtime as rt

def update_session_clock(e):
    # Pine 4925
    if 'asiaHigh' not in e.persistent:
        e.initialize('asiaHigh', rt.NA)
    # Pine 4926
    if 'asiaLow' not in e.persistent:
        e.initialize('asiaLow', rt.NA)
    # Pine 4927
    if 'londonHigh' not in e.persistent:
        e.initialize('londonHigh', rt.NA)
    # Pine 4928
    if 'londonLow' not in e.persistent:
        e.initialize('londonLow', rt.NA)
    # Pine 4929
    if 'newYorkHigh' not in e.persistent:
        e.initialize('newYorkHigh', rt.NA)
    # Pine 4930
    if 'newYorkLow' not in e.persistent:
        e.initialize('newYorkLow', rt.NA)
    # Pine 4931
    if 'prevAsiaHigh' not in e.persistent:
        e.initialize('prevAsiaHigh', rt.NA)
    # Pine 4932
    if 'prevAsiaLow' not in e.persistent:
        e.initialize('prevAsiaLow', rt.NA)
    # Pine 4933
    if 'prevLondonHigh' not in e.persistent:
        e.initialize('prevLondonHigh', rt.NA)
    # Pine 4934
    if 'prevLondonLow' not in e.persistent:
        e.initialize('prevLondonLow', rt.NA)
    # Pine 4935
    if 'prevNewYorkHigh' not in e.persistent:
        e.initialize('prevNewYorkHigh', rt.NA)
    # Pine 4936
    if 'prevNewYorkLow' not in e.persistent:
        e.initialize('prevNewYorkLow', rt.NA)
    # Pine 4937
    if 'asiaHighBar' not in e.persistent:
        e.initialize('asiaHighBar', rt.NA)
    # Pine 4938
    if 'asiaLowBar' not in e.persistent:
        e.initialize('asiaLowBar', rt.NA)
    # Pine 4939
    if 'londonHighBar' not in e.persistent:
        e.initialize('londonHighBar', rt.NA)
    # Pine 4940
    if 'londonLowBar' not in e.persistent:
        e.initialize('londonLowBar', rt.NA)
    # Pine 4941
    if 'newYorkHighBar' not in e.persistent:
        e.initialize('newYorkHighBar', rt.NA)
    # Pine 4942
    if 'newYorkLowBar' not in e.persistent:
        e.initialize('newYorkLowBar', rt.NA)
    # Pine 4943
    if 'prevAsiaHighBar' not in e.persistent:
        e.initialize('prevAsiaHighBar', rt.NA)
    # Pine 4944
    if 'prevAsiaLowBar' not in e.persistent:
        e.initialize('prevAsiaLowBar', rt.NA)
    # Pine 4945
    if 'prevLondonHighBar' not in e.persistent:
        e.initialize('prevLondonHighBar', rt.NA)
    # Pine 4946
    if 'prevLondonLowBar' not in e.persistent:
        e.initialize('prevLondonLowBar', rt.NA)
    # Pine 4947
    if 'prevNewYorkHighBar' not in e.persistent:
        e.initialize('prevNewYorkHighBar', rt.NA)
    # Pine 4948
    if 'prevNewYorkLowBar' not in e.persistent:
        e.initialize('prevNewYorkLowBar', rt.NA)
    # Pine 4949
    if 'nearestHighPrice' not in e.persistent:
        e.initialize('nearestHighPrice', rt.NA)
    # Pine 4950
    if 'nearestHighPriceBar' not in e.persistent:
        e.initialize('nearestHighPriceBar', rt.NA)
    # Pine 4951
    if 'nearestHighPriceSession' not in e.persistent:
        e.initialize('nearestHighPriceSession', '')
    # Pine 4952
    if 'nearestLowPrice' not in e.persistent:
        e.initialize('nearestLowPrice', rt.NA)
    # Pine 4953
    if 'nearestLowPriceBar' not in e.persistent:
        e.initialize('nearestLowPriceBar', rt.NA)
    # Pine 4954
    if 'nearestLowPriceSession' not in e.persistent:
        e.initialize('nearestLowPriceSession', '')
    # Pine 4955
    if 'nearestHighPriceDistance' not in e.persistent:
        e.initialize('nearestHighPriceDistance', rt.NA)
    # Pine 4956
    if 'nearestLowPriceDistance' not in e.persistent:
        e.initialize('nearestLowPriceDistance', rt.NA)
    # Pine 4959
    e['asiaSession'] = (not rt.truth(rt.is_na(e.session('0000-0800'))))
    # Pine 4960
    e['londonSession'] = (not rt.truth(rt.is_na(e.session('0800-1600'))))
    # Pine 4961
    e['newYorkSession'] = (not rt.truth(rt.is_na(e.session('1300-2100'))))

def update_asia_session(e):
    # Pine 4964
    e['newAsiaSession'] = (rt.truth(e['asiaSession']) and rt.truth((not rt.truth(e.previous('asiaSession', 1)))))
    # Pine 4965
    if rt.truth(e['newAsiaSession']):
        # Pine 4966
        e['prevAsiaHigh'] = e['asiaHigh']
        # Pine 4967
        e['prevAsiaLow'] = e['asiaLow']
        # Pine 4968
        e['prevAsiaHighBar'] = e['asiaHighBar']
        # Pine 4969
        e['prevAsiaLowBar'] = e['asiaLowBar']
        # Pine 4971
        e['asiaHighBar'] = e['bar_index']
        # Pine 4972
        e['asiaLowBar'] = e['bar_index']
        # Pine 4973
        e['asiaHigh'] = e['h']
        # Pine 4974
        e['asiaLow'] = e['l']
    # Pine 4976
    elif rt.truth(e['asiaSession']):
        # Pine 4977
        if rt.truth((rt.truth(rt.is_na(e['asiaHigh'])) or rt.truth(rt.binary('>', e['h'], e['asiaHigh'])))):
            # Pine 4978
            e['asiaHigh'] = e['h']
            # Pine 4979
            e['asiaHighBar'] = e['bar_index']
        # Pine 4981
        if rt.truth((rt.truth(rt.is_na(e['asiaLow'])) or rt.truth(rt.binary('<', e['l'], e['asiaLow'])))):
            # Pine 4982
            e['asiaLow'] = e['l']
            # Pine 4983
            e['asiaLowBar'] = e['bar_index']
    # Pine 5030
    e['asiaRange'] = (rt.binary('-', e['asiaHigh'], e['asiaLow']) if rt.truth((rt.truth((not rt.truth(rt.is_na(e['asiaHigh'])))) and rt.truth((not rt.truth(rt.is_na(e['asiaLow'])))))) else rt.NA)
    # Pine 5033
    e['prevAsiaRange'] = (rt.binary('-', e['prevAsiaHigh'], e['prevAsiaLow']) if rt.truth((rt.truth((not rt.truth(rt.is_na(e['prevAsiaHigh'])))) and rt.truth((not rt.truth(rt.is_na(e['prevAsiaLow'])))))) else rt.NA)

def update_london_session(e):
    # Pine 4986
    e['newLondonSession'] = (rt.truth(e['londonSession']) and rt.truth((not rt.truth(e.previous('londonSession', 1)))))
    # Pine 4987
    if rt.truth(e['newLondonSession']):
        # Pine 4988
        e['prevLondonHigh'] = e['londonHigh']
        # Pine 4989
        e['prevLondonLow'] = e['londonLow']
        # Pine 4990
        e['prevLondonHighBar'] = e['londonHighBar']
        # Pine 4991
        e['prevLondonLowBar'] = e['londonLowBar']
        # Pine 4993
        e['londonHighBar'] = e['bar_index']
        # Pine 4994
        e['londonLowBar'] = e['bar_index']
        # Pine 4995
        e['londonHigh'] = e['h']
        # Pine 4996
        e['londonLow'] = e['l']
    # Pine 4998
    elif rt.truth(e['londonSession']):
        # Pine 4999
        if rt.truth((rt.truth(rt.is_na(e['londonHigh'])) or rt.truth(rt.binary('>', e['h'], e['londonHigh'])))):
            # Pine 5000
            e['londonHigh'] = e['h']
            # Pine 5001
            e['londonHighBar'] = e['bar_index']
        # Pine 5003
        if rt.truth((rt.truth(rt.is_na(e['londonLow'])) or rt.truth(rt.binary('<', e['l'], e['londonLow'])))):
            # Pine 5004
            e['londonLow'] = e['l']
            # Pine 5005
            e['londonLowBar'] = e['bar_index']
    # Pine 5031
    e['londonRange'] = (rt.binary('-', e['londonHigh'], e['londonLow']) if rt.truth((rt.truth((not rt.truth(rt.is_na(e['londonHigh'])))) and rt.truth((not rt.truth(rt.is_na(e['londonLow'])))))) else rt.NA)
    # Pine 5034
    e['prevLondonRange'] = (rt.binary('-', e['prevLondonHigh'], e['prevLondonLow']) if rt.truth((rt.truth((not rt.truth(rt.is_na(e['prevLondonHigh'])))) and rt.truth((not rt.truth(rt.is_na(e['prevLondonLow'])))))) else rt.NA)

def update_newyork_session(e):
    # Pine 5008
    e['newNewYorkSession'] = (rt.truth(e['newYorkSession']) and rt.truth((not rt.truth(e.previous('newYorkSession', 1)))))
    # Pine 5009
    if rt.truth(e['newNewYorkSession']):
        # Pine 5010
        e['prevNewYorkHigh'] = e['newYorkHigh']
        # Pine 5011
        e['prevNewYorkLow'] = e['newYorkLow']
        # Pine 5012
        e['prevNewYorkHighBar'] = e['newYorkHighBar']
        # Pine 5013
        e['prevNewYorkLowBar'] = e['newYorkLowBar']
        # Pine 5015
        e['newYorkHighBar'] = e['bar_index']
        # Pine 5016
        e['newYorkLowBar'] = e['bar_index']
        # Pine 5017
        e['newYorkHigh'] = e['h']
        # Pine 5018
        e['newYorkLow'] = e['l']
    # Pine 5020
    elif rt.truth(e['newYorkSession']):
        # Pine 5021
        if rt.truth((rt.truth(rt.is_na(e['newYorkHigh'])) or rt.truth(rt.binary('>', e['h'], e['newYorkHigh'])))):
            # Pine 5022
            e['newYorkHigh'] = e['h']
            # Pine 5023
            e['newYorkHighBar'] = e['bar_index']
        # Pine 5025
        if rt.truth((rt.truth(rt.is_na(e['newYorkLow'])) or rt.truth(rt.binary('<', e['l'], e['newYorkLow'])))):
            # Pine 5026
            e['newYorkLow'] = e['l']
            # Pine 5027
            e['newYorkLowBar'] = e['bar_index']
    # Pine 5032
    e['newYorkRange'] = (rt.binary('-', e['newYorkHigh'], e['newYorkLow']) if rt.truth((rt.truth((not rt.truth(rt.is_na(e['newYorkHigh'])))) and rt.truth((not rt.truth(rt.is_na(e['newYorkLow'])))))) else rt.NA)
    # Pine 5035
    e['prevNewYorkRange'] = (rt.binary('-', e['prevNewYorkHigh'], e['prevNewYorkLow']) if rt.truth((rt.truth((not rt.truth(rt.is_na(e['prevNewYorkHigh'])))) and rt.truth((not rt.truth(rt.is_na(e['prevNewYorkLow'])))))) else rt.NA)

def update_nearest_session_levels(e):
    # Pine 5038
    e['nearestHighPrice'] = rt.NA
    # Pine 5039
    e['nearestHighPriceBar'] = rt.NA
    # Pine 5040
    e['nearestHighPriceSession'] = ''
    # Pine 5041
    e['nearestHighPriceDistance'] = rt.NA
    # Pine 5043
    e['nearestLowPrice'] = rt.NA
    # Pine 5044
    e['nearestLowPriceBar'] = rt.NA
    # Pine 5045
    e['nearestLowPriceSession'] = ''
    # Pine 5046
    e['nearestLowPriceDistance'] = rt.NA
    # Pine 5049
    if rt.truth((not rt.truth(rt.is_na(e['asiaHigh'])))):
        # Pine 5050
        e['d'] = rt.math_abs(rt.binary('-', e['c'], e['asiaHigh']))
        # Pine 5051
        if rt.truth((rt.truth(rt.is_na(e['nearestHighPriceDistance'])) or rt.truth(rt.binary('<', e['d'], e['nearestHighPriceDistance'])))):
            # Pine 5052
            e['nearestHighPriceDistance'] = e['d']
            # Pine 5053
            e['nearestHighPrice'] = e['asiaHigh']
            # Pine 5054
            e['nearestHighPriceBar'] = e['asiaHighBar']
            # Pine 5055
            e['nearestHighPriceSession'] = 'ASIA'
    # Pine 5057
    if rt.truth((not rt.truth(rt.is_na(e['londonHigh'])))):
        # Pine 5058
        e['d'] = rt.math_abs(rt.binary('-', e['c'], e['londonHigh']))
        # Pine 5059
        if rt.truth((rt.truth(rt.is_na(e['nearestHighPriceDistance'])) or rt.truth(rt.binary('<', e['d'], e['nearestHighPriceDistance'])))):
            # Pine 5060
            e['nearestHighPriceDistance'] = e['d']
            # Pine 5061
            e['nearestHighPrice'] = e['londonHigh']
            # Pine 5062
            e['nearestHighPriceBar'] = e['londonHighBar']
            # Pine 5063
            e['nearestHighPriceSession'] = 'LONDON'
    # Pine 5065
    if rt.truth((not rt.truth(rt.is_na(e['newYorkHigh'])))):
        # Pine 5066
        e['d'] = rt.math_abs(rt.binary('-', e['c'], e['newYorkHigh']))
        # Pine 5067
        if rt.truth((rt.truth(rt.is_na(e['nearestHighPriceDistance'])) or rt.truth(rt.binary('<', e['d'], e['nearestHighPriceDistance'])))):
            # Pine 5068
            e['nearestHighPriceDistance'] = e['d']
            # Pine 5069
            e['nearestHighPrice'] = e['newYorkHigh']
            # Pine 5070
            e['nearestHighPriceBar'] = e['newYorkHighBar']
            # Pine 5071
            e['nearestHighPriceSession'] = 'NEW_YORK'
    # Pine 5074
    if rt.truth((not rt.truth(rt.is_na(e['asiaLow'])))):
        # Pine 5075
        e['d'] = rt.math_abs(rt.binary('-', e['c'], e['asiaLow']))
        # Pine 5076
        if rt.truth((rt.truth(rt.is_na(e['nearestLowPriceDistance'])) or rt.truth(rt.binary('<', e['d'], e['nearestLowPriceDistance'])))):
            # Pine 5077
            e['nearestLowPriceDistance'] = e['d']
            # Pine 5078
            e['nearestLowPrice'] = e['asiaLow']
            # Pine 5079
            e['nearestLowPriceBar'] = e['asiaLowBar']
            # Pine 5080
            e['nearestLowPriceSession'] = 'ASIA'
    # Pine 5082
    if rt.truth((not rt.truth(rt.is_na(e['londonLow'])))):
        # Pine 5083
        e['d'] = rt.math_abs(rt.binary('-', e['c'], e['londonLow']))
        # Pine 5084
        if rt.truth((rt.truth(rt.is_na(e['nearestLowPriceDistance'])) or rt.truth(rt.binary('<', e['d'], e['nearestLowPriceDistance'])))):
            # Pine 5085
            e['nearestLowPriceDistance'] = e['d']
            # Pine 5086
            e['nearestLowPrice'] = e['londonLow']
            # Pine 5087
            e['nearestLowPriceBar'] = e['londonLowBar']
            # Pine 5088
            e['nearestLowPriceSession'] = 'LONDON'
    # Pine 5090
    if rt.truth((not rt.truth(rt.is_na(e['newYorkLow'])))):
        # Pine 5091
        e['d'] = rt.math_abs(rt.binary('-', e['c'], e['newYorkLow']))
        # Pine 5092
        if rt.truth((rt.truth(rt.is_na(e['nearestLowPriceDistance'])) or rt.truth(rt.binary('<', e['d'], e['nearestLowPriceDistance'])))):
            # Pine 5093
            e['nearestLowPriceDistance'] = e['d']
            # Pine 5094
            e['nearestLowPrice'] = e['newYorkLow']
            # Pine 5095
            e['nearestLowPriceBar'] = e['newYorkLowBar']
            # Pine 5096
            e['nearestLowPriceSession'] = 'NEW_YORK'

def update(e):
    update_session_clock(e)
    update_asia_session(e)
    update_london_session(e)
    update_newyork_session(e)
    update_nearest_session_levels(e)
