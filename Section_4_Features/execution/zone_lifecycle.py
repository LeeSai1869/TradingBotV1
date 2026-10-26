"""Export authoritative S/R changes after Pine has invalidated and merged zones.

Only births, changed bounds/classification, and removals are stored per candle.
No display-side price heuristics or additional zone limits change the strategy.
"""
import json
from . import ob_lifecycle


def changes(previous, current):
    events = [dict(id=identity, **zone, before=previous.get(identity)) for identity, zone in current.items()
              if previous.get(identity) != zone]
    events.extend(dict(id=identity, removed=True, before=previous[identity]) for identity in previous.keys() - current.keys())
    return json.dumps(events, separators=(',', ':'), sort_keys=True)


def snapshot(ids, lows, highs, institutional, side):
    institutions = set(institutional)
    return {str(identity): dict(side=side, low=low, high=high, institutional=identity in institutions)
            for identity, low, high in zip(ids, lows, highs)}


def bounds(zones, identity, side, edge):
    zone = zones.get(str(identity))
    return zone[edge] if zone and zone['side'] == side else None


def update(e):
    if 'srDisplayPrevious' not in e.persistent:
        e.initialize('srDisplayPrevious', {})
    e['srDisplayCurrent'] = {
        **snapshot(e['supportZoneIDArray'], e['supportLowArray'], e['supportHighArray'], e['instSupportZoneIDArray'], 'support'),
        **snapshot(e['resistanceZoneIDArray'], e['resistanceLowArray'], e['resistanceHighArray'], e['instResistanceZoneIDArray'], 'resistance'),
    }
    e['srZoneEvents'] = changes(e['srDisplayPrevious'], e['srDisplayCurrent'])
    e['srDisplayPrevious'] = e['srDisplayCurrent']
    e['instSupportZoneLow'] = bounds(e['srDisplayCurrent'], e['nearestInstSupportZoneID'], 'support', 'low')
    e['instSupportZoneHigh'] = bounds(e['srDisplayCurrent'], e['nearestInstSupportZoneID'], 'support', 'high')
    e['instResistanceZoneLow'] = bounds(e['srDisplayCurrent'], e['nearestInstResistanceZoneID'], 'resistance', 'low')
    e['instResistanceZoneHigh'] = bounds(e['srDisplayCurrent'], e['nearestInstResistanceZoneID'], 'resistance', 'high')

    # Explicit inputs let selective replay trace only OB dependencies.
    if 'obDisplayZones' not in e.persistent:
        e.initialize('obDisplayZones', {})
    e['obDisplayZones'], e['obZoneEvents'] = ob_lifecycle.advance(
        e['obDisplayZones'], e['bar_index'], e['time'], e['l'], e['h'], e['c'], [
            (False,'bull',e['bullOBEvent'],e['bullOBLow'],e['bullOBHigh'],e['bullFVG'],e['bullOBStrength']),
            (False,'bear',e['bearOBEvent'],e['bearOBLow'],e['bearOBHigh'],e['bearFVG'],e['bearOBStrength']),
            (True,'bull',e['strictBullOBEvent'],e['strictBullOBLow'],e['strictBullOBHigh'],e['bullFVG'],e['bullOBStrength']),
            (True,'bear',e['strictBearOBEvent'],e['strictBearOBLow'],e['strictBearOBHigh'],e['bearFVG'],e['bearOBStrength']),
        ])
