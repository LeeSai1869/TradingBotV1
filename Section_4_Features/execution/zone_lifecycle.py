"""Export authoritative S/R changes after Pine has invalidated and merged zones.

Only births, changed bounds/classification, and removals are stored per candle.
No display-side price heuristics or additional zone limits change the strategy.
"""
import json


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
