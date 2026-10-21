"""Liquidity. Generated main-feature implementation.
Stages execute in manifest dependency order; see individual/README.md."""
from . import runtime as rt

def update_liquidity_pools(e):
    # Pine 4123
    e['bidAbsorption'] = False
    # Pine 4124
    e['askAbsorption'] = False
    # Pine 4126
    e['bidAbsorptionStrength'] = 0.0
    # Pine 4127
    e['askAbsorptionStrength'] = 0.0
    # Pine 4128
    e['nearestBuyLiquidityPriceDistance'] = rt.NA
    # Pine 4129
    e['nearestBuyLiquidityATRDistance'] = rt.NA
    # Pine 4130
    e['nearestSellLiquidityPriceDistance'] = rt.NA
    # Pine 4131
    e['nearestSellLiquidityATRDistance'] = rt.NA
    # Pine 4134
    e['recentHighLiquidity'] = e.ta('highest', '4134', e['h'], e['liquidityLookback'])
    # Pine 4135
    e['recentLowLiquidity'] = e.ta('lowest', '4135', e['l'], e['liquidityLookback'])
    # Pine 4136
    e['prevLowLiquidity'] = e.ta('lowest', '4136', e['l1'], e['liquidityLookback'])
    # Pine 4137
    e['prevHighLiquidity'] = e.ta('highest', '4137', e['h1'], e['liquidityLookback'])
    # Pine 4140
    e['liquidityHighDistance'] = (rt.binary('*', rt.binary('/', rt.binary('-', e['recentHighLiquidity'], e['c']), e['c']), 100) if rt.truth((not rt.truth(rt.is_na(e['recentHighLiquidity'])))) else rt.NA)
    # Pine 4141
    e['liquidityLowDistance'] = (rt.binary('*', rt.binary('/', rt.binary('-', e['c'], e['recentLowLiquidity']), e['c']), 100) if rt.truth((not rt.truth(rt.is_na(e['recentLowLiquidity'])))) else rt.NA)
    # Pine 4144
    e['equalHighLiquidity'] = rt.binary('<', rt.binary('/', rt.math_abs(rt.binary('-', e['h'], e['h1'])), e['c']), 0.001)
    # Pine 4145
    e['equalLowLiquidity'] = rt.binary('<', rt.binary('/', rt.math_abs(rt.binary('-', e['l'], e['l1'])), e['c']), 0.001)

def update_liquidity_sweeps(e):
    # Pine 4151
    e['bullSweepDetected'] = rt.binary('<', e['l'], e['prevLowLiquidity'])
    # Pine 4152
    e['bullSweepReclaim'] = (rt.truth(e['bullSweepDetected']) and rt.truth(rt.binary('>', e['c'], e.previous('recentLowLiquidity', 1))))
    # Pine 4156
    e['bearSweepDetected'] = rt.binary('>', e['h'], e['prevHighLiquidity'])
    # Pine 4157
    e['bearSweepReject'] = (rt.truth(e['bearSweepDetected']) and rt.truth(rt.binary('<', e['c'], e.previous('recentHighLiquidity', 1))))
    # Pine 4160
    e['bullSweepStrength'] = (rt.math_min(rt.binary('/', rt.math_abs(rt.binary('-', e.previous('recentLowLiquidity', 1), e['l'])), e['atr']), 5) if rt.truth(e['bullSweepDetected']) else 0)
    # Pine 4161
    e['bearSweepStrength'] = (rt.math_min(rt.binary('/', rt.math_abs(rt.binary('-', e['h'], e.previous('recentHighLiquidity', 1))), e['atr']), 5) if rt.truth(e['bearSweepDetected']) else 0)

def update_absorption(e):
    # Pine 4164
    e['elevatedVolume'] = (rt.truth((not rt.truth(rt.is_na(e['volumeMA'])))) and rt.truth(rt.binary('>=', e['volume'], rt.binary('*', e['volumeMA'], 1.5))))
    # Pine 4165
    e['supportInteraction'] = (rt.truth((rt.truth((not rt.truth(rt.is_na(e['supportHigh'])))) and rt.truth(rt.binary('<=', e['l'], e['supportHigh'])))) and rt.truth(rt.binary('>=', e['c'], e['supportHigh'])))
    # Pine 4166
    e['resistanceInteraction'] = (rt.truth((rt.truth((not rt.truth(rt.is_na(e['resistanceLow'])))) and rt.truth(rt.binary('>=', e['h'], e['resistanceLow'])))) and rt.truth(rt.binary('<=', e['c'], e['resistanceLow'])))
    # Pine 4167
    e['bullishRejection'] = (rt.truth((rt.truth(rt.binary('>', e['candleRange'], 0)) and rt.truth(rt.binary('>=', rt.binary('/', e['lowerWick'], e['candleRange']), 0.35)))) and rt.truth(rt.binary('>', e['c'], e['o'])))
    # Pine 4168
    e['bearishRejection'] = (rt.truth((rt.truth(rt.binary('>', e['candleRange'], 0)) and rt.truth(rt.binary('>=', rt.binary('/', e['upperWick'], e['candleRange']), 0.35)))) and rt.truth(rt.binary('<', e['c'], e['o'])))
    # Pine 4170
    e['bidAbsorption'] = (rt.truth((rt.truth(e['supportInteraction']) and rt.truth(e['elevatedVolume']))) and rt.truth(e['bullishRejection']))
    # Pine 4171
    e['askAbsorption'] = (rt.truth((rt.truth(e['resistanceInteraction']) and rt.truth(e['elevatedVolume']))) and rt.truth(e['bearishRejection']))
    # Pine 4174
    e['bidAbsorptionStrength'] = 0.0
    # Pine 4175
    e['askAbsorptionStrength'] = 0.0
    # Pine 4177
    if rt.truth(e['bidAbsorption']):
        # Pine 4178
        e['bidAbsorptionStrength'] = rt.binary('+', e['bidAbsorptionStrength'], rt.math_min(rt.binary('*', e['volumeRatio'], 20.0), 30.0))
        # Pine 4179
        e['bidAbsorptionStrength'] = rt.binary('+', e['bidAbsorptionStrength'], rt.math_min(rt.binary('*', e['wickRatio'], 50.0), 30.0))
        # Pine 4181
        if rt.truth(e['bullSweepDetected']):
            # Pine 4182
            e['bidAbsorptionStrength'] = rt.binary('+', e['bidAbsorptionStrength'], 20.0)
        # Pine 4184
        if rt.truth(e['bullSweepReclaim']):
            # Pine 4185
            e['bidAbsorptionStrength'] = rt.binary('+', e['bidAbsorptionStrength'], 20.0)
        # Pine 4187
        e['bidAbsorptionStrength'] = rt.math_min(e['bidAbsorptionStrength'], 100.0)
    # Pine 4189
    if rt.truth(e['askAbsorption']):
        # Pine 4190
        e['askAbsorptionStrength'] = rt.binary('+', e['askAbsorptionStrength'], rt.math_min(rt.binary('*', e['volumeRatio'], 20.0), 30.0))
        # Pine 4191
        e['askAbsorptionStrength'] = rt.binary('+', e['askAbsorptionStrength'], rt.math_min(rt.binary('*', e['wickRatio'], 50.0), 30.0))
        # Pine 4193
        if rt.truth(e['bearSweepDetected']):
            # Pine 4194
            e['askAbsorptionStrength'] = rt.binary('+', e['askAbsorptionStrength'], 20.0)
        # Pine 4196
        if rt.truth(e['bearSweepReject']):
            # Pine 4197
            e['askAbsorptionStrength'] = rt.binary('+', e['askAbsorptionStrength'], 20.0)
        # Pine 4199
        e['askAbsorptionStrength'] = rt.math_min(e['askAbsorptionStrength'], 100.0)

def update_liquidity_type(e):
    # Pine 4202
    e['liquidityType'] = ('SELL_SIDE_EQUAL_LOW' if rt.truth((rt.truth(e['equalLowLiquidity']) and rt.truth(e['bullSweepDetected']))) else ('BUY_SIDE_EQUAL_HIGH' if rt.truth((rt.truth(e['equalHighLiquidity']) and rt.truth(e['bearSweepDetected']))) else ('SELL_SIDE_SWEEP' if rt.truth(e['bullSweepDetected']) else ('BUY_SIDE_SWEEP' if rt.truth(e['bearSweepDetected']) else 'NONE'))))

def update_external_liquidity(e):
    # Pine 4220
    e['externalLiquidityLookback'] = 200
    # Pine 4221
    e['internalLiquidityLookback'] = 50
    # Pine 4222
    e['liquidityClusterTolerance'] = 0.002
    # Pine 4229
    e['externalHighLiquidity'] = e.ta('highest', '4229', e['h'], e['externalLiquidityLookback'])
    # Pine 4230
    e['externalLowLiquidity'] = e.ta('lowest', '4230', e['l'], e['externalLiquidityLookback'])
    # Pine 4233
    e['externalHighDistancePct'] = (rt.binary('*', rt.binary('/', rt.math_abs(rt.binary('-', e['externalHighLiquidity'], e['c'])), e['c']), 100) if rt.truth((not rt.truth(rt.is_na(e['externalHighLiquidity'])))) else rt.NA)
    # Pine 4234
    e['externalHighDistance'] = (rt.math_abs(rt.binary('-', e['externalHighLiquidity'], e['c'])) if rt.truth((not rt.truth(rt.is_na(e['externalHighLiquidity'])))) else rt.NA)
    # Pine 4235
    e['externalLowDistancePct'] = (rt.binary('*', rt.binary('/', rt.math_abs(rt.binary('-', e['c'], e['externalLowLiquidity'])), e['c']), 100) if rt.truth((not rt.truth(rt.is_na(e['externalLowLiquidity'])))) else rt.NA)
    # Pine 4236
    e['externalLowDistance'] = (rt.math_abs(rt.binary('-', e['c'], e['externalLowLiquidity'])) if rt.truth((not rt.truth(rt.is_na(e['externalLowLiquidity'])))) else rt.NA)

def update_internal_liquidity(e):
    # Pine 4240
    e['internalHighLiquidity'] = e.ta('highest', '4240', e['h'], e['internalLiquidityLookback'])
    # Pine 4241
    e['internalLowLiquidity'] = e.ta('lowest', '4241', e['l'], e['internalLiquidityLookback'])
    # Pine 4242
    e['internalHighDistancePct'] = (rt.binary('*', rt.binary('/', rt.math_abs(rt.binary('-', e['internalHighLiquidity'], e['c'])), e['c']), 100) if rt.truth((not rt.truth(rt.is_na(e['internalHighLiquidity'])))) else rt.NA)
    # Pine 4243
    e['internalHighDistance'] = (rt.math_abs(rt.binary('-', e['internalHighLiquidity'], e['c'])) if rt.truth((not rt.truth(rt.is_na(e['internalHighLiquidity'])))) else rt.NA)
    # Pine 4244
    e['internalLowDistance'] = (rt.binary('*', rt.binary('/', rt.math_abs(rt.binary('-', e['c'], e['internalLowLiquidity'])), e['c']), 100) if rt.truth((not rt.truth(rt.is_na(e['internalLowLiquidity'])))) else rt.NA)

def update_liquidity_clusters(e):
    # Pine 4253
    e['highClusterCount'] = 0
    # Pine 4254
    e['lowClusterCount'] = 0
    # Pine 4256
    for e['i'] in rt.inclusive(1, 50):
        # Pine 4257
        if rt.truth(rt.binary('<=', rt.binary('/', rt.math_abs(rt.binary('-', e.previous('h', e['i']), e['externalHighLiquidity'])), e['c']), e['liquidityClusterTolerance'])):
            # Pine 4258
            e['highClusterCount'] = rt.binary('+', e['highClusterCount'], 1)
        # Pine 4260
        if rt.truth(rt.binary('<=', rt.binary('/', rt.math_abs(rt.binary('-', e.previous('l', e['i']), e['externalLowLiquidity'])), e['c']), e['liquidityClusterTolerance'])):
            # Pine 4261
            e['lowClusterCount'] = rt.binary('+', e['lowClusterCount'], 1)
    # Pine 4263
    e['highLiquidityClusterScore'] = rt.math_min(rt.binary('/', e['highClusterCount'], 3), 5)
    # Pine 4264
    e['lowLiquidityClusterScore'] = rt.math_min(rt.binary('/', e['lowClusterCount'], 3), 5)
    # Pine 4265
    e['highLiquidityCluster'] = rt.binary('>=', e['highLiquidityClusterScore'], 2)
    # Pine 4266
    e['lowLiquidityCluster'] = rt.binary('>=', e['lowLiquidityClusterScore'], 2)

def update_liquidity_age(e):
    # Pine 4274
    e['highLiquidityAge'] = rt.NA
    # Pine 4275
    e['lowLiquidityAge'] = rt.NA
    # Pine 4277
    for e['i'] in rt.inclusive(1, e['externalLiquidityLookback']):
        # Pine 4278
        if rt.truth((rt.truth(rt.is_na(e['highLiquidityAge'])) and rt.truth(rt.binary('<', rt.binary('/', rt.math_abs(rt.binary('-', e.previous('h', e['i']), e['externalHighLiquidity'])), e['c']), 0.0005)))):
            # Pine 4279
            e['highLiquidityAge'] = e['i']
        # Pine 4281
        if rt.truth((rt.truth(rt.is_na(e['lowLiquidityAge'])) and rt.truth(rt.binary('<', rt.binary('/', rt.math_abs(rt.binary('-', e.previous('l', e['i']), e['externalLowLiquidity'])), e['c']), 0.0005)))):
            # Pine 4282
            e['lowLiquidityAge'] = e['i']

def update_liquidity_importance(e):
    # Pine 4289
    e['highLiquidityImportance'] = 0.0
    # Pine 4290
    e['lowLiquidityImportance'] = 0.0
    # Pine 4293
    if rt.truth((not rt.truth(rt.is_na(e['externalHighDistancePct'])))):
        # Pine 4294
        e['highLiquidityImportance'] = rt.binary('+', e['highLiquidityImportance'], rt.math_max(0, rt.binary('-', 5, e['externalHighDistancePct'])))
    # Pine 4296
    if rt.truth((not rt.truth(rt.is_na(e['externalLowDistance'])))):
        # Pine 4297
        e['lowLiquidityImportance'] = rt.binary('+', e['lowLiquidityImportance'], rt.math_max(0, rt.binary('-', 5, e['externalLowDistancePct'])))
    # Pine 4299
    e['liquidityMaxDistancePct'] = 5.0
    # Pine 4302
    e['liquidityClusterImportance'] = 2.0
    # Pine 4304
    if rt.truth(e['highLiquidityCluster']):
        # Pine 4305
        e['highLiquidityImportance'] = rt.binary('+', e['highLiquidityImportance'], e['liquidityClusterImportance'])
    # Pine 4307
    if rt.truth(e['lowLiquidityCluster']):
        # Pine 4308
        e['lowLiquidityImportance'] = rt.binary('+', e['lowLiquidityImportance'], e['liquidityClusterImportance'])
    # Pine 4311
    if rt.truth((not rt.truth(rt.is_na(e['highLiquidityAge'])))):
        # Pine 4312
        e['highLiquidityImportance'] = rt.binary('+', e['highLiquidityImportance'], rt.math_min(rt.binary('/', e['highLiquidityAge'], 50), 3))
    # Pine 4314
    if rt.truth((not rt.truth(rt.is_na(e['lowLiquidityAge'])))):
        # Pine 4315
        e['lowLiquidityImportance'] = rt.binary('+', e['lowLiquidityImportance'], rt.math_min(rt.binary('/', e['lowLiquidityAge'], 50), 3))
    # Pine 4318
    e['highLiquidityImportance'] = rt.math_min(e['highLiquidityImportance'], 10)
    # Pine 4319
    e['lowLiquidityImportance'] = rt.math_min(e['lowLiquidityImportance'], 10)
    # Pine 4322
    e['liquidityLocation'] = ('BOTH_CLUSTER' if rt.truth((rt.truth(e['highLiquidityCluster']) and rt.truth(e['lowLiquidityCluster']))) else ('BUY_SIDE_CLUSTER' if rt.truth(e['highLiquidityCluster']) else ('SELL_SIDE_CLUSTER' if rt.truth(e['lowLiquidityCluster']) else 'NO_CLUSTER')))
    # Pine 4331
    e['liquiditySide'] = ('SELL_SIDE_NEAR' if rt.truth(rt.binary('<', e['c'], e['externalLowLiquidity'])) else ('BUY_SIDE_NEAR' if rt.truth(rt.binary('>', e['c'], e['externalHighLiquidity'])) else 'MID_RANGE'))

def update_nearest_liquidity(e):
    # Pine 4334
    e['nearestBuyLiquidityPct'] = rt.NA
    # Pine 4335
    e['nearestSellLiquidityPct'] = rt.NA
    # Pine 4336
    e['nearestBuyLiquidityPrice'] = rt.NA
    # Pine 4337
    e['nearestSellLiquidityPrice'] = rt.NA
    # Pine 4340
    if rt.truth((rt.truth((not rt.truth(rt.is_na(e['internalHighDistancePct'])))) and rt.truth((not rt.truth(rt.is_na(e['externalHighDistancePct'])))))):
        # Pine 4341
        e['nearestBuyLiquidityPct'] = rt.math_min(e['internalHighDistancePct'], e['externalHighDistancePct'])
    # Pine 4342
    elif rt.truth((not rt.truth(rt.is_na(e['internalHighDistancePct'])))):
        # Pine 4343
        e['nearestBuyLiquidityPct'] = e['internalHighDistancePct']
    # Pine 4344
    elif rt.truth((not rt.truth(rt.is_na(e['externalHighDistancePct'])))):
        # Pine 4345
        e['nearestBuyLiquidityPct'] = e['externalHighDistancePct']
    # Pine 4347
    if rt.truth((rt.truth((rt.truth((not rt.truth(rt.is_na(e['nearestBuyLiquidityPct'])))) and rt.truth((not rt.truth(rt.is_na(e['atr'])))))) and rt.truth(rt.binary('>', e['c'], 0)))):
        # Pine 4348
        e['nearestBuyLiquidityPriceDistance'] = rt.binary('/', rt.binary('*', e['c'], e['nearestBuyLiquidityPct']), 100.0)
        # Pine 4349
        e['nearestBuyLiquidityPrice'] = rt.binary('+', e['c'], e['nearestBuyLiquidityPriceDistance'])
        # Pine 4350
        e['nearestBuyLiquidityATRDistance'] = rt.binary('/', e['nearestBuyLiquidityPriceDistance'], e['atr'])
    # Pine 4353
    if rt.truth((rt.truth((not rt.truth(rt.is_na(e['internalLowDistance'])))) and rt.truth((not rt.truth(rt.is_na(e['externalLowDistancePct'])))))):
        # Pine 4354
        e['nearestSellLiquidityPct'] = rt.math_min(e['internalLowDistance'], e['externalLowDistancePct'])
    # Pine 4355
    elif rt.truth((not rt.truth(rt.is_na(e['internalLowDistance'])))):
        # Pine 4356
        e['nearestSellLiquidityPct'] = e['internalLowDistance']
    # Pine 4357
    elif rt.truth((not rt.truth(rt.is_na(e['externalLowDistancePct'])))):
        # Pine 4358
        e['nearestSellLiquidityPct'] = e['externalLowDistancePct']
    # Pine 4360
    if rt.truth((rt.truth((rt.truth((not rt.truth(rt.is_na(e['nearestSellLiquidityPct'])))) and rt.truth((not rt.truth(rt.is_na(e['atr'])))))) and rt.truth(rt.binary('>', e['c'], 0)))):
        # Pine 4361
        e['nearestSellLiquidityPriceDistance'] = rt.binary('/', rt.binary('*', e['c'], e['nearestSellLiquidityPct']), 100.0)
        # Pine 4362
        e['nearestSellLiquidityPrice'] = rt.binary('-', e['c'], e['nearestSellLiquidityPriceDistance'])
        # Pine 4363
        e['nearestSellLiquidityATRDistance'] = rt.binary('/', e['nearestSellLiquidityPriceDistance'], e['atr'])

def update(e):
    update_liquidity_pools(e)
    update_liquidity_sweeps(e)
    update_absorption(e)
    update_liquidity_type(e)
    update_external_liquidity(e)
    update_internal_liquidity(e)
    update_liquidity_clusters(e)
    update_liquidity_age(e)
    update_liquidity_importance(e)
    update_nearest_liquidity(e)
