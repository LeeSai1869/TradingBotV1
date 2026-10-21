"""Support Resistance. Generated main-feature implementation.
Stages execute in manifest dependency order; see individual/README.md."""
from . import runtime as rt

def update_zone_geometry(e):
    # Pine 1041
    if 'nextSupportZoneSequence' not in e.persistent:
        e.initialize('nextSupportZoneSequence', 0)
    # Pine 1042
    if 'nextResistanceZoneSequence' not in e.persistent:
        e.initialize('nextResistanceZoneSequence', 0)
    # Pine 1044
    e['srZoneATRMultiplier'] = e.input('SR Zone ATR Multiplier', 0.5)
    # Pine 1045
    e['srMergeATRMultiplier'] = e.input('SR Merge ATR Multiplier', 0.25)
    # Pine 1046
    e['srZoneDistanceATR'] = e.input('SR Zone Distance ATR', 2.0)
    # Pine 1047
    e['srPivotLookback'] = e.input('S/R Pivot Lookback', 5)
    # Pine 1048
    e['srPivotRight'] = e.input('S/R Pivot Right', 1)
    # Pine 1049
    e['srReactionATR'] = e.input('S/R Reaction ATR', 0.5)
    # Pine 1050
    e['normalizationPower'] = e.input('S/R Normalization Power', 1.0)
    # Pine 1052
    e['srPivotHigh'] = e.ta('pivothigh', '1052', e['h'], e['srPivotLookback'], e['srPivotRight'])
    # Pine 1053
    e['srPivotLow'] = e.ta('pivotlow', '1053', e['l'], e['srPivotLookback'], e['srPivotRight'])
    # Pine 1055
    e['pivotATR'] = e.previous('atr', e['srPivotRight'])
    # Pine 1057
    e['support'] = e.ta('valuewhen', '1057', (not rt.truth(rt.is_na(e['srPivotLow']))), e['srPivotLow'], 0)
    # Pine 1058
    e['resistance'] = e.ta('valuewhen', '1058', (not rt.truth(rt.is_na(e['srPivotHigh']))), e['srPivotHigh'], 0)
    # Pine 1060
    e['srZoneSize'] = rt.binary('*', e['pivotATR'], e['srZoneATRMultiplier'])
    # Pine 1061
    e['srMergeDistance'] = rt.binary('*', e['pivotATR'], e['srMergeATRMultiplier'])
    # Pine 1063
    e['supportHigh'] = (rt.binary('+', e['support'], e['srZoneSize']) if rt.truth((not rt.truth(rt.is_na(e['support'])))) else rt.NA)
    # Pine 1064
    e['supportLow'] = (rt.binary('-', e['support'], e['srZoneSize']) if rt.truth((not rt.truth(rt.is_na(e['support'])))) else rt.NA)
    # Pine 1066
    e['resistanceHigh'] = (rt.binary('+', e['resistance'], e['srZoneSize']) if rt.truth((not rt.truth(rt.is_na(e['resistance'])))) else rt.NA)
    # Pine 1067
    e['resistanceLow'] = (rt.binary('-', e['resistance'], e['srZoneSize']) if rt.truth((not rt.truth(rt.is_na(e['resistance'])))) else rt.NA)
    # Pine 1069
    e['supportDistance'] = (rt.NA if rt.truth(rt.is_na(e['support'])) else (rt.binary('/', rt.binary('-', e['c'], e['support']), e['atr']) if rt.truth(rt.binary('>', e['atr'], 0)) else rt.NA))
    # Pine 1070
    e['resistanceDistance'] = (rt.NA if rt.truth(rt.is_na(e['resistance'])) else (rt.binary('/', rt.binary('-', e['resistance'], e['c']), e['atr']) if rt.truth(rt.binary('>', e['atr'], 0)) else rt.NA))
    # Pine 1072
    e['supportReactionATR'] = (rt.binary('/', rt.binary('-', e['c'], e['srPivotLow']), e['atr']) if rt.truth(rt.binary('>', e['atr'], 0)) else 0.0)
    # Pine 1073
    e['resistanceReactionATR'] = (rt.binary('/', rt.binary('-', e['srPivotHigh'], e['c']), e['atr']) if rt.truth(rt.binary('>', e['atr'], 0)) else 0.0)
    # Pine 1075
    e['sZoneDistanceATR'] = ((rt.binary('/', rt.binary('-', e['c'], e['supportHigh']), e['atr']) if rt.truth(rt.binary('>', e['c'], e['supportHigh'])) else (rt.binary('/', rt.binary('-', e['supportLow'], e['c']), e['atr']) if rt.truth(rt.binary('<', e['c'], e['supportLow'])) else 0.0)) if rt.truth((rt.truth((rt.truth(rt.binary('>', e['atr'], 0)) and rt.truth((not rt.truth(rt.is_na(e['supportHigh'])))))) and rt.truth((not rt.truth(rt.is_na(e['supportLow'])))))) else rt.NA)
    # Pine 1076
    e['rZoneDistanceATR'] = ((rt.binary('/', rt.binary('-', e['c'], e['resistanceHigh']), e['atr']) if rt.truth(rt.binary('>', e['c'], e['resistanceHigh'])) else (rt.binary('/', rt.binary('-', e['resistanceLow'], e['c']), e['atr']) if rt.truth(rt.binary('<', e['c'], e['resistanceLow'])) else 0.0)) if rt.truth((rt.truth((rt.truth(rt.binary('>', e['atr'], 0)) and rt.truth((not rt.truth(rt.is_na(e['resistanceHigh'])))))) and rt.truth((not rt.truth(rt.is_na(e['resistanceLow'])))))) else rt.NA)
    # Pine 1078
    e['nearSupport'] = rt.binary('<=', e['sZoneDistanceATR'], e['srZoneDistanceATR'])
    # Pine 1079
    e['nearResistance'] = rt.binary('<=', e['rZoneDistanceATR'], e['srZoneDistanceATR'])
    # Pine 1081
    e['averageDynamicSupportScore'] = rt.NA
    # Pine 1082
    e['averageDynamicSupportES'] = rt.NA
    # Pine 1084
    e['averageDynamicResistanceScore'] = rt.NA
    # Pine 1085
    e['averageDynamicResistanceES'] = rt.NA
    # Pine 1087
    e['nearestSupportPrice'] = rt.NA
    # Pine 1088
    e['nearestResistancePrice'] = rt.NA
    # Pine 1090
    e['nearestSupportDistance'] = rt.NA
    # Pine 1091
    e['nearestResistanceDistance'] = rt.NA
    # Pine 1093
    e['nearestSupportZonePrice'] = rt.NA
    # Pine 1094
    e['nearestResistanceZonePrice'] = rt.NA
    # Pine 1096
    e['nearestSupportStrength'] = rt.NA
    # Pine 1097
    e['nearestResistanceStrength'] = rt.NA
    # Pine 1099
    e['nearestSupportES'] = rt.NA
    # Pine 1100
    e['nearestResistanceES'] = rt.NA
    # Pine 1102
    e['nearestSupportScore'] = rt.NA
    # Pine 1103
    e['nearestResistanceScore'] = rt.NA
    # Pine 1105
    e['nearestSupportZoneID'] = rt.NA
    # Pine 1106
    e['nearestResistanceZoneID'] = rt.NA
    # Pine 1108
    e['nearestSupportState'] = rt.NA
    # Pine 1109
    e['nearestResistanceState'] = rt.NA
    # Pine 1111
    e['nearestInstSupport'] = rt.NA
    # Pine 1112
    e['nearestInstResistance'] = rt.NA
    # Pine 1114
    e['nearestInstSupportDistanceATR'] = rt.NA
    # Pine 1115
    e['nearestInstResistanceDistanceATR'] = rt.NA
    # Pine 1117
    e['nearestInstSupportScore'] = rt.NA
    # Pine 1118
    e['nearestInstResistanceScore'] = rt.NA
    # Pine 1120
    e['nearestInstSupportStrength'] = rt.NA
    # Pine 1121
    e['nearestInstResistanceStrength'] = rt.NA
    # Pine 1123
    e['nearestInstSupportES'] = rt.NA
    # Pine 1124
    e['nearestInstResistanceES'] = rt.NA
    # Pine 1126
    e['nearestInstSupportZoneID'] = rt.NA
    # Pine 1127
    e['nearestInstResistanceZoneID'] = rt.NA
    # Pine 1129
    e['nearInstSupport'] = False
    # Pine 1130
    e['nearInstResistance'] = False
    # Pine 1132
    e['averageInstResistanceScore'] = rt.NA
    # Pine 1133
    e['averageInstResistanceES'] = rt.NA
    # Pine 1135
    e['averageInstSupportScore'] = rt.NA
    # Pine 1136
    e['averageInstSupportES'] = rt.NA
    # Pine 1138
    e['interactingSupportZoneId'] = rt.NA
    # Pine 1139
    e['interactingResistanceZoneId'] = rt.NA
    # Pine 1141
    e['nearestSupportZonePriceDistance'] = rt.NA
    # Pine 1142
    e['nearestResistanceZonePriceDistance'] = rt.NA
    # Pine 1144
    e['nearestSupportZonePriceID'] = rt.NA
    # Pine 1145
    e['nearestResistanceZonePriceID'] = rt.NA
    # Pine 1147
    e['nearestSupportZonePriceATR'] = rt.NA
    # Pine 1148
    e['nearestResistanceZonePriceATR'] = rt.NA
    # Pine 1150
    e['nearestSupportLastTestAge'] = rt.NA
    # Pine 1151
    e['nearestSupportLastTestType'] = rt.NA
    # Pine 1153
    e['nearestResistanceLastTestAge'] = rt.NA
    # Pine 1154
    e['nearestResistanceLastTestType'] = rt.NA
    # Pine 1156
    e['nearestInstSupportLastTestAge'] = rt.NA
    # Pine 1157
    e['nearestInstSupportLastTestType'] = rt.NA
    # Pine 1159
    e['nearestInstResistanceLastTestAge'] = rt.NA
    # Pine 1160
    e['nearestInstResistanceLastTestType'] = rt.NA
    # Pine 1162
    e['averageDynamicResistanceLastTestAge'] = rt.NA
    # Pine 1163
    e['averageDynamicSupportLastTestAge'] = rt.NA
    # Pine 1165
    e['averageInstResistanceLastTestAge'] = rt.NA
    # Pine 1166
    e['averageInstSupportLastTestAge'] = rt.NA
    # Pine 1168
    e['dynamicSupportLastTestAgeNormalized'] = rt.NA
    # Pine 1169
    e['dynamicResistanceLastTestAgeNormalized'] = rt.NA
    # Pine 1171
    e['instSupportLastTestAgeNormalized'] = rt.NA
    # Pine 1172
    e['instResistanceLastTestAgeNormalized'] = rt.NA
    # Pine 1174
    e['dynamicSupportESNormalized'] = rt.NA
    # Pine 1175
    e['dynamicResistanceESNormalized'] = rt.NA
    # Pine 1177
    e['instSupportESNormalized'] = rt.NA
    # Pine 1178
    e['instResistanceESNormalized'] = rt.NA
    # Pine 1180
    e['nearestSupportStrongTouches'] = rt.NA
    # Pine 1181
    e['nearestSupportWeakTouches'] = rt.NA
    # Pine 1182
    e['nearestInstSupportFailureCount'] = rt.NA
    # Pine 1184
    e['nearestResistanceStrongTouches'] = rt.NA
    # Pine 1185
    e['nearestResistanceWeakTouches'] = rt.NA
    # Pine 1186
    e['nearestInstResistanceFailureCount'] = rt.NA
    # Pine 1188
    e['dynamicSupportWTNormalized'] = rt.NA
    # Pine 1189
    e['dynamicResistanceWTNormalized'] = rt.NA
    # Pine 1190
    e['dynamicSupportSTNormalized'] = rt.NA
    # Pine 1191
    e['dynamicResistanceSTNormalized'] = rt.NA
    # Pine 1192
    e['instSupportWTNormalized'] = rt.NA
    # Pine 1193
    e['instResistanceWTNormalized'] = rt.NA
    # Pine 1194
    e['instSupportSTNormalized'] = rt.NA
    # Pine 1195
    e['instResistanceSTNormalized'] = rt.NA
    # Pine 1196
    e['instSupportFailureNormalized'] = rt.NA
    # Pine 1197
    e['instResistanceFailureNormalized'] = rt.NA
    # Pine 1201
    e['zoneTFPrefix'] = ('1m' if rt.truth(rt.binary('==', e['timeframe.period'], '1')) else ('5m' if rt.truth(rt.binary('==', e['timeframe.period'], '5')) else ('15m' if rt.truth(rt.binary('==', e['timeframe.period'], '15')) else ('30m' if rt.truth(rt.binary('==', e['timeframe.period'], '30')) else ('1H' if rt.truth(rt.binary('==', e['timeframe.period'], '60')) else ('2H' if rt.truth(rt.binary('==', e['timeframe.period'], '120')) else ('4H' if rt.truth(rt.binary('==', e['timeframe.period'], '240')) else ('1D' if rt.truth(rt.binary('==', e['timeframe.period'], 'D')) else ('1W' if rt.truth(rt.binary('==', e['timeframe.period'], 'W')) else ('1M' if rt.truth(rt.binary('==', e['timeframe.period'], 'M')) else ('3M' if rt.truth(rt.binary('==', e['timeframe.period'], '3M')) else ('6M' if rt.truth(rt.binary('==', e['timeframe.period'], '6M')) else e['timeframe.period']))))))))))))

def update_support_zones(e):
    # Pine 1219
    if rt.truth(rt.binary('>', rt.arr_size(e['supportLowArray']), 0)):
        # Pine 1220
        for e['supportZoneI'] in rt.inclusive(0, rt.binary('-', rt.arr_size(e['supportLowArray']), 1)):
            # Pine 1221
            e['supportZoneLow'] = rt.arr_get(e['supportLowArray'], e['supportZoneI'])
            # Pine 1222
            e['supportZoneHigh'] = rt.arr_get(e['supportHighArray'], e['supportZoneI'])
            # Pine 1223
            e['wasInsideSupportZone'] = rt.arr_get(e['prevCandleInsideSupportZoneArray'], e['supportZoneI'])
            # Pine 1224
            e['insideSupportZone'] = (rt.truth((rt.truth(rt.binary('>', e['bar_index'], rt.arr_get(e['supportBarArray'], e['supportZoneI']))) and rt.truth(rt.binary('<=', e['l'], e['supportZoneHigh'])))) and rt.truth(rt.binary('>=', e['h'], e['supportZoneLow'])))
            # Pine 1225
            e['oldDirection'] = rt.arr_get(e['supportApproachDirectionArray'], e['supportZoneI'])
            # Pine 1226
            e['approachDirection'] = e['oldDirection']
            # Pine 1228
            if rt.truth((rt.truth((rt.truth((rt.truth(e['barstate.isconfirmed']) and rt.truth(rt.binary('>', e['c'], e['supportZoneHigh'])))) and rt.truth((not rt.truth(e['insideSupportZone']))))) and rt.truth((not rt.truth(e['wasInsideSupportZone']))))):
                # Pine 1229
                e['approachDirection'] = 1
            # Pine 1231
            rt.arr_set(e['supportApproachDirectionArray'], e['supportZoneI'], e['approachDirection'])
    # Pine 1234
    if rt.truth((rt.truth((rt.truth(e['barstate.isconfirmed']) and rt.truth((not rt.truth(rt.is_na(e['srPivotLow'])))))) and rt.truth(rt.binary('>=', e['supportReactionATR'], e['srReactionATR'])))):
        # Pine 1235
        e['potentialSupportLow'] = rt.binary('-', e['srPivotLow'], e['srZoneSize'])
        # Pine 1236
        e['potentialSupportHigh'] = rt.binary('+', e['srPivotLow'], e['srZoneSize'])
        # Pine 1237
        e['insideInstitutionalSupport'] = False
        # Pine 1239
        if rt.truth(rt.binary('>', rt.arr_size(e['instSupportZoneIDArray']), 0)):
            # Pine 1240
            for e['instI'] in rt.inclusive(0, rt.binary('-', rt.arr_size(e['instSupportZoneIDArray']), 1)):
                # Pine 1241
                e['instSupportZoneID'] = rt.arr_get(e['instSupportZoneIDArray'], e['instI'])
                # Pine 1243
                e['instDynamicIndex'] = rt.arr_indexof(e['supportZoneIDArray'], e['instSupportZoneID'])
                # Pine 1245
                if rt.truth(rt.binary('!=', e['instDynamicIndex'], rt.neg(1))):
                    # Pine 1246
                    e['instSupportZoneLow'] = rt.arr_get(e['supportLowArray'], e['instDynamicIndex'])
                    # Pine 1247
                    e['instSupportZoneHigh'] = rt.arr_get(e['supportHighArray'], e['instDynamicIndex'])
                    # Pine 1248
                    e['institutionalSupportOverlap'] = (rt.truth(rt.binary('<=', e['potentialSupportLow'], e['instSupportZoneHigh'])) and rt.truth(rt.binary('>=', e['potentialSupportHigh'], e['instSupportZoneLow'])))
                    # Pine 1250
                    if rt.truth(e['institutionalSupportOverlap']):
                        # Pine 1251
                        e['insideInstitutionalSupport'] = True
                        # Pine 1252
                        break
        # Pine 1256
        if rt.truth((not rt.truth(e['insideInstitutionalSupport']))):
            # Pine 1257
            e['nextSupportZoneSequence'] = rt.binary('+', e['nextSupportZoneSequence'], 1)
            # Pine 1258
            e['newSupportZoneID'] = rt.binary('+', rt.binary('+', e['zoneTFPrefix'], '-S-'), rt.str_tostring(e['nextSupportZoneSequence'], '000000'))
            # Pine 1259
            rt.arr_push(e['supportZoneIDArray'], e['newSupportZoneID'])
            # Pine 1260
            rt.arr_push(e['supportLowArray'], rt.binary('-', e['srPivotLow'], e['srZoneSize']))
            # Pine 1261
            rt.arr_push(e['supportHighArray'], rt.binary('+', e['srPivotLow'], e['srZoneSize']))
            # Pine 1262
            rt.arr_push(e['supportOriginArray'], e['srPivotLow'])
            # Pine 1263
            rt.arr_push(e['supportBarArray'], rt.binary('-', e['bar_index'], e['srPivotRight']))
            # Pine 1264
            rt.arr_push(e['supportTouchArray'], 0)
            # Pine 1265
            rt.arr_push(e['prevCandleInsideSupportZoneArray'], False)
            # Pine 1266
            rt.arr_push(e['supportLastTestBarArray'], rt.NA)
            # Pine 1267
            rt.arr_push(e['supportLastTestTypeArray'], 'NO_TEST')
            # Pine 1268
            rt.arr_push(e['supportStrengthArray'], 0)
            # Pine 1269
            rt.arr_push(e['supportStrongRejectArray'], 0)
            # Pine 1270
            rt.arr_push(e['supportMaxPenetrationArray'], 0.0)
            # Pine 1271
            rt.arr_push(e['supportMaxWickRatioArray'], 0.0)
            # Pine 1272
            rt.arr_push(e['supportMaxReactionArray'], 0.0)
            # Pine 1273
            rt.arr_push(e['supportApproachDirectionArray'], 0)
            # Pine 1274
            rt.arr_push(e['supportOriginTimeArray'], e.previous('time', e['srPivotRight']))
            # Pine 1275
            rt.arr_push(e['supportScoreArray'], 0.0)
            # Pine 1276
            rt.arr_push(e['supportESArray'], 0)
            # Pine 1277
            rt.arr_push(e['supportZoneATRArray'], e['pivotATR'])
    # Pine 1279
    if rt.truth(rt.binary('>', rt.arr_size(e['supportLowArray']), 0)):
        # Pine 1280
        for e['i'] in rt.inclusive(rt.binary('-', rt.arr_size(e['supportLowArray']), 1), 0):
            # Pine 1281
            e['supportZoneLow'] = rt.arr_get(e['supportLowArray'], e['i'])
            # Pine 1282
            e['supportZoneHigh'] = rt.arr_get(e['supportHighArray'], e['i'])
            # Pine 1283
            e['supportZoneDistanceATR'] = ((rt.binary('/', rt.binary('-', e['c'], e['supportZoneHigh']), e['atr']) if rt.truth(rt.binary('>', e['c'], e['supportZoneHigh'])) else (rt.binary('/', rt.binary('-', e['supportZoneLow'], e['c']), e['atr']) if rt.truth(rt.binary('<', e['c'], e['supportZoneLow'])) else 0.0)) if rt.truth(rt.binary('>', e['atr'], 0)) else rt.NA)
            # Pine 1284
            e['wasInsideSupportZone'] = rt.arr_get(e['prevCandleInsideSupportZoneArray'], e['i'])
            # Pine 1285
            e['insideSupportZone'] = (rt.truth((rt.truth(rt.binary('>', e['bar_index'], rt.arr_get(e['supportBarArray'], e['i']))) and rt.truth(rt.binary('<=', e['l'], e['supportZoneHigh'])))) and rt.truth(rt.binary('>=', e['h'], e['supportZoneLow'])))
            # Pine 1286
            if rt.truth(e['insideSupportZone']):
                # Pine 1287
                e['interactingSupportZoneId'] = e['i']
            # Pine 1288
            if rt.truth(e['barstate.isconfirmed']):
                # Pine 1289
                rt.arr_set(e['prevCandleInsideSupportZoneArray'], e['i'], e['insideSupportZone'])
            # Pine 1291
            if rt.truth((rt.truth(rt.binary('>', e['supportZoneDistanceATR'], e['srZoneDistanceATR'])) and rt.truth((not rt.truth((rt.truth(e['wasInsideSupportZone']) or rt.truth(e['insideSupportZone']))))))):
                # Pine 1292
                continue
            # Pine 1294
            e['supportZoneAge'] = rt.binary('-', e['bar_index'], rt.arr_get(e['supportBarArray'], e['i']))
            # Pine 1295
            e['lastSupportTestBar'] = rt.arr_get(e['supportLastTestBarArray'], e['i'])
            # Pine 1296
            e['barsSinceSupportTest'] = (rt.binary('-', e['bar_index'], e['lastSupportTestBar']) if rt.truth((not rt.truth(rt.is_na(e['lastSupportTestBar'])))) else e['supportZoneAge'])
            # Pine 1297
            e['wasApproachedFromAbove'] = rt.binary('==', rt.arr_get(e['supportApproachDirectionArray'], e['i']), 1)
            # Pine 1298
            e['previousCandleCrossedZone'] = (rt.truth((rt.truth((rt.truth(e['barstate.isconfirmed']) and rt.truth(rt.binary('>', e['h1'], e['supportZoneHigh'])))) and rt.truth(rt.binary('<', e['l1'], e['supportZoneLow'])))) and rt.truth(e['wasApproachedFromAbove']))
            # Pine 1299
            e['supportInvalid'] = (rt.truth((rt.truth(e['barstate.isconfirmed']) and rt.truth(rt.binary('<', e['h'], e['supportZoneLow'])))) and rt.truth((rt.truth(e['wasApproachedFromAbove']) or rt.truth(e['previousCandleCrossedZone']))))
            # Pine 1301
            if rt.truth(e['supportInvalid']):
                # Pine 1302
                e['zoneID'] = rt.arr_get(e['supportZoneIDArray'], e['i'])
                # Pine 1303
                e['instIndex'] = rt.arr_indexof(e['instSupportZoneIDArray'], e['zoneID'])
                # Pine 1304
                e['isSupportInstitutional'] = rt.binary('!=', e['instIndex'], rt.neg(1))
                # Pine 1306
                if rt.truth((not rt.truth(e['isSupportInstitutional']))):
                    # Pine 1307
                    rt.arr_remove(e['supportZoneIDArray'], e['i'])
                    # Pine 1308
                    rt.arr_remove(e['supportLowArray'], e['i'])
                    # Pine 1309
                    rt.arr_remove(e['supportHighArray'], e['i'])
                    # Pine 1310
                    rt.arr_remove(e['supportOriginArray'], e['i'])
                    # Pine 1311
                    rt.arr_remove(e['supportBarArray'], e['i'])
                    # Pine 1312
                    rt.arr_remove(e['supportTouchArray'], e['i'])
                    # Pine 1313
                    rt.arr_remove(e['prevCandleInsideSupportZoneArray'], e['i'])
                    # Pine 1314
                    rt.arr_remove(e['supportLastTestBarArray'], e['i'])
                    # Pine 1315
                    rt.arr_remove(e['supportLastTestTypeArray'], e['i'])
                    # Pine 1316
                    rt.arr_remove(e['supportStrengthArray'], e['i'])
                    # Pine 1317
                    rt.arr_remove(e['supportStrongRejectArray'], e['i'])
                    # Pine 1318
                    rt.arr_remove(e['supportMaxPenetrationArray'], e['i'])
                    # Pine 1319
                    rt.arr_remove(e['supportMaxWickRatioArray'], e['i'])
                    # Pine 1320
                    rt.arr_remove(e['supportMaxReactionArray'], e['i'])
                    # Pine 1321
                    rt.arr_remove(e['supportApproachDirectionArray'], e['i'])
                    # Pine 1322
                    rt.arr_remove(e['supportOriginTimeArray'], e['i'])
                    # Pine 1323
                    rt.arr_remove(e['supportScoreArray'], e['i'])
                    # Pine 1324
                    rt.arr_remove(e['supportESArray'], e['i'])
                    # Pine 1325
                    rt.arr_remove(e['supportZoneATRArray'], e['i'])
                # Pine 1327
                if rt.truth(e['isSupportInstitutional']):
                    # Pine 1328
                    e['oldFailureCount'] = rt.arr_get(e['instSupportFailureCountArray'], e['instIndex'])
                    # Pine 1329
                    rt.arr_set(e['InstSupportBreakBarArray'], e['instIndex'], e['bar_index'])
                    # Pine 1330
                    rt.arr_set(e['instSupportFailureCountArray'], e['instIndex'], rt.binary('+', e['oldFailureCount'], 1))
                    # Pine 1331
                    rt.arr_set(e['supportLastTestBarArray'], e['i'], e['bar_index'])
                    # Pine 1332
                    rt.arr_set(e['supportLastTestTypeArray'], e['i'], 'FAILED')
                    # Pine 1333
                    rt.arr_set(e['supportApproachDirectionArray'], e['i'], 0)
                    # Pine 1334
                    e['instSupportScore'] = rt.arr_get(e['instSupportScoreArray'], e['instIndex'])
                    # Pine 1336
                    if rt.truth(rt.binary('<=', e['instSupportScore'], 5)):
                        # Pine 1338
                        rt.arr_remove(e['instSupportZoneIDArray'], e['instIndex'])
                        # Pine 1339
                        rt.arr_remove(e['instSupportScoreArray'], e['instIndex'])
                        # Pine 1340
                        rt.arr_remove(e['instSupportStrengthArray'], e['instIndex'])
                        # Pine 1341
                        rt.arr_remove(e['instQualifiedSupportTFListArray'], e['instIndex'])
                        # Pine 1342
                        rt.arr_remove(e['instSupportFailureCountArray'], e['instIndex'])
                        # Pine 1343
                        rt.arr_remove(e['InstSupportBreakBarArray'], e['instIndex'])
                        # Pine 1346
                        rt.arr_remove(e['supportZoneIDArray'], e['i'])
                        # Pine 1347
                        rt.arr_remove(e['supportLowArray'], e['i'])
                        # Pine 1348
                        rt.arr_remove(e['supportHighArray'], e['i'])
                        # Pine 1349
                        rt.arr_remove(e['supportOriginArray'], e['i'])
                        # Pine 1350
                        rt.arr_remove(e['supportBarArray'], e['i'])
                        # Pine 1351
                        rt.arr_remove(e['supportTouchArray'], e['i'])
                        # Pine 1352
                        rt.arr_remove(e['prevCandleInsideSupportZoneArray'], e['i'])
                        # Pine 1353
                        rt.arr_remove(e['supportLastTestBarArray'], e['i'])
                        # Pine 1354
                        rt.arr_remove(e['supportLastTestTypeArray'], e['i'])
                        # Pine 1355
                        rt.arr_remove(e['supportStrengthArray'], e['i'])
                        # Pine 1356
                        rt.arr_remove(e['supportStrongRejectArray'], e['i'])
                        # Pine 1357
                        rt.arr_remove(e['supportMaxPenetrationArray'], e['i'])
                        # Pine 1358
                        rt.arr_remove(e['supportMaxWickRatioArray'], e['i'])
                        # Pine 1359
                        rt.arr_remove(e['supportMaxReactionArray'], e['i'])
                        # Pine 1360
                        rt.arr_remove(e['supportApproachDirectionArray'], e['i'])
                        # Pine 1361
                        rt.arr_remove(e['supportOriginTimeArray'], e['i'])
                        # Pine 1362
                        rt.arr_remove(e['supportScoreArray'], e['i'])
                        # Pine 1363
                        rt.arr_remove(e['supportESArray'], e['i'])
                        # Pine 1364
                        rt.arr_remove(e['supportZoneATRArray'], e['i'])
            # Pine 1366
            elif rt.truth(e['barstate.isconfirmed']):
                # Pine 1367
                e['oldSupportTouches'] = rt.arr_get(e['supportTouchArray'], e['i'])
                # Pine 1368
                e['oldSupportStrength'] = rt.arr_get(e['supportStrengthArray'], e['i'])
                # Pine 1369
                e['supportZoneHeight'] = rt.binary('-', e['supportZoneHigh'], e['supportZoneLow'])
                # Pine 1370
                e['supportPenetration'] = rt.math_max(0.0, rt.binary('/', rt.binary('-', e['supportZoneHigh'], e['l']), e['supportZoneHeight']))
                # Pine 1371
                e['penetrationInsideSupportZone'] = (rt.truth(rt.binary('>=', e['l'], e['supportZoneLow'])) and rt.truth(rt.binary('<=', e['l'], e['supportZoneHigh'])))
                # Pine 1372
                if rt.truth(e['penetrationInsideSupportZone']):
                    # Pine 1373
                    e['oldMaxPenetration'] = rt.arr_get(e['supportMaxPenetrationArray'], e['i'])
                    # Pine 1374
                    rt.arr_set(e['supportMaxPenetrationArray'], e['i'], rt.math_max(e['oldMaxPenetration'], e['supportPenetration']))
                # Pine 1376
                e['wickSize'] = (rt.binary('-', e['supportZoneLow'], e['l']) if rt.truth(rt.binary('<', e['l'], e['supportZoneLow'])) else 0)
                # Pine 1377
                e['candleRange'] = rt.binary('-', e['h'], e['l'])
                # Pine 1378
                e['wickRatio'] = (rt.binary('/', e['wickSize'], e['candleRange']) if rt.truth(rt.binary('>', e['candleRange'], 0)) else 0)
                # Pine 1379
                e['currentSupportReaction'] = (rt.binary('/', rt.binary('-', e['c'], e['supportZoneHigh']), e['atr']) if rt.truth(rt.binary('>', e['c'], e['supportZoneHigh'])) else 0)
                # Pine 1380
                e['oldWick'] = rt.arr_get(e['supportMaxWickRatioArray'], e['i'])
                # Pine 1381
                e['oldReaction'] = rt.arr_get(e['supportMaxReactionArray'], e['i'])
                # Pine 1383
                rt.arr_set(e['supportMaxWickRatioArray'], e['i'], rt.math_max(e['oldWick'], e['wickRatio']))
                # Pine 1384
                rt.arr_set(e['supportMaxReactionArray'], e['i'], rt.math_max(e['oldReaction'], e['currentSupportReaction']))
                # Pine 1386
                e['wickBelowSupport'] = (rt.truth(rt.binary('<', e['l'], e['supportZoneLow'])) and rt.truth(rt.binary('>', e['c'], e['supportZoneHigh'])))
                # Pine 1387
                if rt.truth((rt.truth((rt.truth(e['wasInsideSupportZone']) and rt.truth(e['wasApproachedFromAbove']))) and rt.truth(rt.binary('>', e['l'], e['supportZoneHigh'])))):
                    # Pine 1388
                    e['newSupportTouches'] = rt.binary('+', e['oldSupportTouches'], 1)
                    # Pine 1389
                    rt.arr_set(e['supportTouchArray'], e['i'], e['newSupportTouches'])
                    # Pine 1390
                    e['strongSupportRejects'] = rt.arr_get(e['supportStrongRejectArray'], e['i'])
                    # Pine 1391
                    e['currentSupportStrength'] = e['oldSupportStrength']
                    # Pine 1393
                    if rt.truth(rt.binary('>=', e['currentSupportReaction'], e['srReactionATR'])):
                        # Pine 1394
                        e['currentSupportStrength'] = rt.binary('+', e['currentSupportStrength'], 5)
                        # Pine 1395
                        e['strongSupportRejects'] = rt.binary('+', e['strongSupportRejects'], 1)
                        # Pine 1396
                        rt.arr_set(e['supportLastTestTypeArray'], e['i'], 'STRONG_REJECTION')
                    # Pine 1398
                    else:
                        # Pine 1399
                        e['currentSupportStrength'] = rt.binary('+', e['currentSupportStrength'], 3)
                        # Pine 1400
                        rt.arr_set(e['supportLastTestTypeArray'], e['i'], 'WEAK_REACTION')
                    # Pine 1402
                    rt.arr_set(e['supportStrengthArray'], e['i'], e['currentSupportStrength'])
                    # Pine 1403
                    rt.arr_set(e['supportStrongRejectArray'], e['i'], e['strongSupportRejects'])
                    # Pine 1404
                    rt.arr_set(e['supportLastTestBarArray'], e['i'], e['bar_index'])
                # Pine 1406
                e['supportTouches'] = rt.arr_get(e['supportTouchArray'], e['i'])
                # Pine 1407
                e['strongSupportRejects'] = rt.arr_get(e['supportStrongRejectArray'], e['i'])
                # Pine 1408
                e['weakSupportTouches'] = rt.math_max(0, rt.binary('-', e['supportTouches'], e['strongSupportRejects']))
                # Pine 1409
                e['supportScore'] = rt.binary('+', rt.binary('*', e['strongSupportRejects'], 5.0), rt.binary('*', e['weakSupportTouches'], 3.0))
                # Pine 1410
                rt.arr_set(e['supportScoreArray'], e['i'], e['supportScore'])
                # Pine 1411
                rt.arr_set(e['prevCandleInsideSupportZoneArray'], e['i'], e['insideSupportZone'])
                # Pine 1413
                e['supportAgeFactor'] = rt.binary('/', 1, rt.binary('+', 1, rt.binary('/', e['supportZoneAge'], 1000)))
                # Pine 1414
                e['supportRecentTestFactor'] = rt.binary('/', 1, rt.binary('+', 1, rt.binary('/', e['barsSinceSupportTest'], 500)))
                # Pine 1415
                e['lastSupportTestType'] = rt.arr_get(e['supportLastTestTypeArray'], e['i'])
                # Pine 1416
                e['supportTestTypeFactor'] = 0.0
                # Pine 1418
                if rt.truth(rt.binary('==', e['lastSupportTestType'], 'STRONG_REJECTION')):
                    # Pine 1419
                    e['supportTestTypeFactor'] = 1.0
                # Pine 1420
                elif rt.truth(rt.binary('==', e['lastSupportTestType'], 'WEAK_REACTION')):
                    # Pine 1421
                    e['supportTestTypeFactor'] = 0.5
                # Pine 1422
                elif rt.truth(rt.binary('==', e['lastSupportTestType'], 'FAILED')):
                    # Pine 1423
                    e['supportTestTypeFactor'] = rt.neg(1.0)
                # Pine 1424
                else:
                    # Pine 1425
                    e['supportTestTypeFactor'] = 0.0
                # Pine 1427
                e['effectiveSupportStrength'] = 0.0
                # Pine 1428
                e['currentSupportZoneID'] = rt.arr_get(e['supportZoneIDArray'], e['i'])
                # Pine 1429
                e['instSupportIndex'] = rt.arr_indexof(e['instSupportZoneIDArray'], e['currentSupportZoneID'])
                # Pine 1430
                if rt.truth(rt.binary('!=', e['instSupportIndex'], rt.neg(1))):
                    # Pine 1431
                    e['effectiveSupportStrength'] = rt.binary('*', rt.binary('*', rt.binary('*', rt.arr_get(e['instSupportStrengthArray'], e['instSupportIndex']), e['supportAgeFactor']), e['supportRecentTestFactor']), e['supportTestTypeFactor'])
                # Pine 1433
                else:
                    # Pine 1434
                    e['effectiveSupportStrength'] = rt.binary('*', rt.binary('*', rt.binary('*', rt.arr_get(e['supportStrengthArray'], e['i']), e['supportAgeFactor']), e['supportRecentTestFactor']), e['supportTestTypeFactor'])
                # Pine 1435
                rt.arr_set(e['supportESArray'], e['i'], e['effectiveSupportStrength'])
                # Pine 1437
                e['supportDistanceATR'] = (rt.binary('/', rt.binary('-', e['c'], e['supportZoneHigh']), e['atr']) if rt.truth(rt.binary('>', e['atr'], 0)) else rt.NA)
                # Pine 1438
                if rt.truth((rt.truth(e['wasApproachedFromAbove']) and rt.truth(rt.binary('>=', e['supportDistanceATR'], 0)))):
                    # Pine 1439
                    if rt.truth((rt.truth(rt.is_na(e['nearestSupportDistance'])) or rt.truth(rt.binary('<', e['supportDistanceATR'], e['nearestSupportDistance'])))):
                        # Pine 1440
                        e['nearestSupportDistance'] = e['supportDistanceATR']
                        # Pine 1441
                        e['nearestSupportPrice'] = e['supportZoneHigh']
                        # Pine 1442
                        e['nearestSupportStrength'] = rt.arr_get(e['supportStrengthArray'], e['i'])
                        # Pine 1443
                        e['nearestSupportScore'] = rt.arr_get(e['supportScoreArray'], e['i'])
                        # Pine 1444
                        e['nearestSupportZoneID'] = rt.arr_get(e['supportZoneIDArray'], e['i'])
                        # Pine 1445
                        e['nearestSupportState'] = rt.arr_get(e['supportLastTestTypeArray'], e['i'])
                # Pine 1447
                rt.arr_set(e['prevCandleInsideSupportZoneArray'], e['i'], e['insideSupportZone'])
                # Pine 1449
                e['supportDistancePrice'] = rt.NA
                # Pine 1450
                if rt.truth(rt.binary('>=', e['c'], e['supportZoneLow'])):
                    # Pine 1451
                    e['supportDistancePrice'] = rt.binary('-', e['c'], e['supportZoneLow'])
                # Pine 1453
                if rt.truth((not rt.truth(rt.is_na(e['supportDistancePrice'])))):
                    # Pine 1454
                    if rt.truth((rt.truth(rt.is_na(e['nearestSupportZonePriceDistance'])) or rt.truth(rt.binary('<', e['supportDistancePrice'], e['nearestSupportZonePriceDistance'])))):
                        # Pine 1455
                        e['nearestSupportZonePrice'] = e['supportZoneLow']
                        # Pine 1456
                        e['nearestSupportZonePriceID'] = rt.arr_get(e['supportZoneIDArray'], e['i'])
                        # Pine 1457
                        e['nearestSupportZonePriceDistance'] = e['supportDistancePrice']
                        # Pine 1458
                        e['nearestSupportZonePriceATR'] = rt.arr_get(e['supportZoneATRArray'], e['i'])
                        # Pine 1459
                        e['nearestSupportES'] = rt.arr_get(e['supportESArray'], e['i'])
                        # Pine 1461
                        e['lastTestBar'] = rt.arr_get(e['supportLastTestBarArray'], e['i'])
                        # Pine 1462
                        e['nearestSupportLastTestAge'] = (rt.binary('-', e['bar_index'], e['lastTestBar']) if rt.truth((not rt.truth(rt.is_na(e['lastTestBar'])))) else rt.NA)
                        # Pine 1463
                        e['nearestSupportLastTestType'] = rt.arr_get(e['supportLastTestTypeArray'], e['i'])
                        # Pine 1464
                        e['nearestSupportStrongTouches'] = rt.arr_get(e['supportStrongRejectArray'], e['i'])
                        # Pine 1466
                        e['nearestSupportTotalTouches'] = rt.arr_get(e['supportTouchArray'], e['i'])
                        # Pine 1467
                        e['nearestSupportWeakTouches'] = rt.math_max(0, rt.binary('-', e['nearestSupportTotalTouches'], e['nearestSupportStrongTouches']))
                        # Pine 1469
                        e['instNearestSupportIndex'] = rt.arr_indexof(e['instSupportZoneIDArray'], e['nearestSupportZonePriceID'])
                        # Pine 1470
                        e['nearestInstSupportFailureCount'] = (rt.arr_get(e['instSupportFailureCountArray'], e['instNearestSupportIndex']) if rt.truth(rt.binary('!=', e['instNearestSupportIndex'], rt.neg(1))) else rt.NA)
    # Pine 1487
    if rt.truth((rt.truth((rt.truth(e['barstate.isconfirmed']) and rt.truth((not rt.truth(rt.is_na(e['srPivotLow'])))))) and rt.truth(rt.binary('>', rt.arr_size(e['supportLowArray']), 1)))):
        # Pine 1488
        e['latestSupportIndex'] = rt.binary('-', rt.arr_size(e['supportLowArray']), 1)
        # Pine 1489
        e['latestSupportZoneID'] = rt.arr_get(e['supportZoneIDArray'], e['latestSupportIndex'])
        # Pine 1490
        e['newSupportLow'] = rt.arr_get(e['supportLowArray'], e['latestSupportIndex'])
        # Pine 1491
        e['newSupportHigh'] = rt.arr_get(e['supportHighArray'], e['latestSupportIndex'])
        # Pine 1494
        e['mergeSupportIndex'] = rt.neg(1)
        # Pine 1495
        e['nearestSupportMergeDistance'] = rt.NA
        # Pine 1496
        for e['i'] in rt.inclusive(0, rt.binary('-', e['latestSupportIndex'], 1)):
            # Pine 1497
            e['existingSupportZoneID'] = rt.arr_get(e['supportZoneIDArray'], e['i'])
            # Pine 1498
            e['existingZoneIsInstitutional'] = rt.binary('!=', rt.arr_indexof(e['instSupportZoneIDArray'], e['existingSupportZoneID']), rt.neg(1))
            # Pine 1499
            if rt.truth(e['existingZoneIsInstitutional']):
                # Pine 1500
                continue
            # Pine 1502
            e['existingSupportLow'] = rt.arr_get(e['supportLowArray'], e['i'])
            # Pine 1503
            e['existingSupportHigh'] = rt.arr_get(e['supportHighArray'], e['i'])
            # Pine 1504
            e['mergeSupportDistance'] = 0.0
            # Pine 1505
            if rt.truth(rt.binary('>', e['newSupportLow'], e['existingSupportHigh'])):
                # Pine 1506
                e['mergeSupportDistance'] = rt.binary('-', e['newSupportLow'], e['existingSupportHigh'])
            # Pine 1508
            elif rt.truth(rt.binary('<', e['newSupportHigh'], e['existingSupportLow'])):
                # Pine 1509
                e['mergeSupportDistance'] = rt.binary('-', e['existingSupportLow'], e['newSupportHigh'])
            # Pine 1510
            else:
                # Pine 1511
                e['mergeSupportDistance'] = 0.0
            # Pine 1513
            e['supportOverlap'] = rt.binary('<=', e['mergeSupportDistance'], e['srMergeDistance'])
            # Pine 1514
            if rt.truth(e['supportOverlap']):
                # Pine 1515
                if rt.truth((rt.truth(rt.is_na(e['nearestSupportMergeDistance'])) or rt.truth(rt.binary('<', e['mergeSupportDistance'], e['nearestSupportMergeDistance'])))):
                    # Pine 1516
                    e['nearestSupportMergeDistance'] = e['mergeSupportDistance']
                    # Pine 1517
                    e['mergeSupportIndex'] = e['i']
        # Pine 1520
        if rt.truth(rt.binary('!=', e['mergeSupportIndex'], rt.neg(1))):
            # Pine 1521
            e['existingSupportLow'] = rt.arr_get(e['supportLowArray'], e['mergeSupportIndex'])
            # Pine 1522
            e['existingSupportHigh'] = rt.arr_get(e['supportHighArray'], e['mergeSupportIndex'])
            # Pine 1523
            e['survivingZoneHeight'] = rt.binary('-', e['existingSupportHigh'], e['existingSupportLow'])
            # Pine 1524
            e['survivingSupportZoneID'] = rt.arr_get(e['supportZoneIDArray'], e['mergeSupportIndex'])
            # Pine 1525
            e['combinedLow'] = rt.math_min(e['existingSupportLow'], e['newSupportLow'])
            # Pine 1526
            e['combinedHigh'] = rt.math_max(e['existingSupportHigh'], e['newSupportHigh'])
            # Pine 1527
            e['mergedCenter'] = rt.binary('/', rt.binary('+', e['combinedLow'], e['combinedHigh']), 2.0)
            # Pine 1528
            e['mergedLow'] = rt.binary('-', e['mergedCenter'], rt.binary('/', e['survivingZoneHeight'], 2.0))
            # Pine 1529
            e['mergedHigh'] = rt.binary('+', e['mergedCenter'], rt.binary('/', e['survivingZoneHeight'], 2.0))
            # Pine 1531
            rt.arr_set(e['supportLowArray'], e['mergeSupportIndex'], e['mergedLow'])
            # Pine 1532
            rt.arr_set(e['supportHighArray'], e['mergeSupportIndex'], e['mergedHigh'])
            # Pine 1535
            e['oldBar'] = rt.arr_get(e['supportBarArray'], e['mergeSupportIndex'])
            # Pine 1536
            e['newBar'] = rt.arr_get(e['supportBarArray'], e['latestSupportIndex'])
            # Pine 1538
            if rt.truth(rt.binary('<', e['newBar'], e['oldBar'])):
                # Pine 1539
                rt.arr_set(e['supportBarArray'], e['mergeSupportIndex'], e['newBar'])
                # Pine 1540
                rt.arr_set(e['supportOriginArray'], e['mergeSupportIndex'], rt.arr_get(e['supportOriginArray'], e['latestSupportIndex']))
                # Pine 1541
                rt.arr_set(e['supportOriginTimeArray'], e['mergeSupportIndex'], rt.arr_get(e['supportOriginTimeArray'], e['latestSupportIndex']))
                # Pine 1542
                rt.arr_set(e['supportZoneATRArray'], e['mergeSupportIndex'], rt.arr_get(e['supportZoneATRArray'], e['latestSupportIndex']))
            # Pine 1545
            e['oldSupportTouches'] = rt.arr_get(e['supportTouchArray'], e['mergeSupportIndex'])
            # Pine 1546
            e['newSupportTouches'] = rt.arr_get(e['supportTouchArray'], e['latestSupportIndex'])
            # Pine 1547
            rt.arr_set(e['supportTouchArray'], e['mergeSupportIndex'], rt.binary('+', e['oldSupportTouches'], e['newSupportTouches']))
            # Pine 1550
            e['oldStrength'] = rt.arr_get(e['supportStrengthArray'], e['mergeSupportIndex'])
            # Pine 1551
            e['newStrength'] = rt.arr_get(e['supportStrengthArray'], e['latestSupportIndex'])
            # Pine 1552
            rt.arr_set(e['supportStrengthArray'], e['mergeSupportIndex'], rt.math_max(e['oldStrength'], e['newStrength']))
            # Pine 1555
            e['oldES'] = rt.arr_get(e['supportESArray'], e['mergeSupportIndex'])
            # Pine 1556
            e['newES'] = rt.arr_get(e['supportESArray'], e['latestSupportIndex'])
            # Pine 1558
            rt.arr_set(e['supportESArray'], e['mergeSupportIndex'], rt.math_max(e['oldES'], e['newES']))
            # Pine 1561
            e['oldReject'] = rt.arr_get(e['supportStrongRejectArray'], e['mergeSupportIndex'])
            # Pine 1562
            e['newReject'] = rt.arr_get(e['supportStrongRejectArray'], e['latestSupportIndex'])
            # Pine 1564
            rt.arr_set(e['supportStrongRejectArray'], e['mergeSupportIndex'], rt.binary('+', e['oldReject'], e['newReject']))
            # Pine 1567
            e['oldLast'] = rt.arr_get(e['supportLastTestBarArray'], e['mergeSupportIndex'])
            # Pine 1568
            e['newLast'] = rt.arr_get(e['supportLastTestBarArray'], e['latestSupportIndex'])
            # Pine 1570
            if rt.truth((rt.truth(rt.is_na(e['oldLast'])) or rt.truth((rt.truth((not rt.truth(rt.is_na(e['newLast'])))) and rt.truth(rt.binary('>', e['newLast'], e['oldLast'])))))):
                # Pine 1571
                rt.arr_set(e['supportLastTestBarArray'], e['mergeSupportIndex'], e['newLast'])
                # Pine 1572
                rt.arr_set(e['supportLastTestTypeArray'], e['mergeSupportIndex'], rt.arr_get(e['supportLastTestTypeArray'], e['latestSupportIndex']))
            # Pine 1575
            e['oldMaxPenetration'] = rt.arr_get(e['supportMaxPenetrationArray'], e['mergeSupportIndex'])
            # Pine 1576
            e['newMaxPenetration'] = rt.arr_get(e['supportMaxPenetrationArray'], e['latestSupportIndex'])
            # Pine 1577
            rt.arr_set(e['supportMaxPenetrationArray'], e['mergeSupportIndex'], rt.math_max(e['oldMaxPenetration'], e['newMaxPenetration']))
            # Pine 1580
            e['oldWick'] = rt.arr_get(e['supportMaxWickRatioArray'], e['mergeSupportIndex'])
            # Pine 1581
            e['newWick'] = rt.arr_get(e['supportMaxWickRatioArray'], e['latestSupportIndex'])
            # Pine 1582
            rt.arr_set(e['supportMaxWickRatioArray'], e['mergeSupportIndex'], rt.math_max(e['oldWick'], e['newWick']))
            # Pine 1585
            e['oldReaction'] = rt.arr_get(e['supportMaxReactionArray'], e['mergeSupportIndex'])
            # Pine 1586
            e['newReaction'] = rt.arr_get(e['supportMaxReactionArray'], e['latestSupportIndex'])
            # Pine 1587
            rt.arr_set(e['supportMaxReactionArray'], e['mergeSupportIndex'], rt.math_max(e['oldReaction'], e['newReaction']))
            # Pine 1589
            e['mergedSupportTouches'] = rt.arr_get(e['supportTouchArray'], e['mergeSupportIndex'])
            # Pine 1590
            e['mergedSupportRejects'] = rt.arr_get(e['supportStrongRejectArray'], e['mergeSupportIndex'])
            # Pine 1591
            e['mergedSupportWeakTouches'] = rt.math_max(0, rt.binary('-', e['mergedSupportTouches'], e['mergedSupportRejects']))
            # Pine 1592
            e['mergedSupportScore'] = rt.binary('+', rt.binary('*', e['mergedSupportRejects'], 5.0), rt.binary('*', e['mergedSupportWeakTouches'], 3.0))
            # Pine 1593
            rt.arr_set(e['supportScoreArray'], e['mergeSupportIndex'], e['mergedSupportScore'])
            # Pine 1596
            e['oldDirection'] = rt.arr_get(e['supportApproachDirectionArray'], e['mergeSupportIndex'])
            # Pine 1597
            e['newDirection'] = rt.arr_get(e['supportApproachDirectionArray'], e['latestSupportIndex'])
            # Pine 1598
            e['mergedDirection'] = e['oldDirection']
            # Pine 1600
            if rt.truth((rt.truth(rt.binary('==', e['mergedDirection'], 0)) and rt.truth(rt.binary('!=', e['newDirection'], 0)))):
                # Pine 1601
                e['mergedDirection'] = e['newDirection']
            # Pine 1602
            rt.arr_set(e['supportApproachDirectionArray'], e['mergeSupportIndex'], e['mergedDirection'])
            # Pine 1612
            rt.arr_remove(e['supportZoneIDArray'], e['latestSupportIndex'])
            # Pine 1613
            rt.arr_remove(e['supportLowArray'], e['latestSupportIndex'])
            # Pine 1614
            rt.arr_remove(e['supportHighArray'], e['latestSupportIndex'])
            # Pine 1615
            rt.arr_remove(e['supportOriginArray'], e['latestSupportIndex'])
            # Pine 1616
            rt.arr_remove(e['supportBarArray'], e['latestSupportIndex'])
            # Pine 1617
            rt.arr_remove(e['supportTouchArray'], e['latestSupportIndex'])
            # Pine 1618
            rt.arr_remove(e['prevCandleInsideSupportZoneArray'], e['latestSupportIndex'])
            # Pine 1619
            rt.arr_remove(e['supportLastTestBarArray'], e['latestSupportIndex'])
            # Pine 1620
            rt.arr_remove(e['supportLastTestTypeArray'], e['latestSupportIndex'])
            # Pine 1621
            rt.arr_remove(e['supportStrengthArray'], e['latestSupportIndex'])
            # Pine 1622
            rt.arr_remove(e['supportStrongRejectArray'], e['latestSupportIndex'])
            # Pine 1623
            rt.arr_remove(e['supportMaxPenetrationArray'], e['latestSupportIndex'])
            # Pine 1624
            rt.arr_remove(e['supportMaxWickRatioArray'], e['latestSupportIndex'])
            # Pine 1625
            rt.arr_remove(e['supportMaxReactionArray'], e['latestSupportIndex'])
            # Pine 1626
            rt.arr_remove(e['supportApproachDirectionArray'], e['latestSupportIndex'])
            # Pine 1627
            rt.arr_remove(e['supportOriginTimeArray'], e['latestSupportIndex'])
            # Pine 1628
            rt.arr_remove(e['supportScoreArray'], e['latestSupportIndex'])
            # Pine 1629
            rt.arr_remove(e['supportESArray'], e['latestSupportIndex'])
            # Pine 1630
            rt.arr_remove(e['supportZoneATRArray'], e['latestSupportIndex'])

def update_institutional_support(e):
    # Pine 1647
    e['isInstSupportQualificationTF'] = rt.binary('==', e['timeframe.period'], '240')
    # Pine 1648
    e['isInstSupportAvailableOnAllTF'] = True
    # Pine 1649
    if rt.truth((rt.truth((rt.truth(e['barstate.isconfirmed']) and rt.truth(e['isInstSupportQualificationTF']))) and rt.truth(rt.binary('>', rt.arr_size(e['supportZoneIDArray']), 0)))):
        # Pine 1650
        for e['i'] in rt.inclusive(0, rt.binary('-', rt.arr_size(e['supportZoneIDArray']), 1)):
            # Pine 1651
            e['instSupportZoneID'] = rt.arr_get(e['supportZoneIDArray'], e['i'])
            # Pine 1652
            e['existinginstSupportZone'] = rt.arr_indexof(e['instSupportZoneIDArray'], e['instSupportZoneID'])
            # Pine 1654
            if rt.truth(rt.binary('!=', e['existinginstSupportZone'], rt.neg(1))):
                # Pine 1655
                continue
            # Pine 1657
            e['instSupportTouches'] = rt.arr_get(e['supportTouchArray'], e['i'])
            # Pine 1658
            e['instSupportStrongRejects'] = rt.arr_get(e['supportStrongRejectArray'], e['i'])
            # Pine 1659
            e['instSupportQualificationScore'] = 0.0
            # Pine 1661
            e['instSupportQualificationScore'] = rt.binary('+', e['instSupportQualificationScore'], rt.binary('*', e['instSupportStrongRejects'], 5))
            # Pine 1663
            e['instSupportWeakTouches'] = rt.binary('-', e['instSupportTouches'], e['instSupportStrongRejects'])
            # Pine 1665
            if rt.truth(rt.binary('>', e['instSupportWeakTouches'], 0)):
                # Pine 1666
                e['instSupportQualificationScore'] = rt.binary('+', e['instSupportQualificationScore'], rt.binary('*', e['instSupportWeakTouches'], 3))
            # Pine 1668
            e['instSupportQualificationScore'] = rt.math_max(0, rt.math_min(50, e['instSupportQualificationScore']))
            # Pine 1670
            e['instQualifiedSupport'] = rt.binary('>=', e['instSupportQualificationScore'], 50)
            # Pine 1672
            if rt.truth((not rt.truth(e['instQualifiedSupport']))):
                # Pine 1673
                continue
            # Pine 1675
            rt.arr_push(e['instSupportZoneIDArray'], e['instSupportZoneID'])
            # Pine 1676
            rt.arr_push(e['instSupportScoreArray'], e['instSupportQualificationScore'])
            # Pine 1677
            rt.arr_push(e['instSupportStrengthArray'], 0)
            # Pine 1678
            rt.arr_push(e['instQualifiedSupportTFListArray'], ',240:0,')
            # Pine 1679
            rt.arr_push(e['instSupportFailureCountArray'], 0)
            # Pine 1680
            rt.arr_push(e['InstSupportBreakBarArray'], rt.NA)
    # Pine 1705
    if rt.truth((rt.truth(e['barstate.isconfirmed']) and rt.truth(rt.binary('>', rt.arr_size(e['instSupportZoneIDArray']), 0)))):
        # Pine 1706
        for e['i'] in rt.inclusive(0, rt.binary('-', rt.arr_size(e['instSupportZoneIDArray']), 1)):
            # Pine 1707
            e['instSupportZoneID'] = rt.arr_get(e['instSupportZoneIDArray'], e['i'])
            # Pine 1708
            e['dynamicSupportIndex'] = rt.arr_indexof(e['supportZoneIDArray'], e['instSupportZoneID'])
            # Pine 1710
            if rt.truth(rt.binary('==', e['dynamicSupportIndex'], rt.neg(1))):
                # Pine 1711
                continue
            # Pine 1713
            e['instSupportfailureCount'] = rt.arr_get(e['instSupportFailureCountArray'], e['i'])
            # Pine 1716
            e['instSupportTouches'] = rt.arr_get(e['supportTouchArray'], e['dynamicSupportIndex'])
            # Pine 1717
            e['instSupportStrongRejects'] = rt.arr_get(e['supportStrongRejectArray'], e['dynamicSupportIndex'])
            # Pine 1718
            e['instSupportReactionScore'] = 0.0
            # Pine 1720
            e['instSupportReactionScore'] = rt.binary('+', e['instSupportReactionScore'], rt.binary('*', e['instSupportStrongRejects'], 5))
            # Pine 1722
            e['instSupportWeakTouches'] = rt.binary('-', e['instSupportTouches'], e['instSupportStrongRejects'])
            # Pine 1723
            if rt.truth(rt.binary('>', e['instSupportWeakTouches'], 0)):
                # Pine 1724
                e['instSupportReactionScore'] = rt.binary('+', e['instSupportReactionScore'], rt.binary('*', e['instSupportWeakTouches'], 3))
            # Pine 1726
            e['instSupportfailureScore'] = rt.binary('*', e['instSupportfailureCount'], 5)
            # Pine 1727
            e['instSupportFinalScore'] = rt.binary('-', e['instSupportReactionScore'], e['instSupportfailureScore'])
            # Pine 1728
            rt.arr_set(e['instSupportScoreArray'], e['i'], e['instSupportFinalScore'])
            # Pine 1735
            e['dynamicSupportLow'] = rt.arr_get(e['supportLowArray'], e['dynamicSupportIndex'])
            # Pine 1736
            e['dynamicSupportHigh'] = rt.arr_get(e['supportHighArray'], e['dynamicSupportIndex'])
            # Pine 1737
            e['validInstSupport'] = rt.binary('<=', e['dynamicSupportHigh'], e['c'])
            # Pine 1738
            if rt.truth((not rt.truth(e['validInstSupport']))):
                # Pine 1739
                continue
            # Pine 1741
            e['instSupportDistanceATR'] = rt.binary('/', rt.binary('-', e['c'], e['dynamicSupportHigh']), e['atr'])
            # Pine 1742
            e['instSupportES'] = rt.arr_get(e['supportESArray'], e['dynamicSupportIndex'])
            # Pine 1744
            if rt.truth((rt.truth(rt.is_na(e['nearestInstSupportDistanceATR'])) or rt.truth(rt.binary('<', e['instSupportDistanceATR'], e['nearestInstSupportDistanceATR'])))):
                # Pine 1745
                e['nearestInstSupportDistanceATR'] = e['instSupportDistanceATR']
                # Pine 1746
                e['nearestInstSupport'] = e['dynamicSupportHigh']
                # Pine 1747
                e['nearestInstSupportScore'] = rt.arr_get(e['instSupportScoreArray'], e['i'])
                # Pine 1748
                e['nearestInstSupportStrength'] = rt.arr_get(e['instSupportStrengthArray'], e['i'])
                # Pine 1749
                e['nearestInstSupportZoneID'] = e['instSupportZoneID']
                # Pine 1750
                e['nearestInstSupportES'] = e['instSupportES']
                # Pine 1751
                e['lastTestBar'] = rt.arr_get(e['supportLastTestBarArray'], e['dynamicSupportIndex'])
                # Pine 1752
                e['nearestInstSupportLastTestAge'] = (rt.binary('-', e['bar_index'], e['lastTestBar']) if rt.truth((not rt.truth(rt.is_na(e['lastTestBar'])))) else rt.NA)
                # Pine 1753
                e['nearestInstSupportLastTestType'] = rt.arr_get(e['supportLastTestTypeArray'], e['dynamicSupportIndex'])
            # Pine 1774
            e['instSupportZoneLow'] = rt.arr_get(e['supportLowArray'], e['dynamicSupportIndex'])
            # Pine 1775
            e['instSupportZoneHigh'] = rt.arr_get(e['supportHighArray'], e['dynamicSupportIndex'])
            # Pine 1776
            e['instSupportZoneBar'] = rt.arr_get(e['supportBarArray'], e['dynamicSupportIndex'])
            # Pine 1777
            e['instQualifiedSupportTFList'] = rt.arr_get(e['instQualifiedSupportTFListArray'], e['i'])
            # Pine 1778
            e['currentInstSupportTFTag'] = e['timeframe.period']
            # Pine 1779
            e['isInstSupportObservationTF'] = (rt.truth((rt.truth((rt.truth(rt.binary('==', e['currentInstSupportTFTag'], '240')) or rt.truth(rt.binary('==', e['currentInstSupportTFTag'], '1D')))) or rt.truth(rt.binary('==', e['currentInstSupportTFTag'], '1W')))) or rt.truth(rt.binary('==', e['currentInstSupportTFTag'], '1M')))
            # Pine 1785
            if rt.truth((not rt.truth(e['isInstSupportObservationTF']))):
                # Pine 1786
                continue
            # Pine 1788
            e['currentSupportTFToken'] = rt.binary('+', rt.binary('+', ',', e['currentInstSupportTFTag']), ':')
            # Pine 1790
            e['instSupportZoneInCurrentTF'] = (rt.truth((rt.truth(rt.binary('>', e['time'], rt.arr_get(e['supportOriginTimeArray'], e['dynamicSupportIndex']))) and rt.truth(rt.binary('<=', e['l'], e['instSupportZoneHigh'])))) and rt.truth(rt.binary('>=', e['h'], e['instSupportZoneLow'])))
            # Pine 1795
            e['currentSupportTFAlreadyStored'] = rt.str_contains(e['instQualifiedSupportTFList'], e['currentSupportTFToken'])
            # Pine 1797
            if rt.truth((rt.truth((rt.truth(e['barstate.isconfirmed']) and rt.truth(e['instSupportZoneInCurrentTF']))) and rt.truth((not rt.truth(e['currentSupportTFAlreadyStored']))))):
                # Pine 1798
                e['instQualifiedSupportTFList'] = rt.binary('+', e['instQualifiedSupportTFList'], rt.binary('+', e['currentInstSupportTFTag'], ':0,'))
                # Pine 1799
                rt.arr_set(e['instQualifiedSupportTFListArray'], e['i'], e['instQualifiedSupportTFList'])
            # Pine 1801
            e['interactionWeight'] = 0.0
            # Pine 1802
            e['rejectionWeight'] = 0.0
            # Pine 1803
            e['failureWeight'] = 0.0
            # Pine 1805
            if rt.truth(rt.binary('==', e['currentInstSupportTFTag'], '240')):
                # Pine 1806
                e['interactionWeight'] = 1.0
                # Pine 1807
                e['rejectionWeight'] = 2.0
                # Pine 1808
                e['failureWeight'] = rt.neg(2.0)
            # Pine 1810
            elif rt.truth(rt.binary('==', e['currentInstSupportTFTag'], '1D')):
                # Pine 1811
                e['interactionWeight'] = 6.0
                # Pine 1812
                e['rejectionWeight'] = 12.0
                # Pine 1813
                e['failureWeight'] = rt.neg(12.0)
            # Pine 1815
            elif rt.truth(rt.binary('==', e['currentInstSupportTFTag'], '1W')):
                # Pine 1816
                e['interactionWeight'] = 42.0
                # Pine 1817
                e['rejectionWeight'] = 84.0
                # Pine 1818
                e['failureWeight'] = rt.neg(84.0)
            # Pine 1820
            elif rt.truth(rt.binary('==', e['currentInstSupportTFTag'], '1M')):
                # Pine 1821
                e['interactionWeight'] = 180.0
                # Pine 1822
                e['rejectionWeight'] = 360.0
                # Pine 1823
                e['failureWeight'] = rt.neg(360.0)
            # Pine 1825
            e['currentTokenPosition'] = rt.str_pos(e['instQualifiedSupportTFList'], e['currentSupportTFToken'])
            # Pine 1826
            e['currentTFStrength'] = 0.0
            # Pine 1828
            if rt.truth(rt.binary('!=', e['currentTokenPosition'], rt.neg(1))):
                # Pine 1829
                e['currentValueStart'] = rt.binary('+', e['currentTokenPosition'], rt.str_length(e['currentSupportTFToken']))
                # Pine 1830
                e['remainingTFString'] = rt.str_substring(e['instQualifiedSupportTFList'], e['currentValueStart'])
                # Pine 1831
                e['commaPosition'] = rt.str_pos(e['remainingTFString'], ',')
                # Pine 1833
                if rt.truth(rt.binary('!=', e['commaPosition'], rt.neg(1))):
                    # Pine 1834
                    e['currentTFValueString'] = rt.str_substring(e['remainingTFString'], 0, e['commaPosition'])
                    # Pine 1835
                    e['parsedCurrentTFStrength'] = rt.str_tonumber(e['currentTFValueString'])
                    # Pine 1837
                    if rt.truth((not rt.truth(rt.is_na(e['parsedCurrentTFStrength'])))):
                        # Pine 1838
                        e['currentTFStrength'] = e['parsedCurrentTFStrength']
            # Pine 1839
            e['dynamicLastTestBar'] = rt.arr_get(e['supportLastTestBarArray'], e['dynamicSupportIndex'])
            # Pine 1840
            e['dynamicLastTestType'] = rt.arr_get(e['supportLastTestTypeArray'], e['dynamicSupportIndex'])
            # Pine 1841
            e['dynamicBreakBar'] = rt.arr_get(e['InstSupportBreakBarArray'], e['i'])
            # Pine 1842
            e['eventDelta'] = 0.0
            # Pine 1844
            if rt.truth((rt.truth((not rt.truth(rt.is_na(e['dynamicBreakBar'])))) and rt.truth(rt.binary('==', e['dynamicBreakBar'], e['bar_index'])))):
                # Pine 1845
                e['eventDelta'] = e['failureWeight']
            # Pine 1847
            elif rt.truth((rt.truth((not rt.truth(rt.is_na(e['dynamicLastTestBar'])))) and rt.truth(rt.binary('==', e['dynamicLastTestBar'], e['bar_index'])))):
                # Pine 1849
                if rt.truth(rt.binary('==', e['dynamicLastTestType'], 'STRONG_REJECTION')):
                    # Pine 1850
                    e['eventDelta'] = e['rejectionWeight']
                # Pine 1852
                elif rt.truth(rt.binary('==', e['dynamicLastTestType'], 'WEAK_REACTION')):
                    # Pine 1853
                    e['eventDelta'] = e['interactionWeight']
            # Pine 1855
            if rt.truth(rt.binary('!=', e['eventDelta'], 0)):
                # Pine 1856
                e['newTFStrength'] = rt.binary('+', e['currentTFStrength'], e['eventDelta'])
                # Pine 1859
                if rt.truth(rt.binary('==', e['currentTokenPosition'], rt.neg(1))):
                    # Pine 1860
                    e['instQualifiedSupportTFList'] = rt.binary('+', e['instQualifiedSupportTFList'], rt.binary('+', rt.binary('+', rt.binary('+', e['currentInstSupportTFTag'], ':'), rt.str_tostring(e['newTFStrength'])), ','))
                # Pine 1862
                else:
                    # Pine 1863
                    e['valueStart'] = rt.binary('+', e['currentTokenPosition'], rt.str_length(e['currentSupportTFToken']))
                    # Pine 1864
                    e['remainingTFString'] = rt.str_substring(e['instQualifiedSupportTFList'], e['valueStart'])
                    # Pine 1865
                    e['commaPosition'] = rt.str_pos(e['remainingTFString'], ',')
                    # Pine 1867
                    if rt.truth(rt.binary('!=', e['commaPosition'], rt.neg(1))):
                        # Pine 1868
                        e['tokenEnd'] = rt.binary('+', e['valueStart'], e['commaPosition'])
                        # Pine 1870
                        e['instQualifiedSupportTFList'] = rt.binary('+', rt.binary('+', rt.str_substring(e['instQualifiedSupportTFList'], 0, e['valueStart']), rt.str_tostring(e['newTFStrength'])), rt.str_substring(e['instQualifiedSupportTFList'], e['tokenEnd']))
                # Pine 1875
                e['currentTotalStrength'] = rt.arr_get(e['instSupportStrengthArray'], e['i'])
                # Pine 1877
                rt.arr_set(e['instSupportStrengthArray'], e['i'], rt.binary('+', e['currentTotalStrength'], rt.to_int(e['eventDelta'])))
                # Pine 1878
                rt.arr_set(e['instQualifiedSupportTFListArray'], e['i'], e['instQualifiedSupportTFList'])
        # Pine 1880
        e['nearInstSupport'] = (rt.truth(rt.binary('>', e['nearestInstSupportES'], 0)) and rt.truth(rt.binary('<=', e['nearestInstSupportDistanceATR'], e['srZoneDistanceATR'])))
    # Pine 1884
    e['dynamicSupportScoreSum'] = 0.0
    # Pine 1885
    e['dynamicSupportESSum'] = 0.0
    # Pine 1886
    e['dynamicSupportCount'] = 0
    # Pine 1887
    e['dynamicSupportLastTestAgeSum'] = 0.0
    # Pine 1888
    e['minDynamicSupportLastTestAge'] = rt.NA
    # Pine 1889
    e['maxDynamicSupportLastTestAge'] = rt.NA
    # Pine 1890
    e['dynamicSupportLastTestAgeCount'] = 0
    # Pine 1891
    e['minDynamicSupportES'] = rt.NA
    # Pine 1892
    e['maxDynamicSupportES'] = rt.NA
    # Pine 1893
    e['minDynamicSupportWeakTouches'] = rt.NA
    # Pine 1894
    e['maxDynamicSupportWeakTouches'] = rt.NA
    # Pine 1895
    e['minDynamicSupportStrongTouches'] = rt.NA
    # Pine 1896
    e['maxDynamicSupportStrongTouches'] = rt.NA
    # Pine 1897
    if rt.truth(rt.binary('>', rt.arr_size(e['supportScoreArray']), 0)):
        # Pine 1898
        for e['i'] in rt.inclusive(0, rt.binary('-', rt.arr_size(e['supportScoreArray']), 1)):
            # Pine 1899
            e['zoneID'] = rt.arr_get(e['supportZoneIDArray'], e['i'])
            # Pine 1900
            e['isInstitutionalZone'] = rt.binary('!=', rt.arr_indexof(e['instSupportZoneIDArray'], e['zoneID']), rt.neg(1))
            # Pine 1901
            if rt.truth((not rt.truth(e['isInstitutionalZone']))):
                # Pine 1902
                e['supportES'] = rt.arr_get(e['supportESArray'], e['i'])
                # Pine 1903
                e['supportScore'] = rt.arr_get(e['supportScoreArray'], e['i'])
                # Pine 1904
                e['strongTouches'] = rt.arr_get(e['supportStrongRejectArray'], e['i'])
                # Pine 1905
                e['totalTouches'] = rt.arr_get(e['supportTouchArray'], e['i'])
                # Pine 1906
                e['weakTouches'] = rt.math_max(0.0, rt.binary('-', e['totalTouches'], e['strongTouches']))
                # Pine 1907
                e['dynamicSupportScoreSum'] = rt.binary('+', e['dynamicSupportScoreSum'], rt.arr_get(e['supportScoreArray'], e['i']))
                # Pine 1908
                e['dynamicSupportESSum'] = rt.binary('+', e['dynamicSupportESSum'], rt.arr_get(e['supportESArray'], e['i']))
                # Pine 1909
                e['dynamicSupportCount'] = rt.binary('+', e['dynamicSupportCount'], 1)
                # Pine 1910
                e['minDynamicSupportES'] = (e['supportES'] if rt.truth(rt.is_na(e['minDynamicSupportES'])) else rt.math_min(e['minDynamicSupportES'], e['supportES']))
                # Pine 1911
                e['maxDynamicSupportES'] = (e['supportES'] if rt.truth(rt.is_na(e['maxDynamicSupportES'])) else rt.math_max(e['maxDynamicSupportES'], e['supportES']))
                # Pine 1912
                e['minDynamicSupportWeakTouches'] = (rt.to_int(e['weakTouches']) if rt.truth(rt.is_na(e['minDynamicSupportWeakTouches'])) else rt.math_min(e['minDynamicSupportWeakTouches'], rt.to_int(e['weakTouches'])))
                # Pine 1913
                e['maxDynamicSupportWeakTouches'] = (rt.to_int(e['weakTouches']) if rt.truth(rt.is_na(e['maxDynamicSupportWeakTouches'])) else rt.math_max(e['maxDynamicSupportWeakTouches'], rt.to_int(e['weakTouches'])))
                # Pine 1914
                e['minDynamicSupportStrongTouches'] = (rt.to_int(e['strongTouches']) if rt.truth(rt.is_na(e['minDynamicSupportStrongTouches'])) else rt.math_min(e['minDynamicSupportStrongTouches'], rt.to_int(e['strongTouches'])))
                # Pine 1915
                e['maxDynamicSupportStrongTouches'] = (rt.to_int(e['strongTouches']) if rt.truth(rt.is_na(e['maxDynamicSupportStrongTouches'])) else rt.math_max(e['maxDynamicSupportStrongTouches'], rt.to_int(e['strongTouches'])))
                # Pine 1917
                e['lastTestBar'] = rt.arr_get(e['supportLastTestBarArray'], e['i'])
                # Pine 1918
                if rt.truth((not rt.truth(rt.is_na(e['lastTestBar'])))):
                    # Pine 1919
                    e['lastTestAge'] = rt.math_max(0.0, rt.binary('-', e['bar_index'], e['lastTestBar']))
                    # Pine 1920
                    e['dynamicSupportLastTestAgeSum'] = rt.binary('+', e['dynamicSupportLastTestAgeSum'], e['lastTestAge'])
                    # Pine 1921
                    e['dynamicSupportLastTestAgeCount'] = rt.binary('+', e['dynamicSupportLastTestAgeCount'], 1)
                    # Pine 1922
                    e['minDynamicSupportLastTestAge'] = (e['lastTestAge'] if rt.truth(rt.is_na(e['minDynamicSupportLastTestAge'])) else rt.math_min(e['minDynamicSupportLastTestAge'], e['lastTestAge']))
                    # Pine 1923
                    e['maxDynamicSupportLastTestAge'] = (e['lastTestAge'] if rt.truth(rt.is_na(e['maxDynamicSupportLastTestAge'])) else rt.math_max(e['maxDynamicSupportLastTestAge'], e['lastTestAge']))
    # Pine 1925
    e['averageDynamicSupportScore'] = (rt.binary('/', e['dynamicSupportScoreSum'], e['dynamicSupportCount']) if rt.truth(rt.binary('>', e['dynamicSupportCount'], 0)) else rt.NA)
    # Pine 1926
    e['averageDynamicSupportES'] = (rt.binary('/', e['dynamicSupportESSum'], e['dynamicSupportCount']) if rt.truth(rt.binary('>', e['dynamicSupportCount'], 0)) else rt.NA)
    # Pine 1927
    e['averageDynamicSupportLastTestAge'] = (rt.binary('/', e['dynamicSupportLastTestAgeSum'], e['dynamicSupportLastTestAgeCount']) if rt.truth(rt.binary('>', e['dynamicSupportLastTestAgeCount'], 0)) else rt.NA)
    # Pine 1928
    e['dynamicSupportWTNormalized'] = rt.normalize(e['nearestSupportWeakTouches'], e['minDynamicSupportWeakTouches'], e['maxDynamicSupportWeakTouches'], e['normalizationPower'], True)
    # Pine 1929
    e['dynamicSupportSTNormalized'] = rt.normalize(e['nearestSupportStrongTouches'], e['minDynamicSupportStrongTouches'], e['maxDynamicSupportStrongTouches'], e['normalizationPower'], True)
    # Pine 1930
    e['dynamicSupportESNormalized'] = rt.normalize(e['nearestSupportES'], e['minDynamicSupportES'], e['maxDynamicSupportES'], e['normalizationPower'], True)
    # Pine 1931
    e['dynamicSupportLastTestAgeNormalized'] = rt.normalize(e['nearestSupportLastTestAge'], e['minDynamicSupportLastTestAge'], e['maxDynamicSupportLastTestAge'], e['normalizationPower'], False)
    # Pine 1935
    e['instSupportScoreSum'] = 0.0
    # Pine 1936
    e['instSupportESSum'] = 0.0
    # Pine 1937
    e['instSupportCount'] = 0
    # Pine 1938
    e['instSupportLastTestAgeSum'] = 0.0
    # Pine 1939
    e['instSupportLastTestAgeCount'] = 0
    # Pine 1940
    e['minInstSupportLastTestAge'] = rt.NA
    # Pine 1941
    e['maxInstSupportLastTestAge'] = rt.NA
    # Pine 1942
    e['minInstSupportES'] = rt.NA
    # Pine 1943
    e['maxInstSupportES'] = rt.NA
    # Pine 1944
    e['minInstSupportWeakTouches'] = rt.NA
    # Pine 1945
    e['maxInstSupportWeakTouches'] = rt.NA
    # Pine 1946
    e['minInstSupportStrongTouches'] = rt.NA
    # Pine 1947
    e['maxInstSupportStrongTouches'] = rt.NA
    # Pine 1948
    e['minInstSupportFailures'] = rt.NA
    # Pine 1949
    e['maxInstSupportFailures'] = rt.NA
    # Pine 1950
    if rt.truth(rt.binary('>', rt.arr_size(e['instSupportZoneIDArray']), 0)):
        # Pine 1951
        for e['i'] in rt.inclusive(0, rt.binary('-', rt.arr_size(e['instSupportZoneIDArray']), 1)):
            # Pine 1952
            e['instZoneID'] = rt.arr_get(e['instSupportZoneIDArray'], e['i'])
            # Pine 1953
            e['dynamicIndex'] = rt.arr_indexof(e['supportZoneIDArray'], e['instZoneID'])
            # Pine 1955
            if rt.truth(rt.binary('!=', e['dynamicIndex'], rt.neg(1))):
                # Pine 1956
                e['supportES'] = rt.arr_get(e['supportESArray'], e['dynamicIndex'])
                # Pine 1957
                e['supportScore'] = rt.arr_get(e['instSupportScoreArray'], e['i'])
                # Pine 1958
                e['strongTouches'] = rt.arr_get(e['supportStrongRejectArray'], e['dynamicIndex'])
                # Pine 1959
                e['totalTouches'] = rt.arr_get(e['supportTouchArray'], e['dynamicIndex'])
                # Pine 1960
                e['weakTouches'] = rt.math_max(0.0, rt.binary('-', e['totalTouches'], e['strongTouches']))
                # Pine 1961
                e['instFailures'] = rt.arr_get(e['instSupportFailureCountArray'], e['i'])
                # Pine 1962
                e['instSupportScoreSum'] = rt.binary('+', e['instSupportScoreSum'], rt.arr_get(e['instSupportScoreArray'], e['i']))
                # Pine 1963
                e['instSupportESSum'] = rt.binary('+', e['instSupportESSum'], rt.arr_get(e['supportESArray'], e['dynamicIndex']))
                # Pine 1964
                e['instSupportCount'] = rt.binary('+', e['instSupportCount'], 1)
                # Pine 1965
                e['minInstSupportES'] = (e['supportES'] if rt.truth(rt.is_na(e['minInstSupportES'])) else rt.math_min(e['minInstSupportES'], e['supportES']))
                # Pine 1966
                e['maxInstSupportES'] = (e['supportES'] if rt.truth(rt.is_na(e['maxInstSupportES'])) else rt.math_max(e['maxInstSupportES'], e['supportES']))
                # Pine 1967
                e['minInstSupportWeakTouches'] = (rt.to_int(e['weakTouches']) if rt.truth(rt.is_na(e['minInstSupportWeakTouches'])) else rt.math_min(e['minInstSupportWeakTouches'], rt.to_int(e['weakTouches'])))
                # Pine 1968
                e['maxInstSupportWeakTouches'] = (rt.to_int(e['weakTouches']) if rt.truth(rt.is_na(e['maxInstSupportWeakTouches'])) else rt.math_max(e['maxInstSupportWeakTouches'], rt.to_int(e['weakTouches'])))
                # Pine 1969
                e['minInstSupportStrongTouches'] = (rt.to_int(e['strongTouches']) if rt.truth(rt.is_na(e['minInstSupportStrongTouches'])) else rt.math_min(e['minInstSupportStrongTouches'], rt.to_int(e['strongTouches'])))
                # Pine 1970
                e['maxInstSupportStrongTouches'] = (rt.to_int(e['strongTouches']) if rt.truth(rt.is_na(e['maxInstSupportStrongTouches'])) else rt.math_max(e['maxInstSupportStrongTouches'], rt.to_int(e['strongTouches'])))
                # Pine 1971
                e['minInstSupportStrongTouches'] = (rt.to_int(e['instFailures']) if rt.truth(rt.is_na(e['minInstSupportFailures'])) else rt.math_min(e['minInstSupportFailures'], rt.to_int(e['instFailures'])))
                # Pine 1972
                e['maxInstSupportStrongTouches'] = (rt.to_int(e['instFailures']) if rt.truth(rt.is_na(e['maxInstSupportFailures'])) else rt.math_max(e['maxInstSupportFailures'], rt.to_int(e['instFailures'])))
                # Pine 1974
                e['lastTestBar'] = rt.arr_get(e['supportLastTestBarArray'], e['dynamicIndex'])
                # Pine 1975
                if rt.truth((not rt.truth(rt.is_na(e['lastTestBar'])))):
                    # Pine 1976
                    e['lastTestAge'] = rt.math_max(0.0, rt.binary('-', e['bar_index'], e['lastTestBar']))
                    # Pine 1977
                    e['instSupportLastTestAgeSum'] = rt.binary('+', e['instSupportLastTestAgeSum'], e['lastTestAge'])
                    # Pine 1978
                    e['instSupportLastTestAgeCount'] = rt.binary('+', e['instSupportLastTestAgeCount'], 1)
                    # Pine 1979
                    e['minInstSupportLastTestAge'] = (e['lastTestAge'] if rt.truth(rt.is_na(e['minInstSupportLastTestAge'])) else rt.math_min(e['minInstSupportLastTestAge'], e['lastTestAge']))
                    # Pine 1980
                    e['maxInstSupportLastTestAge'] = (e['lastTestAge'] if rt.truth(rt.is_na(e['maxInstSupportLastTestAge'])) else rt.math_max(e['maxInstSupportLastTestAge'], e['lastTestAge']))
    # Pine 1982
    e['averageInstSupportScore'] = (rt.binary('/', e['instSupportScoreSum'], e['instSupportCount']) if rt.truth(rt.binary('>', e['instSupportCount'], 0)) else rt.NA)
    # Pine 1983
    e['averageInstSupportES'] = (rt.binary('/', e['instSupportESSum'], e['instSupportCount']) if rt.truth(rt.binary('>', e['instSupportCount'], 0)) else rt.NA)
    # Pine 1984
    e['averageInstSupportLastTestAge'] = (rt.binary('/', e['instSupportLastTestAgeSum'], e['instSupportLastTestAgeCount']) if rt.truth(rt.binary('>', e['instSupportLastTestAgeCount'], 0)) else rt.NA)
    # Pine 1985
    e['instSupportLastTestAgeNormalized'] = rt.normalize(e['nearestInstSupportLastTestAge'], e['minInstSupportLastTestAge'], e['maxInstSupportLastTestAge'], e['normalizationPower'], False)
    # Pine 1986
    e['instSupportWTNormalized'] = rt.normalize(e['nearestSupportWeakTouches'], e['minInstSupportWeakTouches'], e['maxInstSupportWeakTouches'], e['normalizationPower'], True)
    # Pine 1987
    e['instSupportSTNormalized'] = rt.normalize(e['nearestSupportStrongTouches'], e['minInstSupportStrongTouches'], e['maxInstSupportStrongTouches'], e['normalizationPower'], True)
    # Pine 1988
    e['instSupportFailureNormalized'] = rt.normalize(e['nearestInstSupportFailureCount'], e['minInstSupportFailures'], e['maxInstSupportFailures'], e['normalizationPower'], True)
    # Pine 1989
    e['instSupportESNormalized'] = rt.normalize(e['nearestInstSupportES'], e['minInstSupportES'], e['maxInstSupportES'], e['normalizationPower'], True)

def update_resistance_zones(e):
    # Pine 1994
    if rt.truth(rt.binary('>', rt.arr_size(e['resistanceLowArray']), 0)):
        # Pine 1995
        for e['resistanceZoneI'] in rt.inclusive(0, rt.binary('-', rt.arr_size(e['resistanceLowArray']), 1)):
            # Pine 1996
            e['resistanceZoneLow'] = rt.arr_get(e['resistanceLowArray'], e['resistanceZoneI'])
            # Pine 1997
            e['resistanceZoneHigh'] = rt.arr_get(e['resistanceHighArray'], e['resistanceZoneI'])
            # Pine 1998
            e['wasInsideResistanceZone'] = rt.arr_get(e['prevCandleInsideResistanceZoneArray'], e['resistanceZoneI'])
            # Pine 1999
            e['insideResistanceZone'] = (rt.truth((rt.truth(rt.binary('>', e['bar_index'], rt.arr_get(e['resistanceBarArray'], e['resistanceZoneI']))) and rt.truth(rt.binary('<=', e['l'], e['resistanceZoneHigh'])))) and rt.truth(rt.binary('>=', e['h'], e['resistanceZoneLow'])))
            # Pine 2000
            e['oldDirection'] = rt.arr_get(e['resistanceApproachDirectionArray'], e['resistanceZoneI'])
            # Pine 2001
            e['approachDirection'] = e['oldDirection']
            # Pine 2003
            if rt.truth((rt.truth((rt.truth((rt.truth(e['barstate.isconfirmed']) and rt.truth(rt.binary('<', e['c'], e['resistanceZoneLow'])))) and rt.truth((not rt.truth(e['insideResistanceZone']))))) and rt.truth((not rt.truth(e['wasInsideResistanceZone']))))):
                # Pine 2004
                e['approachDirection'] = 1
            # Pine 2006
            rt.arr_set(e['resistanceApproachDirectionArray'], e['resistanceZoneI'], e['approachDirection'])
    # Pine 2009
    if rt.truth((rt.truth((rt.truth(e['barstate.isconfirmed']) and rt.truth((not rt.truth(rt.is_na(e['srPivotHigh'])))))) and rt.truth(rt.binary('>=', e['resistanceReactionATR'], e['srReactionATR'])))):
        # Pine 2010
        e['potentialResistanceLow'] = rt.binary('-', e['srPivotHigh'], e['srZoneSize'])
        # Pine 2011
        e['potentialResistanceHigh'] = rt.binary('+', e['srPivotHigh'], e['srZoneSize'])
        # Pine 2012
        e['insideInstitutionalResistance'] = False
        # Pine 2014
        if rt.truth(rt.binary('>', rt.arr_size(e['instResistanceZoneIDArray']), 0)):
            # Pine 2015
            for e['instI'] in rt.inclusive(0, rt.binary('-', rt.arr_size(e['instResistanceZoneIDArray']), 1)):
                # Pine 2016
                e['instResistanceZoneID'] = rt.arr_get(e['instResistanceZoneIDArray'], e['instI'])
                # Pine 2018
                e['instDynamicIndex'] = rt.arr_indexof(e['resistanceZoneIDArray'], e['instResistanceZoneID'])
                # Pine 2020
                if rt.truth(rt.binary('!=', e['instDynamicIndex'], rt.neg(1))):
                    # Pine 2021
                    e['instResistanceZoneLow'] = rt.arr_get(e['resistanceLowArray'], e['instDynamicIndex'])
                    # Pine 2022
                    e['instResistanceZoneHigh'] = rt.arr_get(e['resistanceHighArray'], e['instDynamicIndex'])
                    # Pine 2023
                    e['institutionalResistanceOverlap'] = (rt.truth(rt.binary('<=', e['potentialResistanceLow'], e['instResistanceZoneHigh'])) and rt.truth(rt.binary('>=', e['potentialResistanceHigh'], e['instResistanceZoneLow'])))
                    # Pine 2025
                    if rt.truth(e['institutionalResistanceOverlap']):
                        # Pine 2026
                        e['insideInstitutionalResistance'] = True
                        # Pine 2027
                        break
        # Pine 2031
        if rt.truth((not rt.truth(e['insideInstitutionalResistance']))):
            # Pine 2032
            e['nextResistanceZoneSequence'] = rt.binary('+', e['nextResistanceZoneSequence'], 1)
            # Pine 2033
            e['newResistanceZoneID'] = rt.binary('+', rt.binary('+', e['zoneTFPrefix'], '-R-'), rt.str_tostring(e['nextResistanceZoneSequence'], '000000'))
            # Pine 2034
            rt.arr_push(e['resistanceZoneIDArray'], e['newResistanceZoneID'])
            # Pine 2035
            rt.arr_push(e['resistanceLowArray'], rt.binary('-', e['srPivotHigh'], e['srZoneSize']))
            # Pine 2036
            rt.arr_push(e['resistanceHighArray'], rt.binary('+', e['srPivotHigh'], e['srZoneSize']))
            # Pine 2037
            rt.arr_push(e['resistanceOriginArray'], e['srPivotHigh'])
            # Pine 2038
            rt.arr_push(e['resistanceBarArray'], rt.binary('-', e['bar_index'], e['srPivotRight']))
            # Pine 2039
            rt.arr_push(e['resistanceTouchArray'], 0)
            # Pine 2040
            rt.arr_push(e['prevCandleInsideResistanceZoneArray'], False)
            # Pine 2041
            rt.arr_push(e['resistanceLastTestBarArray'], rt.NA)
            # Pine 2042
            rt.arr_push(e['resistanceLastTestTypeArray'], 'NO_TEST')
            # Pine 2043
            rt.arr_push(e['resistanceStrengthArray'], 0)
            # Pine 2044
            rt.arr_push(e['resistanceStrongRejectArray'], 0)
            # Pine 2045
            rt.arr_push(e['resistanceMaxPenetrationArray'], 0.0)
            # Pine 2046
            rt.arr_push(e['resistanceMaxWickRatioArray'], 0.0)
            # Pine 2047
            rt.arr_push(e['resistanceMaxReactionArray'], 0.0)
            # Pine 2048
            rt.arr_push(e['resistanceApproachDirectionArray'], 0)
            # Pine 2049
            rt.arr_push(e['resistanceOriginTimeArray'], e.previous('time', e['srPivotRight']))
            # Pine 2050
            rt.arr_push(e['resistanceScoreArray'], 0.0)
            # Pine 2051
            rt.arr_push(e['resistanceESArray'], 0)
            # Pine 2052
            rt.arr_push(e['resistanceZoneATRArray'], e['pivotATR'])
    # Pine 2054
    if rt.truth(rt.binary('>', rt.arr_size(e['resistanceLowArray']), 0)):
        # Pine 2055
        for e['i'] in rt.inclusive(rt.binary('-', rt.arr_size(e['resistanceLowArray']), 1), 0):
            # Pine 2056
            e['resistanceZoneLow'] = rt.arr_get(e['resistanceLowArray'], e['i'])
            # Pine 2057
            e['resistanceZoneHigh'] = rt.arr_get(e['resistanceHighArray'], e['i'])
            # Pine 2058
            e['resistanceZoneDistanceATR'] = ((rt.binary('/', rt.binary('-', e['c'], e['resistanceZoneHigh']), e['atr']) if rt.truth(rt.binary('>', e['c'], e['resistanceZoneHigh'])) else (rt.binary('/', rt.binary('-', e['resistanceZoneLow'], e['c']), e['atr']) if rt.truth(rt.binary('<', e['c'], e['resistanceZoneLow'])) else 0.0)) if rt.truth(rt.binary('>', e['atr'], 0)) else rt.NA)
            # Pine 2059
            e['wasInsideResistanceZone'] = rt.arr_get(e['prevCandleInsideResistanceZoneArray'], e['i'])
            # Pine 2060
            e['insideResistanceZone'] = (rt.truth((rt.truth(rt.binary('>', e['bar_index'], rt.arr_get(e['resistanceBarArray'], e['i']))) and rt.truth(rt.binary('<=', e['l'], e['resistanceZoneHigh'])))) and rt.truth(rt.binary('>=', e['h'], e['resistanceZoneLow'])))
            # Pine 2061
            if rt.truth(e['insideResistanceZone']):
                # Pine 2062
                e['interactingResistanceZoneId'] = e['i']
            # Pine 2063
            if rt.truth(e['barstate.isconfirmed']):
                # Pine 2064
                rt.arr_set(e['prevCandleInsideResistanceZoneArray'], e['i'], e['insideResistanceZone'])
            # Pine 2066
            if rt.truth((rt.truth(rt.binary('>', e['resistanceZoneDistanceATR'], e['srZoneDistanceATR'])) and rt.truth((not rt.truth((rt.truth(e['wasInsideResistanceZone']) or rt.truth(e['insideResistanceZone']))))))):
                # Pine 2067
                continue
            # Pine 2069
            e['resistanceZoneAge'] = rt.binary('-', e['bar_index'], rt.arr_get(e['resistanceBarArray'], e['i']))
            # Pine 2070
            e['lastResistanceTestBar'] = rt.arr_get(e['resistanceLastTestBarArray'], e['i'])
            # Pine 2071
            e['barsSinceResistanceTest'] = (rt.binary('-', e['bar_index'], e['lastResistanceTestBar']) if rt.truth((not rt.truth(rt.is_na(e['lastResistanceTestBar'])))) else e['resistanceZoneAge'])
            # Pine 2072
            e['wasApproachedFromBelow'] = rt.binary('==', rt.arr_get(e['resistanceApproachDirectionArray'], e['i']), 1)
            # Pine 2073
            e['previousCandleCrossedZone'] = (rt.truth((rt.truth((rt.truth(e['barstate.isconfirmed']) and rt.truth(rt.binary('>', e['h1'], e['resistanceZoneHigh'])))) and rt.truth(rt.binary('<', e['l1'], e['resistanceZoneLow'])))) and rt.truth(e['wasApproachedFromBelow']))
            # Pine 2074
            e['resistanceInvalid'] = (rt.truth((rt.truth(e['barstate.isconfirmed']) and rt.truth(rt.binary('>', e['h'], e['resistanceZoneHigh'])))) and rt.truth((rt.truth(e['wasApproachedFromBelow']) or rt.truth(e['previousCandleCrossedZone']))))
            # Pine 2076
            if rt.truth(e['resistanceInvalid']):
                # Pine 2077
                e['zoneID'] = rt.arr_get(e['resistanceZoneIDArray'], e['i'])
                # Pine 2078
                e['instIndex'] = rt.arr_indexof(e['instResistanceZoneIDArray'], e['zoneID'])
                # Pine 2079
                e['isResistanceInstitutional'] = rt.binary('!=', e['instIndex'], rt.neg(1))
                # Pine 2081
                if rt.truth((not rt.truth(e['isResistanceInstitutional']))):
                    # Pine 2082
                    rt.arr_remove(e['resistanceZoneIDArray'], e['i'])
                    # Pine 2083
                    rt.arr_remove(e['resistanceLowArray'], e['i'])
                    # Pine 2084
                    rt.arr_remove(e['resistanceHighArray'], e['i'])
                    # Pine 2085
                    rt.arr_remove(e['resistanceOriginArray'], e['i'])
                    # Pine 2086
                    rt.arr_remove(e['resistanceBarArray'], e['i'])
                    # Pine 2087
                    rt.arr_remove(e['resistanceTouchArray'], e['i'])
                    # Pine 2088
                    rt.arr_remove(e['prevCandleInsideResistanceZoneArray'], e['i'])
                    # Pine 2089
                    rt.arr_remove(e['resistanceLastTestBarArray'], e['i'])
                    # Pine 2090
                    rt.arr_remove(e['resistanceLastTestTypeArray'], e['i'])
                    # Pine 2091
                    rt.arr_remove(e['resistanceStrengthArray'], e['i'])
                    # Pine 2092
                    rt.arr_remove(e['resistanceStrongRejectArray'], e['i'])
                    # Pine 2093
                    rt.arr_remove(e['resistanceMaxPenetrationArray'], e['i'])
                    # Pine 2094
                    rt.arr_remove(e['resistanceMaxWickRatioArray'], e['i'])
                    # Pine 2095
                    rt.arr_remove(e['resistanceMaxReactionArray'], e['i'])
                    # Pine 2096
                    rt.arr_remove(e['resistanceApproachDirectionArray'], e['i'])
                    # Pine 2097
                    rt.arr_remove(e['resistanceOriginTimeArray'], e['i'])
                    # Pine 2098
                    rt.arr_remove(e['resistanceScoreArray'], e['i'])
                    # Pine 2099
                    rt.arr_remove(e['resistanceESArray'], e['i'])
                    # Pine 2100
                    rt.arr_remove(e['resistanceZoneATRArray'], e['i'])
                # Pine 2102
                if rt.truth(e['isResistanceInstitutional']):
                    # Pine 2103
                    e['oldFailureCount'] = rt.arr_get(e['instResistanceFailureCountArray'], e['instIndex'])
                    # Pine 2104
                    rt.arr_set(e['InstResistanceBreakBarArray'], e['instIndex'], e['bar_index'])
                    # Pine 2105
                    rt.arr_set(e['instResistanceFailureCountArray'], e['instIndex'], rt.binary('+', e['oldFailureCount'], 1))
                    # Pine 2106
                    rt.arr_set(e['resistanceLastTestBarArray'], e['i'], e['bar_index'])
                    # Pine 2107
                    rt.arr_set(e['resistanceLastTestTypeArray'], e['i'], 'FAILED')
                    # Pine 2108
                    rt.arr_set(e['resistanceApproachDirectionArray'], e['i'], 0)
                    # Pine 2109
                    e['instResistanceScore'] = rt.arr_get(e['instResistanceScoreArray'], e['instIndex'])
                    # Pine 2111
                    if rt.truth(rt.binary('<=', e['instResistanceScore'], 5)):
                        # Pine 2113
                        rt.arr_remove(e['instResistanceZoneIDArray'], e['instIndex'])
                        # Pine 2114
                        rt.arr_remove(e['instResistanceScoreArray'], e['instIndex'])
                        # Pine 2115
                        rt.arr_remove(e['instResistanceStrengthArray'], e['instIndex'])
                        # Pine 2116
                        rt.arr_remove(e['instQualifiedResistanceTFListArray'], e['instIndex'])
                        # Pine 2117
                        rt.arr_remove(e['instResistanceFailureCountArray'], e['instIndex'])
                        # Pine 2118
                        rt.arr_remove(e['InstResistanceBreakBarArray'], e['instIndex'])
                        # Pine 2121
                        rt.arr_remove(e['resistanceZoneIDArray'], e['i'])
                        # Pine 2122
                        rt.arr_remove(e['resistanceLowArray'], e['i'])
                        # Pine 2123
                        rt.arr_remove(e['resistanceHighArray'], e['i'])
                        # Pine 2124
                        rt.arr_remove(e['resistanceOriginArray'], e['i'])
                        # Pine 2125
                        rt.arr_remove(e['resistanceBarArray'], e['i'])
                        # Pine 2126
                        rt.arr_remove(e['resistanceTouchArray'], e['i'])
                        # Pine 2127
                        rt.arr_remove(e['prevCandleInsideResistanceZoneArray'], e['i'])
                        # Pine 2128
                        rt.arr_remove(e['resistanceLastTestBarArray'], e['i'])
                        # Pine 2129
                        rt.arr_remove(e['resistanceLastTestTypeArray'], e['i'])
                        # Pine 2130
                        rt.arr_remove(e['resistanceStrengthArray'], e['i'])
                        # Pine 2131
                        rt.arr_remove(e['resistanceStrongRejectArray'], e['i'])
                        # Pine 2132
                        rt.arr_remove(e['resistanceMaxPenetrationArray'], e['i'])
                        # Pine 2133
                        rt.arr_remove(e['resistanceMaxWickRatioArray'], e['i'])
                        # Pine 2134
                        rt.arr_remove(e['resistanceMaxReactionArray'], e['i'])
                        # Pine 2135
                        rt.arr_remove(e['resistanceApproachDirectionArray'], e['i'])
                        # Pine 2136
                        rt.arr_remove(e['resistanceOriginTimeArray'], e['i'])
                        # Pine 2137
                        rt.arr_remove(e['resistanceScoreArray'], e['i'])
                        # Pine 2138
                        rt.arr_remove(e['resistanceESArray'], e['i'])
                        # Pine 2139
                        rt.arr_remove(e['resistanceZoneATRArray'], e['i'])
            # Pine 2141
            elif rt.truth(e['barstate.isconfirmed']):
                # Pine 2142
                e['oldResistanceTouches'] = rt.arr_get(e['resistanceTouchArray'], e['i'])
                # Pine 2143
                e['oldResistanceStrength'] = rt.arr_get(e['resistanceStrengthArray'], e['i'])
                # Pine 2144
                e['resistanceZoneHeight'] = rt.binary('-', e['resistanceZoneHigh'], e['resistanceZoneLow'])
                # Pine 2145
                e['resistancePenetration'] = rt.math_max(0.0, rt.binary('/', rt.binary('-', e['h'], e['resistanceZoneLow']), e['resistanceZoneHeight']))
                # Pine 2146
                e['penetrationInsideResistanceZone'] = (rt.truth(rt.binary('>=', e['h'], e['resistanceZoneLow'])) and rt.truth(rt.binary('<=', e['h'], e['resistanceZoneHigh'])))
                # Pine 2147
                if rt.truth(e['penetrationInsideResistanceZone']):
                    # Pine 2148
                    e['oldMaxPenetration'] = rt.arr_get(e['resistanceMaxPenetrationArray'], e['i'])
                    # Pine 2149
                    rt.arr_set(e['resistanceMaxPenetrationArray'], e['i'], rt.math_max(e['oldMaxPenetration'], e['resistancePenetration']))
                # Pine 2151
                e['wickSize'] = (rt.binary('-', e['h'], e['resistanceZoneHigh']) if rt.truth(rt.binary('>', e['h'], e['resistanceZoneHigh'])) else 0)
                # Pine 2152
                e['candleRange'] = rt.binary('-', e['h'], e['l'])
                # Pine 2153
                e['wickRatio'] = (rt.binary('/', e['wickSize'], e['candleRange']) if rt.truth(rt.binary('>', e['candleRange'], 0)) else 0)
                # Pine 2154
                e['currentResistanceReaction'] = (rt.binary('/', rt.binary('-', e['resistanceZoneHigh'], e['c']), e['atr']) if rt.truth(rt.binary('<', e['c'], e['resistanceZoneHigh'])) else 0)
                # Pine 2155
                e['oldWick'] = rt.arr_get(e['resistanceMaxWickRatioArray'], e['i'])
                # Pine 2156
                e['oldReaction'] = rt.arr_get(e['resistanceMaxReactionArray'], e['i'])
                # Pine 2158
                rt.arr_set(e['resistanceMaxWickRatioArray'], e['i'], rt.math_max(e['oldWick'], e['wickRatio']))
                # Pine 2159
                rt.arr_set(e['resistanceMaxReactionArray'], e['i'], rt.math_max(e['oldReaction'], e['currentResistanceReaction']))
                # Pine 2161
                e['wickAboveResistance'] = (rt.truth(rt.binary('>', e['h'], e['resistanceZoneHigh'])) and rt.truth(rt.binary('<', e['c'], e['resistanceZoneLow'])))
                # Pine 2162
                if rt.truth((rt.truth((rt.truth(e['wasInsideResistanceZone']) and rt.truth(e['wasApproachedFromBelow']))) and rt.truth(rt.binary('<', e['h'], e['resistanceZoneLow'])))):
                    # Pine 2163
                    e['newResistanceTouches'] = rt.binary('+', e['oldResistanceTouches'], 1)
                    # Pine 2164
                    rt.arr_set(e['resistanceTouchArray'], e['i'], e['newResistanceTouches'])
                    # Pine 2165
                    e['strongResistanceRejects'] = rt.arr_get(e['resistanceStrongRejectArray'], e['i'])
                    # Pine 2166
                    e['currentResistanceStrength'] = e['oldResistanceStrength']
                    # Pine 2168
                    if rt.truth(rt.binary('>=', e['currentResistanceReaction'], e['srReactionATR'])):
                        # Pine 2169
                        e['currentResistanceStrength'] = rt.binary('+', e['currentResistanceStrength'], 5)
                        # Pine 2170
                        e['strongResistanceRejects'] = rt.binary('+', e['strongResistanceRejects'], 1)
                        # Pine 2171
                        rt.arr_set(e['resistanceLastTestTypeArray'], e['i'], 'STRONG_REJECTION')
                    # Pine 2173
                    else:
                        # Pine 2174
                        e['currentResistanceStrength'] = rt.binary('+', e['currentResistanceStrength'], 3)
                        # Pine 2175
                        rt.arr_set(e['resistanceLastTestTypeArray'], e['i'], 'WEAK_REACTION')
                    # Pine 2177
                    rt.arr_set(e['resistanceStrengthArray'], e['i'], e['currentResistanceStrength'])
                    # Pine 2178
                    rt.arr_set(e['resistanceStrongRejectArray'], e['i'], e['strongResistanceRejects'])
                    # Pine 2179
                    rt.arr_set(e['resistanceLastTestBarArray'], e['i'], e['bar_index'])
                # Pine 2182
                e['resistanceTouches'] = rt.arr_get(e['resistanceTouchArray'], e['i'])
                # Pine 2183
                e['strongResistanceRejects'] = rt.arr_get(e['resistanceStrongRejectArray'], e['i'])
                # Pine 2184
                e['weakResistanceTouches'] = rt.math_max(0, rt.binary('-', e['resistanceTouches'], e['strongResistanceRejects']))
                # Pine 2185
                e['resistanceScore'] = rt.binary('+', rt.binary('*', e['strongResistanceRejects'], 5.0), rt.binary('*', e['weakResistanceTouches'], 3.0))
                # Pine 2186
                rt.arr_set(e['resistanceScoreArray'], e['i'], e['resistanceScore'])
                # Pine 2188
                e['resistanceAgeFactor'] = rt.binary('/', 1, rt.binary('+', 1, rt.binary('/', e['resistanceZoneAge'], 1000)))
                # Pine 2189
                e['resistanceRecentTestFactor'] = rt.binary('/', 1, rt.binary('+', 1, rt.binary('/', e['barsSinceResistanceTest'], 500)))
                # Pine 2190
                e['lastResistanceTestType'] = rt.arr_get(e['resistanceLastTestTypeArray'], e['i'])
                # Pine 2191
                e['resistanceTestTypeFactor'] = 0.0
                # Pine 2193
                if rt.truth(rt.binary('==', e['lastResistanceTestType'], 'STRONG_REJECTION')):
                    # Pine 2194
                    e['resistanceTestTypeFactor'] = 1.0
                # Pine 2195
                elif rt.truth(rt.binary('==', e['lastResistanceTestType'], 'WEAK_REACTION')):
                    # Pine 2196
                    e['resistanceTestTypeFactor'] = 0.5
                # Pine 2197
                elif rt.truth(rt.binary('==', e['lastResistanceTestType'], 'FAILED')):
                    # Pine 2198
                    e['resistanceTestTypeFactor'] = rt.neg(1.0)
                # Pine 2199
                else:
                    # Pine 2200
                    e['resistanceTestTypeFactor'] = 0.0
                # Pine 2202
                e['effectiveResistanceStrength'] = 0.0
                # Pine 2203
                e['currentResistanceZoneID'] = rt.arr_get(e['resistanceZoneIDArray'], e['i'])
                # Pine 2204
                e['instResistanceIndex'] = rt.arr_indexof(e['instResistanceZoneIDArray'], e['currentResistanceZoneID'])
                # Pine 2205
                if rt.truth(rt.binary('!=', e['instResistanceIndex'], rt.neg(1))):
                    # Pine 2206
                    e['effectiveResistanceStrength'] = rt.binary('*', rt.binary('*', rt.binary('*', rt.arr_get(e['instResistanceStrengthArray'], e['instResistanceIndex']), e['resistanceAgeFactor']), e['resistanceRecentTestFactor']), e['resistanceTestTypeFactor'])
                # Pine 2208
                else:
                    # Pine 2209
                    e['effectiveResistanceStrength'] = rt.binary('*', rt.binary('*', rt.binary('*', rt.arr_get(e['resistanceStrengthArray'], e['i']), e['resistanceAgeFactor']), e['resistanceRecentTestFactor']), e['resistanceTestTypeFactor'])
                # Pine 2210
                rt.arr_set(e['resistanceESArray'], e['i'], e['effectiveResistanceStrength'])
                # Pine 2212
                e['resistanceDistanceATR'] = (rt.binary('/', rt.binary('-', e['resistanceZoneLow'], e['c']), e['atr']) if rt.truth(rt.binary('>', e['atr'], 0)) else rt.NA)
                # Pine 2213
                if rt.truth((rt.truth(e['wasApproachedFromBelow']) and rt.truth(rt.binary('>=', e['resistanceDistanceATR'], 0)))):
                    # Pine 2214
                    if rt.truth((rt.truth(rt.is_na(e['nearestResistanceDistance'])) or rt.truth(rt.binary('<', e['resistanceDistanceATR'], e['nearestResistanceDistance'])))):
                        # Pine 2215
                        e['nearestResistanceDistance'] = e['resistanceDistanceATR']
                        # Pine 2216
                        e['nearestResistancePrice'] = e['resistanceZoneLow']
                        # Pine 2217
                        e['nearestResistanceStrength'] = rt.arr_get(e['resistanceStrengthArray'], e['i'])
                        # Pine 2218
                        e['nearestResistanceScore'] = rt.arr_get(e['resistanceScoreArray'], e['i'])
                        # Pine 2219
                        e['nearestResistanceZoneID'] = rt.arr_get(e['resistanceZoneIDArray'], e['i'])
                        # Pine 2220
                        e['nearestResistanceState'] = rt.arr_get(e['resistanceLastTestTypeArray'], e['i'])
                # Pine 2222
                rt.arr_set(e['prevCandleInsideResistanceZoneArray'], e['i'], e['insideResistanceZone'])
                # Pine 2224
                e['resistanceDistancePrice'] = rt.NA
                # Pine 2226
                if rt.truth(rt.binary('<=', e['c'], e['resistanceZoneHigh'])):
                    # Pine 2227
                    e['resistanceDistancePrice'] = rt.binary('-', e['resistanceZoneHigh'], e['c'])
                # Pine 2229
                if rt.truth((not rt.truth(rt.is_na(e['resistanceDistancePrice'])))):
                    # Pine 2230
                    if rt.truth((rt.truth(rt.is_na(e['nearestResistanceZonePriceDistance'])) or rt.truth(rt.binary('<', e['resistanceDistancePrice'], e['nearestResistanceZonePriceDistance'])))):
                        # Pine 2231
                        e['nearestResistanceZonePrice'] = e['resistanceZoneHigh']
                        # Pine 2232
                        e['nearestResistanceZonePriceID'] = rt.arr_get(e['resistanceZoneIDArray'], e['i'])
                        # Pine 2233
                        e['nearestResistanceZonePriceDistance'] = e['resistanceDistancePrice']
                        # Pine 2234
                        e['nearestResistanceZonePriceATR'] = rt.arr_get(e['resistanceZoneATRArray'], e['i'])
                        # Pine 2235
                        e['nearestResistanceES'] = rt.arr_get(e['resistanceESArray'], e['i'])
                        # Pine 2237
                        e['lastTestBar'] = rt.arr_get(e['resistanceLastTestBarArray'], e['i'])
                        # Pine 2238
                        e['nearestResistanceLastTestAge'] = (rt.binary('-', e['bar_index'], e['lastTestBar']) if rt.truth((not rt.truth(rt.is_na(e['lastTestBar'])))) else rt.NA)
                        # Pine 2239
                        e['nearestResistanceLastTestType'] = rt.arr_get(e['resistanceLastTestTypeArray'], e['i'])
                        # Pine 2240
                        e['nearestResistanceStrongTouches'] = rt.arr_get(e['resistanceStrongRejectArray'], e['i'])
                        # Pine 2242
                        e['nearestResistanceTotalTouches'] = rt.arr_get(e['resistanceTouchArray'], e['i'])
                        # Pine 2243
                        e['nearestResistanceWeakTouches'] = rt.math_max(0, rt.binary('-', e['nearestResistanceTotalTouches'], e['nearestResistanceStrongTouches']))
                        # Pine 2245
                        e['instNearestResistanceIndex'] = rt.arr_indexof(e['instResistanceZoneIDArray'], e['nearestResistanceZonePriceID'])
                        # Pine 2246
                        e['nearestInstResistanceFailureCount'] = (rt.arr_get(e['instResistanceFailureCountArray'], e['instNearestResistanceIndex']) if rt.truth(rt.binary('!=', e['instNearestResistanceIndex'], rt.neg(1))) else rt.NA)
    # Pine 2263
    if rt.truth((rt.truth((rt.truth(e['barstate.isconfirmed']) and rt.truth((not rt.truth(rt.is_na(e['srPivotHigh'])))))) and rt.truth(rt.binary('>', rt.arr_size(e['resistanceLowArray']), 1)))):
        # Pine 2264
        e['latestResistanceIndex'] = rt.binary('-', rt.arr_size(e['resistanceLowArray']), 1)
        # Pine 2265
        e['latestResistanceZoneID'] = rt.arr_get(e['resistanceZoneIDArray'], e['latestResistanceIndex'])
        # Pine 2266
        e['newResistanceLow'] = rt.arr_get(e['resistanceLowArray'], e['latestResistanceIndex'])
        # Pine 2267
        e['newResistanceHigh'] = rt.arr_get(e['resistanceHighArray'], e['latestResistanceIndex'])
        # Pine 2270
        e['mergeResistanceIndex'] = rt.neg(1)
        # Pine 2271
        e['nearestResistanceMergeDistance'] = rt.NA
        # Pine 2272
        for e['i'] in rt.inclusive(0, rt.binary('-', e['latestResistanceIndex'], 1)):
            # Pine 2273
            e['existingResistanceZoneID'] = rt.arr_get(e['resistanceZoneIDArray'], e['i'])
            # Pine 2274
            e['existingZoneIsInstitutional'] = rt.binary('!=', rt.arr_indexof(e['instResistanceZoneIDArray'], e['existingResistanceZoneID']), rt.neg(1))
            # Pine 2275
            if rt.truth(e['existingZoneIsInstitutional']):
                # Pine 2276
                continue
            # Pine 2278
            e['existingResistanceLow'] = rt.arr_get(e['resistanceLowArray'], e['i'])
            # Pine 2279
            e['existingResistanceHigh'] = rt.arr_get(e['resistanceHighArray'], e['i'])
            # Pine 2280
            e['mergeResistanceDistance'] = 0.0
            # Pine 2281
            if rt.truth(rt.binary('>', e['newResistanceLow'], e['existingResistanceHigh'])):
                # Pine 2282
                e['mergeResistanceDistance'] = rt.binary('-', e['newResistanceLow'], e['existingResistanceHigh'])
            # Pine 2284
            elif rt.truth(rt.binary('<', e['newResistanceHigh'], e['existingResistanceLow'])):
                # Pine 2285
                e['mergeResistanceDistance'] = rt.binary('-', e['existingResistanceLow'], e['newResistanceHigh'])
            # Pine 2286
            else:
                # Pine 2287
                e['mergeResistanceDistance'] = 0.0
            # Pine 2289
            e['resistanceOverlap'] = rt.binary('<=', e['mergeResistanceDistance'], e['srMergeDistance'])
            # Pine 2290
            if rt.truth(e['resistanceOverlap']):
                # Pine 2291
                if rt.truth((rt.truth(rt.is_na(e['nearestResistanceMergeDistance'])) or rt.truth(rt.binary('<', e['mergeResistanceDistance'], e['nearestResistanceMergeDistance'])))):
                    # Pine 2292
                    e['nearestResistanceMergeDistance'] = e['mergeResistanceDistance']
                    # Pine 2293
                    e['mergeResistanceIndex'] = e['i']
        # Pine 2296
        if rt.truth(rt.binary('!=', e['mergeResistanceIndex'], rt.neg(1))):
            # Pine 2297
            e['existingResistanceLow'] = rt.arr_get(e['resistanceLowArray'], e['mergeResistanceIndex'])
            # Pine 2298
            e['existingResistanceHigh'] = rt.arr_get(e['resistanceHighArray'], e['mergeResistanceIndex'])
            # Pine 2299
            e['survivingZoneHeight'] = rt.binary('-', e['existingResistanceHigh'], e['existingResistanceLow'])
            # Pine 2300
            e['survivingResistanceZoneID'] = rt.arr_get(e['resistanceZoneIDArray'], e['mergeResistanceIndex'])
            # Pine 2301
            e['combinedLow'] = rt.math_min(e['existingResistanceLow'], e['newResistanceLow'])
            # Pine 2302
            e['combinedHigh'] = rt.math_max(e['existingResistanceHigh'], e['newResistanceHigh'])
            # Pine 2303
            e['mergedCenter'] = rt.binary('/', rt.binary('+', e['combinedLow'], e['combinedHigh']), 2.0)
            # Pine 2304
            e['mergedLow'] = rt.binary('-', e['mergedCenter'], rt.binary('/', e['survivingZoneHeight'], 2.0))
            # Pine 2305
            e['mergedHigh'] = rt.binary('+', e['mergedCenter'], rt.binary('/', e['survivingZoneHeight'], 2.0))
            # Pine 2307
            rt.arr_set(e['resistanceLowArray'], e['mergeResistanceIndex'], e['mergedLow'])
            # Pine 2308
            rt.arr_set(e['resistanceHighArray'], e['mergeResistanceIndex'], e['mergedHigh'])
            # Pine 2311
            e['oldBar'] = rt.arr_get(e['resistanceBarArray'], e['mergeResistanceIndex'])
            # Pine 2312
            e['newBar'] = rt.arr_get(e['resistanceBarArray'], e['latestResistanceIndex'])
            # Pine 2314
            if rt.truth(rt.binary('<', e['newBar'], e['oldBar'])):
                # Pine 2315
                rt.arr_set(e['resistanceBarArray'], e['mergeResistanceIndex'], e['newBar'])
                # Pine 2316
                rt.arr_set(e['resistanceOriginArray'], e['mergeResistanceIndex'], rt.arr_get(e['resistanceOriginArray'], e['latestResistanceIndex']))
                # Pine 2317
                rt.arr_set(e['resistanceOriginTimeArray'], e['mergeResistanceIndex'], rt.arr_get(e['resistanceOriginTimeArray'], e['latestResistanceIndex']))
                # Pine 2318
                rt.arr_set(e['resistanceZoneATRArray'], e['mergeResistanceIndex'], rt.arr_get(e['resistanceZoneATRArray'], e['latestResistanceIndex']))
            # Pine 2321
            e['oldResistanceTouches'] = rt.arr_get(e['resistanceTouchArray'], e['mergeResistanceIndex'])
            # Pine 2322
            e['newResistanceTouches'] = rt.arr_get(e['resistanceTouchArray'], e['latestResistanceIndex'])
            # Pine 2323
            rt.arr_set(e['resistanceTouchArray'], e['mergeResistanceIndex'], rt.binary('+', e['oldResistanceTouches'], e['newResistanceTouches']))
            # Pine 2326
            e['oldStrength'] = rt.arr_get(e['resistanceStrengthArray'], e['mergeResistanceIndex'])
            # Pine 2327
            e['newStrength'] = rt.arr_get(e['resistanceStrengthArray'], e['latestResistanceIndex'])
            # Pine 2328
            rt.arr_set(e['resistanceStrengthArray'], e['mergeResistanceIndex'], rt.math_max(e['oldStrength'], e['newStrength']))
            # Pine 2331
            e['oldES'] = rt.arr_get(e['resistanceESArray'], e['mergeResistanceIndex'])
            # Pine 2332
            e['newES'] = rt.arr_get(e['resistanceESArray'], e['latestResistanceIndex'])
            # Pine 2334
            rt.arr_set(e['resistanceESArray'], e['mergeResistanceIndex'], rt.math_max(e['oldES'], e['newES']))
            # Pine 2337
            e['oldReject'] = rt.arr_get(e['resistanceStrongRejectArray'], e['mergeResistanceIndex'])
            # Pine 2338
            e['newReject'] = rt.arr_get(e['resistanceStrongRejectArray'], e['latestResistanceIndex'])
            # Pine 2339
            rt.arr_set(e['resistanceStrongRejectArray'], e['mergeResistanceIndex'], rt.binary('+', e['oldReject'], e['newReject']))
            # Pine 2342
            e['oldLast'] = rt.arr_get(e['resistanceLastTestBarArray'], e['mergeResistanceIndex'])
            # Pine 2343
            e['newLast'] = rt.arr_get(e['resistanceLastTestBarArray'], e['latestResistanceIndex'])
            # Pine 2344
            if rt.truth((rt.truth(rt.is_na(e['oldLast'])) or rt.truth((rt.truth((not rt.truth(rt.is_na(e['newLast'])))) and rt.truth(rt.binary('>', e['newLast'], e['oldLast'])))))):
                # Pine 2345
                rt.arr_set(e['resistanceLastTestBarArray'], e['mergeResistanceIndex'], e['newLast'])
                # Pine 2346
                rt.arr_set(e['resistanceLastTestTypeArray'], e['mergeResistanceIndex'], rt.arr_get(e['resistanceLastTestTypeArray'], e['latestResistanceIndex']))
            # Pine 2349
            e['oldMaxPenetration'] = rt.arr_get(e['resistanceMaxPenetrationArray'], e['mergeResistanceIndex'])
            # Pine 2350
            e['newMaxPenetration'] = rt.arr_get(e['resistanceMaxPenetrationArray'], e['latestResistanceIndex'])
            # Pine 2351
            rt.arr_set(e['resistanceMaxPenetrationArray'], e['mergeResistanceIndex'], rt.math_max(e['oldMaxPenetration'], e['newMaxPenetration']))
            # Pine 2354
            e['oldWick'] = rt.arr_get(e['resistanceMaxWickRatioArray'], e['mergeResistanceIndex'])
            # Pine 2355
            e['newWick'] = rt.arr_get(e['resistanceMaxWickRatioArray'], e['latestResistanceIndex'])
            # Pine 2356
            rt.arr_set(e['resistanceMaxWickRatioArray'], e['mergeResistanceIndex'], rt.math_max(e['oldWick'], e['newWick']))
            # Pine 2359
            e['mergedResistanceTouches'] = rt.arr_get(e['resistanceTouchArray'], e['mergeResistanceIndex'])
            # Pine 2360
            e['mergedResistanceRejects'] = rt.arr_get(e['resistanceStrongRejectArray'], e['mergeResistanceIndex'])
            # Pine 2361
            e['mergedResistanceWeakTouches'] = rt.math_max(0, rt.binary('-', e['mergedResistanceTouches'], e['mergedResistanceRejects']))
            # Pine 2362
            e['mergedResistanceScore'] = rt.binary('+', rt.binary('*', e['mergedResistanceRejects'], 5.0), rt.binary('*', e['mergedResistanceWeakTouches'], 3.0))
            # Pine 2363
            rt.arr_set(e['resistanceScoreArray'], e['mergeResistanceIndex'], e['mergedResistanceScore'])
            # Pine 2366
            e['oldReaction'] = rt.arr_get(e['resistanceMaxReactionArray'], e['mergeResistanceIndex'])
            # Pine 2367
            e['newReaction'] = rt.arr_get(e['resistanceMaxReactionArray'], e['latestResistanceIndex'])
            # Pine 2368
            rt.arr_set(e['resistanceMaxReactionArray'], e['mergeResistanceIndex'], rt.math_max(e['oldReaction'], e['newReaction']))
            # Pine 2371
            e['oldDirection'] = rt.arr_get(e['resistanceApproachDirectionArray'], e['mergeResistanceIndex'])
            # Pine 2372
            e['newDirection'] = rt.arr_get(e['resistanceApproachDirectionArray'], e['latestResistanceIndex'])
            # Pine 2373
            e['mergedDirection'] = e['oldDirection']
            # Pine 2375
            if rt.truth((rt.truth(rt.binary('==', e['mergedDirection'], 0)) and rt.truth(rt.binary('!=', e['newDirection'], 0)))):
                # Pine 2376
                e['mergedDirection'] = e['newDirection']
            # Pine 2377
            rt.arr_set(e['resistanceApproachDirectionArray'], e['mergeResistanceIndex'], e['mergedDirection'])
            # Pine 2387
            rt.arr_remove(e['resistanceZoneIDArray'], e['latestResistanceIndex'])
            # Pine 2388
            rt.arr_remove(e['resistanceLowArray'], e['latestResistanceIndex'])
            # Pine 2389
            rt.arr_remove(e['resistanceHighArray'], e['latestResistanceIndex'])
            # Pine 2390
            rt.arr_remove(e['resistanceOriginArray'], e['latestResistanceIndex'])
            # Pine 2391
            rt.arr_remove(e['resistanceBarArray'], e['latestResistanceIndex'])
            # Pine 2392
            rt.arr_remove(e['resistanceTouchArray'], e['latestResistanceIndex'])
            # Pine 2393
            rt.arr_remove(e['prevCandleInsideResistanceZoneArray'], e['latestResistanceIndex'])
            # Pine 2394
            rt.arr_remove(e['resistanceLastTestBarArray'], e['latestResistanceIndex'])
            # Pine 2395
            rt.arr_remove(e['resistanceLastTestTypeArray'], e['latestResistanceIndex'])
            # Pine 2396
            rt.arr_remove(e['resistanceStrengthArray'], e['latestResistanceIndex'])
            # Pine 2397
            rt.arr_remove(e['resistanceStrongRejectArray'], e['latestResistanceIndex'])
            # Pine 2398
            rt.arr_remove(e['resistanceMaxPenetrationArray'], e['latestResistanceIndex'])
            # Pine 2399
            rt.arr_remove(e['resistanceMaxWickRatioArray'], e['latestResistanceIndex'])
            # Pine 2400
            rt.arr_remove(e['resistanceMaxReactionArray'], e['latestResistanceIndex'])
            # Pine 2401
            rt.arr_remove(e['resistanceApproachDirectionArray'], e['latestResistanceIndex'])
            # Pine 2402
            rt.arr_remove(e['resistanceOriginTimeArray'], e['latestResistanceIndex'])
            # Pine 2403
            rt.arr_remove(e['resistanceScoreArray'], e['latestResistanceIndex'])
            # Pine 2404
            rt.arr_remove(e['resistanceESArray'], e['latestResistanceIndex'])
            # Pine 2405
            rt.arr_remove(e['resistanceZoneATRArray'], e['latestResistanceIndex'])

def update_institutional_resistance(e):
    # Pine 2422
    e['isInstResistanceQualificationTF'] = rt.binary('==', e['timeframe.period'], '240')
    # Pine 2423
    e['isInstResistanceAvailableOnAllTF'] = True
    # Pine 2424
    if rt.truth((rt.truth((rt.truth(e['barstate.isconfirmed']) and rt.truth(e['isInstResistanceQualificationTF']))) and rt.truth(rt.binary('>', rt.arr_size(e['resistanceZoneIDArray']), 0)))):
        # Pine 2425
        for e['i'] in rt.inclusive(0, rt.binary('-', rt.arr_size(e['resistanceZoneIDArray']), 1)):
            # Pine 2426
            e['instResistanceZoneID'] = rt.arr_get(e['resistanceZoneIDArray'], e['i'])
            # Pine 2427
            e['existinginstResistanceZone'] = rt.arr_indexof(e['instResistanceZoneIDArray'], e['instResistanceZoneID'])
            # Pine 2429
            if rt.truth(rt.binary('!=', e['existinginstResistanceZone'], rt.neg(1))):
                # Pine 2430
                continue
            # Pine 2432
            e['instResistanceTouches'] = rt.arr_get(e['resistanceTouchArray'], e['i'])
            # Pine 2433
            e['instResistanceStrongRejects'] = rt.arr_get(e['resistanceStrongRejectArray'], e['i'])
            # Pine 2434
            e['instResistanceQualificationScore'] = 0.0
            # Pine 2436
            e['instResistanceQualificationScore'] = rt.binary('+', e['instResistanceQualificationScore'], rt.binary('*', e['instResistanceStrongRejects'], 5))
            # Pine 2438
            e['instResistanceWeakTouches'] = rt.binary('-', e['instResistanceTouches'], e['instResistanceStrongRejects'])
            # Pine 2440
            if rt.truth(rt.binary('>', e['instResistanceWeakTouches'], 0)):
                # Pine 2441
                e['instResistanceQualificationScore'] = rt.binary('+', e['instResistanceQualificationScore'], rt.binary('*', e['instResistanceWeakTouches'], 3))
            # Pine 2443
            e['instResistanceQualificationScore'] = rt.math_max(0, rt.math_min(50, e['instResistanceQualificationScore']))
            # Pine 2445
            e['instQualifiedResistance'] = rt.binary('>=', e['instResistanceQualificationScore'], 50)
            # Pine 2447
            if rt.truth((not rt.truth(e['instQualifiedResistance']))):
                # Pine 2448
                continue
            # Pine 2450
            rt.arr_push(e['instResistanceZoneIDArray'], e['instResistanceZoneID'])
            # Pine 2451
            rt.arr_push(e['instResistanceScoreArray'], e['instResistanceQualificationScore'])
            # Pine 2452
            rt.arr_push(e['instResistanceStrengthArray'], 0)
            # Pine 2453
            rt.arr_push(e['instQualifiedResistanceTFListArray'], ',240:0,')
            # Pine 2454
            rt.arr_push(e['instResistanceFailureCountArray'], 0)
            # Pine 2455
            rt.arr_push(e['InstResistanceBreakBarArray'], rt.NA)
    # Pine 2479
    if rt.truth((rt.truth(e['barstate.isconfirmed']) and rt.truth(rt.binary('>', rt.arr_size(e['instResistanceZoneIDArray']), 0)))):
        # Pine 2480
        for e['i'] in rt.inclusive(0, rt.binary('-', rt.arr_size(e['instResistanceZoneIDArray']), 1)):
            # Pine 2481
            e['instResistanceZoneID'] = rt.arr_get(e['instResistanceZoneIDArray'], e['i'])
            # Pine 2482
            e['dynamicResistanceIndex'] = rt.arr_indexof(e['resistanceZoneIDArray'], e['instResistanceZoneID'])
            # Pine 2484
            if rt.truth(rt.binary('==', e['dynamicResistanceIndex'], rt.neg(1))):
                # Pine 2485
                continue
            # Pine 2487
            e['instResistancefailureCount'] = rt.arr_get(e['instResistanceFailureCountArray'], e['i'])
            # Pine 2490
            e['instResistanceTouches'] = rt.arr_get(e['resistanceTouchArray'], e['dynamicResistanceIndex'])
            # Pine 2491
            e['instResistanceStrongRejects'] = rt.arr_get(e['resistanceStrongRejectArray'], e['dynamicResistanceIndex'])
            # Pine 2492
            e['instResistanceReactionScore'] = 0.0
            # Pine 2494
            e['instResistanceReactionScore'] = rt.binary('+', e['instResistanceReactionScore'], rt.binary('*', e['instResistanceStrongRejects'], 5))
            # Pine 2496
            e['instResistanceWeakTouches'] = rt.binary('-', e['instResistanceTouches'], e['instResistanceStrongRejects'])
            # Pine 2497
            if rt.truth(rt.binary('>', e['instResistanceWeakTouches'], 0)):
                # Pine 2498
                e['instResistanceReactionScore'] = rt.binary('+', e['instResistanceReactionScore'], rt.binary('*', e['instResistanceWeakTouches'], 3))
            # Pine 2500
            e['instResistancefailureScore'] = rt.binary('*', e['instResistancefailureCount'], 5)
            # Pine 2501
            e['instResistanceFinalScore'] = rt.binary('-', e['instResistanceReactionScore'], e['instResistancefailureScore'])
            # Pine 2502
            rt.arr_set(e['instResistanceScoreArray'], e['i'], e['instResistanceFinalScore'])
            # Pine 2509
            e['dynamicResistanceLow'] = rt.arr_get(e['resistanceLowArray'], e['dynamicResistanceIndex'])
            # Pine 2510
            e['dynamicResistanceHigh'] = rt.arr_get(e['resistanceHighArray'], e['dynamicResistanceIndex'])
            # Pine 2511
            e['validInstResistance'] = rt.binary('>=', e['dynamicResistanceLow'], e['c'])
            # Pine 2512
            if rt.truth((not rt.truth(e['validInstResistance']))):
                # Pine 2513
                continue
            # Pine 2515
            e['instResistanceDistanceATR'] = rt.binary('/', rt.binary('-', e['dynamicResistanceLow'], e['c']), e['atr'])
            # Pine 2516
            e['instResistanceES'] = rt.arr_get(e['resistanceESArray'], e['dynamicResistanceIndex'])
            # Pine 2517
            if rt.truth((rt.truth(rt.is_na(e['nearestInstResistanceDistanceATR'])) or rt.truth(rt.binary('<', e['instResistanceDistanceATR'], e['nearestInstResistanceDistanceATR'])))):
                # Pine 2518
                e['nearestInstResistanceDistanceATR'] = e['instResistanceDistanceATR']
                # Pine 2519
                e['nearestInstResistance'] = e['dynamicResistanceLow']
                # Pine 2520
                e['nearestInstResistanceScore'] = rt.arr_get(e['instResistanceScoreArray'], e['i'])
                # Pine 2521
                e['nearestInstResistanceStrength'] = rt.arr_get(e['instResistanceStrengthArray'], e['i'])
                # Pine 2522
                e['nearestInstResistanceZoneID'] = e['instResistanceZoneID']
                # Pine 2523
                e['nearestInstResistanceES'] = e['instResistanceES']
                # Pine 2524
                e['lastTestBar'] = rt.arr_get(e['resistanceLastTestBarArray'], e['dynamicResistanceIndex'])
                # Pine 2525
                e['nearestInstResistanceLastTestAge'] = (rt.binary('-', e['bar_index'], e['lastTestBar']) if rt.truth((not rt.truth(rt.is_na(e['lastTestBar'])))) else rt.NA)
                # Pine 2526
                e['nearestInstResistanceLastTestType'] = rt.arr_get(e['resistanceLastTestTypeArray'], e['dynamicResistanceIndex'])
            # Pine 2547
            e['instResistanceZoneLow'] = rt.arr_get(e['resistanceLowArray'], e['dynamicResistanceIndex'])
            # Pine 2548
            e['instResistanceZoneHigh'] = rt.arr_get(e['resistanceHighArray'], e['dynamicResistanceIndex'])
            # Pine 2549
            e['instResistanceZoneBar'] = rt.arr_get(e['resistanceBarArray'], e['dynamicResistanceIndex'])
            # Pine 2550
            e['instQualifiedResistanceTFList'] = rt.arr_get(e['instQualifiedResistanceTFListArray'], e['i'])
            # Pine 2551
            e['currentInstResistanceTFTag'] = e['timeframe.period']
            # Pine 2552
            e['isInstResistanceObservationTF'] = (rt.truth((rt.truth((rt.truth(rt.binary('==', e['currentInstResistanceTFTag'], '240')) or rt.truth(rt.binary('==', e['currentInstResistanceTFTag'], '1D')))) or rt.truth(rt.binary('==', e['currentInstResistanceTFTag'], '1W')))) or rt.truth(rt.binary('==', e['currentInstResistanceTFTag'], '1M')))
            # Pine 2558
            if rt.truth((not rt.truth(e['isInstResistanceObservationTF']))):
                # Pine 2559
                continue
            # Pine 2561
            e['currentResistanceTFToken'] = rt.binary('+', rt.binary('+', ',', e['currentInstResistanceTFTag']), ':')
            # Pine 2563
            e['instResistanceZoneInCurrentTF'] = (rt.truth((rt.truth(rt.binary('>', e['time'], rt.arr_get(e['resistanceOriginTimeArray'], e['dynamicResistanceIndex']))) and rt.truth(rt.binary('<=', e['l'], e['instResistanceZoneHigh'])))) and rt.truth(rt.binary('>=', e['h'], e['instResistanceZoneLow'])))
            # Pine 2568
            e['currentResistanceTFAlreadyStored'] = rt.str_contains(e['instQualifiedResistanceTFList'], e['currentResistanceTFToken'])
            # Pine 2570
            if rt.truth((rt.truth((rt.truth(e['barstate.isconfirmed']) and rt.truth(e['instResistanceZoneInCurrentTF']))) and rt.truth((not rt.truth(e['currentResistanceTFAlreadyStored']))))):
                # Pine 2571
                e['instQualifiedResistanceTFList'] = rt.binary('+', e['instQualifiedResistanceTFList'], rt.binary('+', e['currentInstResistanceTFTag'], ':0,'))
                # Pine 2572
                rt.arr_set(e['instQualifiedResistanceTFListArray'], e['i'], e['instQualifiedResistanceTFList'])
            # Pine 2574
            e['interactionWeight'] = 0.0
            # Pine 2575
            e['rejectionWeight'] = 0.0
            # Pine 2576
            e['failureWeight'] = 0.0
            # Pine 2578
            if rt.truth(rt.binary('==', e['currentInstResistanceTFTag'], '240')):
                # Pine 2579
                e['interactionWeight'] = 1.0
                # Pine 2580
                e['rejectionWeight'] = 2.0
                # Pine 2581
                e['failureWeight'] = rt.neg(2.0)
            # Pine 2583
            elif rt.truth(rt.binary('==', e['currentInstResistanceTFTag'], '1D')):
                # Pine 2584
                e['interactionWeight'] = 6.0
                # Pine 2585
                e['rejectionWeight'] = 12.0
                # Pine 2586
                e['failureWeight'] = rt.neg(12.0)
            # Pine 2588
            elif rt.truth(rt.binary('==', e['currentInstResistanceTFTag'], '1W')):
                # Pine 2589
                e['interactionWeight'] = 42.0
                # Pine 2590
                e['rejectionWeight'] = 84.0
                # Pine 2591
                e['failureWeight'] = rt.neg(84.0)
            # Pine 2593
            elif rt.truth(rt.binary('==', e['currentInstResistanceTFTag'], '1M')):
                # Pine 2594
                e['interactionWeight'] = 180.0
                # Pine 2595
                e['rejectionWeight'] = 360.0
                # Pine 2596
                e['failureWeight'] = rt.neg(360.0)
            # Pine 2598
            e['currentTokenPosition'] = rt.str_pos(e['instQualifiedResistanceTFList'], e['currentResistanceTFToken'])
            # Pine 2599
            e['currentTFStrength'] = 0.0
            # Pine 2601
            if rt.truth(rt.binary('!=', e['currentTokenPosition'], rt.neg(1))):
                # Pine 2602
                e['currentValueStart'] = rt.binary('+', e['currentTokenPosition'], rt.str_length(e['currentResistanceTFToken']))
                # Pine 2603
                e['remainingTFString'] = rt.str_substring(e['instQualifiedResistanceTFList'], e['currentValueStart'])
                # Pine 2604
                e['commaPosition'] = rt.str_pos(e['remainingTFString'], ',')
                # Pine 2606
                if rt.truth(rt.binary('!=', e['commaPosition'], rt.neg(1))):
                    # Pine 2607
                    e['currentTFValueString'] = rt.str_substring(e['remainingTFString'], 0, e['commaPosition'])
                    # Pine 2608
                    e['parsedCurrentTFStrength'] = rt.str_tonumber(e['currentTFValueString'])
                    # Pine 2610
                    if rt.truth((not rt.truth(rt.is_na(e['parsedCurrentTFStrength'])))):
                        # Pine 2611
                        e['currentTFStrength'] = e['parsedCurrentTFStrength']
            # Pine 2612
            e['dynamicLastTestBar'] = rt.arr_get(e['resistanceLastTestBarArray'], e['dynamicResistanceIndex'])
            # Pine 2613
            e['dynamicLastTestType'] = rt.arr_get(e['resistanceLastTestTypeArray'], e['dynamicResistanceIndex'])
            # Pine 2614
            e['dynamicBreakBar'] = rt.arr_get(e['InstResistanceBreakBarArray'], e['i'])
            # Pine 2615
            e['eventDelta'] = 0.0
            # Pine 2617
            if rt.truth((rt.truth((not rt.truth(rt.is_na(e['dynamicBreakBar'])))) and rt.truth(rt.binary('==', e['dynamicBreakBar'], e['bar_index'])))):
                # Pine 2618
                e['eventDelta'] = e['failureWeight']
            # Pine 2620
            elif rt.truth((rt.truth((not rt.truth(rt.is_na(e['dynamicLastTestBar'])))) and rt.truth(rt.binary('==', e['dynamicLastTestBar'], e['bar_index'])))):
                # Pine 2622
                if rt.truth(rt.binary('==', e['dynamicLastTestType'], 'STRONG_REJECTION')):
                    # Pine 2623
                    e['eventDelta'] = e['rejectionWeight']
                # Pine 2625
                elif rt.truth(rt.binary('==', e['dynamicLastTestType'], 'WEAK_REACTION')):
                    # Pine 2626
                    e['eventDelta'] = e['interactionWeight']
            # Pine 2628
            if rt.truth(rt.binary('!=', e['eventDelta'], 0)):
                # Pine 2629
                e['newTFStrength'] = rt.binary('+', e['currentTFStrength'], e['eventDelta'])
                # Pine 2632
                if rt.truth(rt.binary('==', e['currentTokenPosition'], rt.neg(1))):
                    # Pine 2633
                    e['instQualifiedResistanceTFList'] = rt.binary('+', e['instQualifiedResistanceTFList'], rt.binary('+', rt.binary('+', rt.binary('+', e['currentInstResistanceTFTag'], ':'), rt.str_tostring(e['newTFStrength'])), ','))
                # Pine 2635
                else:
                    # Pine 2636
                    e['valueStart'] = rt.binary('+', e['currentTokenPosition'], rt.str_length(e['currentResistanceTFToken']))
                    # Pine 2637
                    e['remainingTFString'] = rt.str_substring(e['instQualifiedResistanceTFList'], e['valueStart'])
                    # Pine 2638
                    e['commaPosition'] = rt.str_pos(e['remainingTFString'], ',')
                    # Pine 2640
                    if rt.truth(rt.binary('!=', e['commaPosition'], rt.neg(1))):
                        # Pine 2641
                        e['tokenEnd'] = rt.binary('+', e['valueStart'], e['commaPosition'])
                        # Pine 2643
                        e['instQualifiedResistanceTFList'] = rt.binary('+', rt.binary('+', rt.str_substring(e['instQualifiedResistanceTFList'], 0, e['valueStart']), rt.str_tostring(e['newTFStrength'])), rt.str_substring(e['instQualifiedResistanceTFList'], e['tokenEnd']))
                # Pine 2648
                e['currentTotalStrength'] = rt.arr_get(e['instResistanceStrengthArray'], e['i'])
                # Pine 2650
                rt.arr_set(e['instResistanceStrengthArray'], e['i'], rt.binary('+', e['currentTotalStrength'], rt.to_int(e['eventDelta'])))
                # Pine 2651
                rt.arr_set(e['instQualifiedResistanceTFListArray'], e['i'], e['instQualifiedResistanceTFList'])
        # Pine 2653
        e['nearInstResistance'] = (rt.truth(rt.binary('>', e['nearestInstResistanceES'], 0)) and rt.truth(rt.binary('<=', e['nearestInstResistanceDistanceATR'], e['srZoneDistanceATR'])))
    # Pine 2657
    e['dynamicResistanceScoreSum'] = 0.0
    # Pine 2658
    e['dynamicResistanceESSum'] = 0.0
    # Pine 2659
    e['dynamicResistanceLastTestAgeSum'] = 0.0
    # Pine 2660
    e['dynamicResistanceCount'] = 0
    # Pine 2661
    e['dynamicResistanceLastTestAgeCount'] = 0
    # Pine 2662
    e['minDynamicResistanceLastTestAge'] = rt.NA
    # Pine 2663
    e['maxDynamicResistanceLastTestAge'] = rt.NA
    # Pine 2664
    e['minDynamicResistanceES'] = rt.NA
    # Pine 2665
    e['maxDynamicResistanceES'] = rt.NA
    # Pine 2666
    e['minDynamicResistanceWeakTouches'] = rt.NA
    # Pine 2667
    e['maxDynamicResistanceWeakTouches'] = rt.NA
    # Pine 2668
    e['minDynamicResistanceStrongTouches'] = rt.NA
    # Pine 2669
    e['maxDynamicResistanceStrongTouches'] = rt.NA
    # Pine 2670
    if rt.truth(rt.binary('>', rt.arr_size(e['resistanceScoreArray']), 0)):
        # Pine 2671
        for e['i'] in rt.inclusive(0, rt.binary('-', rt.arr_size(e['resistanceScoreArray']), 1)):
            # Pine 2672
            e['zoneID'] = rt.arr_get(e['resistanceZoneIDArray'], e['i'])
            # Pine 2673
            e['isInstitutionalZone'] = rt.binary('!=', rt.arr_indexof(e['instResistanceZoneIDArray'], e['zoneID']), rt.neg(1))
            # Pine 2674
            if rt.truth((not rt.truth(e['isInstitutionalZone']))):
                # Pine 2675
                e['resistanceES'] = rt.arr_get(e['resistanceESArray'], e['i'])
                # Pine 2676
                e['resistanceScore'] = rt.arr_get(e['resistanceScoreArray'], e['i'])
                # Pine 2677
                e['strongTouches'] = rt.arr_get(e['resistanceStrongRejectArray'], e['i'])
                # Pine 2678
                e['totalTouches'] = rt.arr_get(e['resistanceTouchArray'], e['i'])
                # Pine 2679
                e['weakTouches'] = rt.math_max(0.0, rt.binary('-', e['totalTouches'], e['strongTouches']))
                # Pine 2680
                e['dynamicResistanceScoreSum'] = rt.binary('+', e['dynamicResistanceScoreSum'], e['resistanceScore'])
                # Pine 2681
                e['dynamicResistanceESSum'] = rt.binary('+', e['dynamicResistanceESSum'], e['resistanceES'])
                # Pine 2682
                e['dynamicResistanceCount'] = rt.binary('+', e['dynamicResistanceCount'], 1)
                # Pine 2683
                e['minDynamicResistanceES'] = (e['resistanceES'] if rt.truth(rt.is_na(e['minDynamicResistanceES'])) else rt.math_min(e['minDynamicResistanceES'], e['resistanceES']))
                # Pine 2684
                e['maxDynamicResistanceES'] = (e['resistanceES'] if rt.truth(rt.is_na(e['maxDynamicResistanceES'])) else rt.math_max(e['maxDynamicResistanceES'], e['resistanceES']))
                # Pine 2685
                e['minDynamicResistanceWeakTouches'] = (rt.to_int(e['weakTouches']) if rt.truth(rt.is_na(e['minDynamicResistanceWeakTouches'])) else rt.math_min(e['minDynamicResistanceWeakTouches'], rt.to_int(e['weakTouches'])))
                # Pine 2686
                e['maxDynamicResistanceWeakTouches'] = (rt.to_int(e['weakTouches']) if rt.truth(rt.is_na(e['maxDynamicResistanceWeakTouches'])) else rt.math_max(e['maxDynamicResistanceWeakTouches'], rt.to_int(e['weakTouches'])))
                # Pine 2687
                e['minDynamicResistanceStrongTouches'] = (rt.to_int(e['strongTouches']) if rt.truth(rt.is_na(e['minDynamicResistanceStrongTouches'])) else rt.math_min(e['minDynamicResistanceStrongTouches'], rt.to_int(e['strongTouches'])))
                # Pine 2688
                e['maxDynamicResistanceStrongTouches'] = (rt.to_int(e['strongTouches']) if rt.truth(rt.is_na(e['maxDynamicResistanceStrongTouches'])) else rt.math_max(e['maxDynamicResistanceStrongTouches'], rt.to_int(e['strongTouches'])))
                # Pine 2690
                e['lastTestBar'] = rt.arr_get(e['resistanceLastTestBarArray'], e['i'])
                # Pine 2691
                if rt.truth((not rt.truth(rt.is_na(e['lastTestBar'])))):
                    # Pine 2692
                    e['lastTestAge'] = rt.math_max(0.0, rt.binary('-', e['bar_index'], e['lastTestBar']))
                    # Pine 2693
                    e['dynamicResistanceLastTestAgeSum'] = rt.binary('+', e['dynamicResistanceLastTestAgeSum'], e['lastTestAge'])
                    # Pine 2694
                    e['dynamicResistanceLastTestAgeCount'] = rt.binary('+', e['dynamicResistanceLastTestAgeCount'], 1)
                    # Pine 2695
                    e['minDynamicResistanceLastTestAge'] = (e['lastTestAge'] if rt.truth(rt.is_na(e['minDynamicResistanceLastTestAge'])) else rt.math_min(e['minDynamicResistanceLastTestAge'], e['lastTestAge']))
                    # Pine 2696
                    e['maxDynamicResistanceLastTestAge'] = (e['lastTestAge'] if rt.truth(rt.is_na(e['maxDynamicResistanceLastTestAge'])) else rt.math_max(e['maxDynamicResistanceLastTestAge'], e['lastTestAge']))
    # Pine 2698
    e['averageDynamicResistanceScore'] = (rt.binary('/', e['dynamicResistanceScoreSum'], e['dynamicResistanceCount']) if rt.truth(rt.binary('>', e['dynamicResistanceCount'], 0)) else rt.NA)
    # Pine 2699
    e['averageDynamicResistanceES'] = (rt.binary('/', e['dynamicResistanceESSum'], e['dynamicResistanceCount']) if rt.truth(rt.binary('>', e['dynamicResistanceCount'], 0)) else rt.NA)
    # Pine 2700
    e['averageDynamicResistanceLastTestAge'] = (rt.binary('/', e['dynamicResistanceLastTestAgeSum'], e['dynamicResistanceLastTestAgeCount']) if rt.truth(rt.binary('>', e['dynamicResistanceLastTestAgeCount'], 0)) else rt.NA)
    # Pine 2701
    e['dynamicResistanceWTNormalized'] = rt.normalize(e['nearestResistanceWeakTouches'], e['minDynamicResistanceWeakTouches'], e['maxDynamicResistanceWeakTouches'], e['normalizationPower'], True)
    # Pine 2702
    e['dynamicResistanceSTNormalized'] = rt.normalize(e['nearestResistanceStrongTouches'], e['minDynamicResistanceStrongTouches'], e['maxDynamicResistanceStrongTouches'], e['normalizationPower'], True)
    # Pine 2703
    e['dynamicResistanceESNormalized'] = rt.normalize(e['nearestResistanceES'], e['minDynamicResistanceES'], e['maxDynamicResistanceES'], e['normalizationPower'], True)
    # Pine 2704
    e['dynamicResistanceLastTestAgeNormalized'] = rt.normalize(e['nearestResistanceLastTestAge'], e['minDynamicResistanceLastTestAge'], e['maxDynamicResistanceLastTestAge'], e['normalizationPower'], False)
    # Pine 2707
    e['instResistanceScoreSum'] = 0.0
    # Pine 2708
    e['instResistanceESSum'] = 0.0
    # Pine 2709
    e['instResistanceLastTestAgeSum'] = 0.0
    # Pine 2710
    e['instResistanceCount'] = 0
    # Pine 2711
    e['instResistanceLastTestAgeCount'] = 0
    # Pine 2712
    e['minInstResistanceLastTestAge'] = rt.NA
    # Pine 2713
    e['maxInstResistanceLastTestAge'] = rt.NA
    # Pine 2714
    e['minInstResistanceES'] = rt.NA
    # Pine 2715
    e['maxInstResistanceES'] = rt.NA
    # Pine 2716
    e['minInstResistanceWeakTouches'] = rt.NA
    # Pine 2717
    e['maxInstResistanceWeakTouches'] = rt.NA
    # Pine 2718
    e['minInstResistanceStrongTouches'] = rt.NA
    # Pine 2719
    e['maxInstResistanceStrongTouches'] = rt.NA
    # Pine 2720
    e['maxInstResistanceFailures'] = rt.NA
    # Pine 2721
    e['minInstResistanceFailures'] = rt.NA
    # Pine 2722
    if rt.truth(rt.binary('>', rt.arr_size(e['instResistanceZoneIDArray']), 0)):
        # Pine 2723
        for e['i'] in rt.inclusive(0, rt.binary('-', rt.arr_size(e['instResistanceZoneIDArray']), 1)):
            # Pine 2724
            e['instZoneID'] = rt.arr_get(e['instResistanceZoneIDArray'], e['i'])
            # Pine 2725
            e['dynamicIndex'] = rt.arr_indexof(e['resistanceZoneIDArray'], e['instZoneID'])
            # Pine 2726
            if rt.truth(rt.binary('!=', e['dynamicIndex'], rt.neg(1))):
                # Pine 2727
                e['resistanceES'] = rt.arr_get(e['resistanceESArray'], e['dynamicIndex'])
                # Pine 2728
                e['resistanceScore'] = rt.arr_get(e['instResistanceScoreArray'], e['i'])
                # Pine 2729
                e['strongTouches'] = rt.arr_get(e['resistanceStrongRejectArray'], e['dynamicIndex'])
                # Pine 2730
                e['totalTouches'] = rt.arr_get(e['resistanceTouchArray'], e['dynamicIndex'])
                # Pine 2731
                e['weakTouches'] = rt.math_max(0.0, rt.binary('-', e['totalTouches'], e['strongTouches']))
                # Pine 2732
                e['instFailures'] = rt.arr_get(e['instResistanceFailureCountArray'], e['i'])
                # Pine 2733
                e['instResistanceScoreSum'] = rt.binary('+', e['instResistanceScoreSum'], e['resistanceScore'])
                # Pine 2734
                e['instResistanceESSum'] = rt.binary('+', e['instResistanceESSum'], e['resistanceES'])
                # Pine 2735
                e['instResistanceCount'] = rt.binary('+', e['instResistanceCount'], 1)
                # Pine 2736
                e['minInstResistanceES'] = (e['resistanceES'] if rt.truth(rt.is_na(e['minInstResistanceES'])) else rt.math_min(e['minInstResistanceES'], e['resistanceES']))
                # Pine 2737
                e['maxInstResistanceES'] = (e['resistanceES'] if rt.truth(rt.is_na(e['maxInstResistanceES'])) else rt.math_max(e['maxInstResistanceES'], e['resistanceES']))
                # Pine 2738
                e['minInstResistanceWeakTouches'] = (rt.to_int(e['weakTouches']) if rt.truth(rt.is_na(e['minInstResistanceWeakTouches'])) else rt.math_min(e['minInstResistanceWeakTouches'], rt.to_int(e['weakTouches'])))
                # Pine 2739
                e['maxInstResistanceWeakTouches'] = (rt.to_int(e['weakTouches']) if rt.truth(rt.is_na(e['maxInstResistanceWeakTouches'])) else rt.math_max(e['maxInstResistanceWeakTouches'], rt.to_int(e['weakTouches'])))
                # Pine 2740
                e['minInstResistanceStrongTouches'] = (rt.to_int(e['strongTouches']) if rt.truth(rt.is_na(e['minInstResistanceStrongTouches'])) else rt.math_min(e['minInstResistanceStrongTouches'], rt.to_int(e['strongTouches'])))
                # Pine 2741
                e['maxInstResistanceStrongTouches'] = (rt.to_int(e['strongTouches']) if rt.truth(rt.is_na(e['maxInstResistanceStrongTouches'])) else rt.math_max(e['maxInstResistanceStrongTouches'], rt.to_int(e['strongTouches'])))
                # Pine 2742
                e['minInstResistanceFailures'] = (rt.to_int(e['instFailures']) if rt.truth(rt.is_na(e['minInstResistanceFailures'])) else rt.math_min(e['minInstResistanceFailures'], rt.to_int(e['instFailures'])))
                # Pine 2743
                e['maxInstResistanceFailures'] = (rt.to_int(e['instFailures']) if rt.truth(rt.is_na(e['maxInstResistanceFailures'])) else rt.math_max(e['maxInstResistanceFailures'], rt.to_int(e['instFailures'])))
                # Pine 2745
                e['lastTestBar'] = rt.arr_get(e['resistanceLastTestBarArray'], e['dynamicIndex'])
                # Pine 2746
                if rt.truth((not rt.truth(rt.is_na(e['lastTestBar'])))):
                    # Pine 2747
                    e['lastTestAge'] = rt.math_max(0.0, rt.binary('-', e['bar_index'], e['lastTestBar']))
                    # Pine 2748
                    e['instResistanceLastTestAgeSum'] = rt.binary('+', e['instResistanceLastTestAgeSum'], e['lastTestAge'])
                    # Pine 2749
                    e['instResistanceLastTestAgeCount'] = rt.binary('+', e['instResistanceLastTestAgeCount'], 1)
                    # Pine 2750
                    e['minInstResistanceLastTestAge'] = (e['lastTestAge'] if rt.truth(rt.is_na(e['minInstResistanceLastTestAge'])) else rt.math_min(e['minInstResistanceLastTestAge'], e['lastTestAge']))
                    # Pine 2751
                    e['maxInstResistanceLastTestAge'] = (e['lastTestAge'] if rt.truth(rt.is_na(e['maxInstResistanceLastTestAge'])) else rt.math_max(e['maxInstResistanceLastTestAge'], e['lastTestAge']))
    # Pine 2753
    e['averageInstResistanceScore'] = (rt.binary('/', e['instResistanceScoreSum'], e['instResistanceCount']) if rt.truth(rt.binary('>', e['instResistanceCount'], 0)) else rt.NA)
    # Pine 2754
    e['averageInstResistanceES'] = (rt.binary('/', e['instResistanceESSum'], e['instResistanceCount']) if rt.truth(rt.binary('>', e['instResistanceCount'], 0)) else rt.NA)
    # Pine 2755
    e['averageInstResistanceLastTestAge'] = (rt.binary('/', e['instResistanceLastTestAgeSum'], e['instResistanceLastTestAgeCount']) if rt.truth(rt.binary('>', e['instResistanceLastTestAgeCount'], 0)) else rt.NA)
    # Pine 2756
    e['instResistanceWTNormalized'] = rt.normalize(e['nearestResistanceWeakTouches'], e['minInstResistanceWeakTouches'], e['maxInstResistanceWeakTouches'], e['normalizationPower'], True)
    # Pine 2757
    e['instResistanceSTNormalized'] = rt.normalize(e['nearestResistanceStrongTouches'], e['minInstResistanceStrongTouches'], e['maxInstResistanceStrongTouches'], e['normalizationPower'], True)
    # Pine 2758
    e['instResistanceESNormalized'] = rt.normalize(e['nearestInstResistanceES'], e['minInstResistanceES'], e['maxInstResistanceES'], e['normalizationPower'], True)
    # Pine 2759
    e['instResistanceFailureNormalized'] = rt.normalize(e['nearestInstResistanceFailureCount'], e['minInstResistanceFailures'], e['maxInstResistanceFailures'], e['normalizationPower'], True)
    # Pine 2760
    e['instResistanceLastTestAgeNormalized'] = rt.normalize(e['nearestInstResistanceLastTestAge'], e['minInstResistanceLastTestAge'], e['maxInstResistanceLastTestAge'], e['normalizationPower'], False)

def update(e):
    update_zone_geometry(e)
    update_support_zones(e)
    update_institutional_support(e)
    update_resistance_zones(e)
    update_institutional_resistance(e)
