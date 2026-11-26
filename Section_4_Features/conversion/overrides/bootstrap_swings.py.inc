    # Pine 2788
    if rt.truth(e['barstate.isconfirmed']):
        # Pine 2789
        if rt.truth(rt.binary('==', e['candidatePivot'], 0)):
            # Pine 2790
            if rt.truth(rt.binary('>', e['h'], e.previous('h', 1))):
                # Pine 2791
                e['candidatePivot'] = 1
                # Pine 2792
                e['candidatePivotHighPrice'] = e['h']
                # Pine 2793
                e['candidatePivotHighBar'] = e['bar_index']
                # Pine 2794
                e['candidatePivotHighTime'] = e['time']
                # Pine 2795
                e['currentSwingDirection'] = 'SWING_UP'
                # Pine 2796
                e['candidatePivotLowPrice'] = e.previous('l', 1)
            # Pine 2797
            elif rt.truth(rt.binary('<', e['l'], e.previous('l', 1))):
                # Pine 2798
                e['candidatePivot'] = rt.neg(1)
                # Pine 2799
                e['candidatePivotLowPrice'] = e['l']
                # Pine 2800
                e['candidatePivotLowBar'] = e['bar_index']
                # Pine 2801
                e['candidatePivotLowTime'] = e['time']
                # Pine 2802
                e['currentSwingDirection'] = 'SWING_DOWN'
                # Pine 2803
                e['candidatePivotHighPrice'] = e.previous('h', 1)
    # Pine 2805
    if rt.truth((rt.truth(e['barstate.isconfirmed']) and rt.truth(rt.binary('==', e['candidatePivot'], 1)))):
        # Pine 2806
        if rt.truth(rt.binary('>', e['h'], e['candidatePivotHighPrice'])):
            # Pine 2807
            e['prevCandidatePivotHighBar'] = e['candidatePivotHighBar']
            # Pine 2808
            e['candidatePivotHighPrice'] = e['h']
            # Pine 2809
            e['candidatePivotHighBar'] = e['bar_index']
            # Pine 2810
            e['candidatePivotHighTime'] = e['time']
            # Pine 2811
            e['currentSwingDirection'] = 'SWING_UP'
            # Pine 2812
            e['swingTransition'] = 0
    # Pine 2814
    e['swingLowCount'] = rt.arr_size(e['swingLowPriceArray'])
    # Pine 2815
    if rt.truth((rt.truth(rt.binary('==', e['candidatePivot'], 1)) and rt.truth((rt.truth(rt.binary('>', e['swingLowCount'], 0)) or rt.truth((not rt.truth(rt.is_na(e['candidatePivotLowPrice'])))))))):
        # Pine 2816
        e['latestConfirmedPivotLow'] = (rt.arr_get(e['swingLowPriceArray'], rt.binary('-', e['swingLowCount'], 1)) if rt.truth(rt.binary('>', e['swingLowCount'], 0)) else rt.NA)
        # Pine 2817
        e['swingDistance'] = rt.binary('-', e['candidatePivotHighPrice'], (e['latestConfirmedPivotLow'] if rt.truth(rt.binary('>', e['swingLowCount'], 0)) else e['candidatePivotLowPrice']))
        # Pine 2818
        e['validationDistance'] = rt.binary('*', e['swingDistance'], e['swingValidationRatio'])
        # Pine 2819
        e['pivotHighConfirmationPrice'] = rt.binary('-', e['candidatePivotHighPrice'], e['validationDistance'])
    # Pine 2821
    if rt.truth((rt.truth((rt.truth((rt.truth((rt.truth(e['barstate.isconfirmed']) and rt.truth(rt.binary('==', e['candidatePivot'], 1)))) and rt.truth(rt.binary('<', e['candidatePivotHighBar'], e['bar_index'])))) and rt.truth(rt.binary('<', e['h'], e['candidatePivotHighPrice'])))) and rt.truth(rt.binary('>', e['c'], e['pivotHighConfirmationPrice'])))):
        # Pine 2822
        e['currentSwingDirection'] = 'SWING_UP'
        # Pine 2823
        e['swingTransition'] = 1
    # Pine 2825
    elif rt.truth((rt.truth((rt.truth((rt.truth(e['barstate.isconfirmed']) and rt.truth(rt.binary('==', e['candidatePivot'], 1)))) and rt.truth(rt.binary('<', e['candidatePivotHighBar'], e['bar_index'])))) and rt.truth(rt.binary('<=', e['c'], e['pivotHighConfirmationPrice'])))):
        # Pine 2826
        e['lastConfirmedPivotType'] = 1
        # Pine 2827
        rt.arr_push(e['swingHighPriceArray'], e['candidatePivotHighPrice'])
        # Pine 2828
        rt.arr_push(e['swingHighBarArray'], e['candidatePivotHighBar'])
        # Pine 2829
        rt.arr_push(e['swingHighTimeArray'], e['candidatePivotHighTime'])
        e['structureEventState'], e['structureEventBuffer'] = event_export.pivot(e['structureEventState'], e['structureEventBuffer'], e.symbol, e.timeframe, e.current_client, 'high', e['candidatePivotHighPrice'], e['candidatePivotHighBar'], e['candidatePivotHighTime'])
        # Pine 2831
        e['activePivotCount'] = rt.arr_size(e['currentActivePivotTypeArray'])
        # Pine 2832
        if rt.truth(rt.binary('>', e['activePivotCount'], 0)):
            # Pine 2833
            rt.arr_push(e['prevActivePivotTypeArray'], rt.arr_get(e['currentActivePivotTypeArray'], rt.binary('-', e['activePivotCount'], 1)))
        # Pine 2834
        rt.arr_push(e['currentActivePivotTypeArray'], 1)
        # Pine 2836
        e['pivotHighConfirmationPrice'] = rt.NA
        # Pine 2837
        e['prevCandidatePivotHighBar'] = rt.NA
        # Pine 2838
        e['currentSwingDirection'] = 'SWING_DOWN'
        # Pine 2839
        e['candidatePivot'] = rt.neg(1)
        # Pine 2840
        e['swingTransition'] = 0
        # Pine 2841
        e['candidatePivotLowPrice'] = e['l']
        # Pine 2842
        e['candidatePivotLowBar'] = e['bar_index']
        # Pine 2843
        e['candidatePivotLowTime'] = e['time']
        # Pine 2844
        e['latestConfirmedPivotLow'] = rt.NA
    # Pine 2847
    if rt.truth((rt.truth(e['barstate.isconfirmed']) and rt.truth(rt.binary('==', e['candidatePivot'], rt.neg(1))))):
        # Pine 2848
        if rt.truth(rt.binary('<', e['l'], e['candidatePivotLowPrice'])):
            # Pine 2849
            e['prevCandidatePivotLowBar'] = e['candidatePivotLowBar']
            # Pine 2850
            e['candidatePivotLowPrice'] = e['low']
            # Pine 2851
            e['candidatePivotLowBar'] = e['bar_index']
            # Pine 2852
            e['candidatePivotLowTime'] = e['time']
            # Pine 2853
            e['currentSwingDirection'] = 'SWING_DOWN'
            # Pine 2854
            e['swingTransition'] = 0
    # Pine 2856
    e['swingHighCount'] = rt.arr_size(e['swingHighPriceArray'])
    # Pine 2857
    if rt.truth((rt.truth(rt.binary('==', e['candidatePivot'], rt.neg(1))) and rt.truth((rt.truth(rt.binary('>', e['swingHighCount'], 0)) or rt.truth((not rt.truth(rt.is_na(e['candidatePivotHighPrice'])))))))):
        # Pine 2858
        e['latestConfirmedPivotHigh'] = (rt.arr_get(e['swingHighPriceArray'], rt.binary('-', e['swingHighCount'], 1)) if rt.truth(rt.binary('>', e['swingHighCount'], 0)) else rt.NA)
        # Pine 2859
        e['swingDistance'] = rt.binary('-', (e['latestConfirmedPivotHigh'] if rt.truth(rt.binary('>', e['swingHighCount'], 0)) else e['candidatePivotHighPrice']), e['candidatePivotLowPrice'])
        # Pine 2860
        e['validationDistance'] = rt.binary('*', e['swingDistance'], e['swingValidationRatio'])
        # Pine 2861
        e['pivotLowConfirmationPrice'] = rt.binary('+', e['candidatePivotLowPrice'], e['validationDistance'])
    # Pine 2863
    if rt.truth((rt.truth((rt.truth((rt.truth((rt.truth(e['barstate.isconfirmed']) and rt.truth(rt.binary('==', e['candidatePivot'], rt.neg(1))))) and rt.truth(rt.binary('<', e['candidatePivotLowBar'], e['bar_index'])))) and rt.truth(rt.binary('>', e['l'], e['candidatePivotLowPrice'])))) and rt.truth(rt.binary('<', e['c'], e['pivotLowConfirmationPrice'])))):
        # Pine 2864
        e['currentSwingDirection'] = 'SWING_DOWN'
        # Pine 2865
        e['swingTransition'] = 1
    # Pine 2867
    elif rt.truth((rt.truth((rt.truth((rt.truth(e['barstate.isconfirmed']) and rt.truth(rt.binary('==', e['candidatePivot'], rt.neg(1))))) and rt.truth(rt.binary('<', e['candidatePivotLowBar'], e['bar_index'])))) and rt.truth(rt.binary('>=', e['c'], e['pivotLowConfirmationPrice'])))):
        # Pine 2868
        e['lastConfirmedPivotType'] = rt.neg(1)
        # Pine 2869
        rt.arr_push(e['swingLowPriceArray'], e['candidatePivotLowPrice'])
        # Pine 2870
        rt.arr_push(e['swingLowBarArray'], e['candidatePivotLowBar'])
        # Pine 2871
        rt.arr_push(e['swingLowTimeArray'], e['candidatePivotLowTime'])
        e['structureEventState'], e['structureEventBuffer'] = event_export.pivot(e['structureEventState'], e['structureEventBuffer'], e.symbol, e.timeframe, e.current_client, 'low', e['candidatePivotLowPrice'], e['candidatePivotLowBar'], e['candidatePivotLowTime'])
        # Pine 2873
        e['activePivotCount'] = rt.arr_size(e['currentActivePivotTypeArray'])
        # Pine 2874
        if rt.truth(rt.binary('>', e['activePivotCount'], 0)):
            # Pine 2875
            rt.arr_push(e['prevActivePivotTypeArray'], rt.arr_get(e['currentActivePivotTypeArray'], rt.binary('-', e['activePivotCount'], 1)))
        # Pine 2876
        rt.arr_push(e['currentActivePivotTypeArray'], rt.neg(1))
        # Pine 2878
        e['pivotLowConfirmationPrice'] = rt.NA
        # Pine 2879
        e['prevCandidatePivotLowBar'] = rt.NA
        # Pine 2880
        e['currentSwingDirection'] = 'SWING_UP'
        # Pine 2881
        e['candidatePivot'] = 1
        # Pine 2882
        e['swingTransition'] = 0
        # Pine 2883
        e['candidatePivotHighPrice'] = e['h']
        # Pine 2884
        e['candidatePivotHighBar'] = e['bar_index']
        # Pine 2885
        e['candidatePivotHighTime'] = e['time']
        # Pine 2886
        e['latestConfirmedPivotHigh'] = rt.NA
