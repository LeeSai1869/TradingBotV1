"""Causal cycle hypotheses from public outputs and a frozen range sequence.

No pivot detector, rolling indicator, data fetch or trade decision lives here.
"""
from copy import deepcopy
import hashlib
import json
import math
from .phase_config import PhaseConfig

VERSION = '1.0.0'
DEPENDENCIES = {'TREND': '1.0.0', 'STRUCTURE': '1.1.0', 'PARTICIPATION': '1.0.0'}
FIELDS = ('range_high', 'range_low', 'atr', 'efficiency_ratio', 'natr_change_fraction',
          'bb_width_change_fraction', 'measurement_contiguous_bars', 'measurement_gap',
          'measurement_version', 'measurement_config_id')
UNITS = {key: 'dimensionless' for key in FIELDS}
for key in ('range_high', 'range_low', 'atr'):
    UNITS[key] = 'price'
UNITS.update(measurement_contiguous_bars='candles', measurement_gap='boolean',
             measurement_version='version', measurement_config_id='identifier')
UNKNOWN = dict(phase='UNKNOWN', development='UNKNOWN', preceding_trend='UNKNOWN')
SEQUENCE_KEYS = dict(prior=None, trend_direction=None, trend_count=0, trend_origin_time=None, range=None,
                     classification=UNKNOWN, last_resolution=None)


def finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _dependency(snapshot, name, flags):
    """Reject mismatched, provisional, future, unreferenced or unusable outputs."""
    dep = snapshot.get('dependencies', {}).get(name)
    expected = snapshot.get('dependency_expectations', {}).get(name, {})
    ref = snapshot.get('dependency_refs', {}).get(name)
    if not isinstance(dep, dict):
        flags.append(name + '_UNAVAILABLE')
        return None
    bound = all(isinstance(expected.get(k), str) and expected[k] and dep.get(k) == expected[k]
                for k in ('engine_version', 'config_hash', 'input_signature'))
    end, known = snapshot['candle_close_time'], snapshot['as_of']
    reconstructed = (snapshot['provenance_mode'] == 'HISTORICAL_RECONSTRUCTION'
                     and dep.get('provenance', {}).get('mode') == 'HISTORICAL_RECONSTRUCTION')
    at, available = dep.get('as_of'), dep.get('available_at')
    good = (bound and dep.get('engine') == name and dep.get('engine_version') == DEPENDENCIES[name]
            and dep.get('identity') == snapshot['identity'] and dep.get('mode') == 'CONFIRMED'
            and dep.get('candle_open_time') == snapshot['candle_open_time']
            and dep.get('candle_close_time') == end and type(at) is int and end < at <= known
            and type(available) is int and available >= at and (available <= known or reconstructed)
            and isinstance(ref, str) and bool(ref) and isinstance(dep.get('classification'), dict)
            and finite(dep.get('coverage')) and 0 < dep['coverage'] <= 1
            and dep.get('data_quality') in ('VALID', 'PARTIAL'))
    if not good:
        flags.append(name + '_DEPENDENCY_REJECTED')
        return None
    if reconstructed:
        flags.append('DEPENDENCY_AVAILABILITY_RECONSTRUCTED')
    return dep


def _events(dep, start, end, flags):
    """Consume only public same-candle producer events; never the old last_event."""
    events = dep.get('measurements', {}).get('new_events') if dep else None
    if not isinstance(events, list) or len(events) > 8:
        flags.append('STRUCTURE_EVENT_LINEAGE_UNAVAILABLE')
        return None
    clean = []
    for event in events:
        if not isinstance(event, dict):
            flags.append('STRUCTURE_EVENT_REJECTED')
            return None
        origin = event.get('origin_time')
        good = (isinstance(event.get('id'), str) and bool(event['id'])
                and event.get('source_version') == 'structure-events-v1'
                and type(event.get('known_time')) is int and event['known_time'] == end + 1
                and type(event.get('confirmation_time')) is int and event['confirmation_time'] == start
                and type(origin) is int and 0 <= origin <= start)
        if event.get('type') in ('PIVOT_HIGH', 'PIVOT_LOW'):
            good = good and origin < start and finite(event.get('price')) and event['price'] > 0
        elif event.get('type') not in ('BOS', 'CHOCH'):
            good = False
        if good:
            clean.append(event)
        else:
            flags.append('STRUCTURE_EVENT_REJECTED')
    return clean


def evaluate(snapshot, config=None, previous_state=None):
    cfg = config or PhaseConfig()
    if not isinstance(cfg, PhaseConfig):
        raise TypeError('Use PhaseConfig')
    identity = deepcopy(snapshot['identity'])
    if set(identity) != {'venue', 'market_type', 'instrument_id', 'symbol', 'timeframe', 'dataset_generation'} or any(not isinstance(v, str) or not v for v in identity.values()):
        raise ValueError('Complete Phase identity required')
    start, end, known, computed = (snapshot[k] for k in ('candle_open_time', 'candle_close_time', 'as_of', 'computed_at'))
    if any(type(v) is not int or v < 0 for v in (start, end, known, computed)) or end < start or computed < known:
        raise ValueError('Invalid Phase times')
    closed = snapshot['closed']
    if type(closed) is not bool or closed and known <= end or not closed and known < start:
        raise ValueError('Invalid candle availability')
    if snapshot['provenance_mode'] not in ('LIVE', 'SIMULATION', 'HISTORICAL_RECONSTRUCTION'):
        raise ValueError('Invalid provenance')
    signature = snapshot['input_signature']
    if not isinstance(signature, str) or not signature:
        raise ValueError('Phase signature required')
    binding = dict(identity=identity, config_hash=cfg.fingerprint, input_signature=signature, state_schema_version=VERSION)
    state = deepcopy(previous_state) if previous_state else dict(**binding, last_open=None, last_close=None, index=-1, **deepcopy(SEQUENCE_KEYS))
    if any(state.get(k) != v for k, v in binding.items()):
        raise ValueError('Phase state identity/config/source mismatch')
    if state['last_open'] is not None and start <= state['last_open']:
        raise ValueError('Phase candles must be chronological')
    old = deepcopy(state['classification'])
    flags, f, invalid = [], {}, False
    for key in FIELDS:
        value = snapshot['features'].get(key)
        at, kind = snapshot['field_available_at'].get(key), UNITS[key]
        if value is not None and (snapshot['field_validity'].get(key) != 'VALID' or snapshot['units'].get(key) != kind or type(at) is not int or not 0 <= at <= known):
            value = None
            flags.append('INPUT_UNAVAILABLE:' + key)
        if value is not None:
            valid = (isinstance(value, str) and bool(value)) if kind in ('version', 'identifier') else (type(value) is bool or finite(value) and value in (0, 1)) if kind == 'boolean' else finite(value)
            if valid and kind == 'price':
                valid = value >= 0 if key == 'atr' else value > 0
            if valid and key == 'efficiency_ratio':
                valid = 0 <= value <= 1
            if valid and kind == 'candles':
                valid = value >= 0 and int(value) == value
            if not valid:
                value, invalid = None, True
                flags.append('INVALID_INPUT:' + key)
            elif kind == 'boolean':
                value = bool(value)
            elif kind == 'candles':
                value = int(value)
        f[key] = value
    prices = [snapshot['candle'].get(k) for k in ('open', 'high', 'low', 'close')]
    raw = all(finite(v) and v > 0 for v in prices)
    raw = raw and prices[1] >= max(prices) and prices[2] <= min(prices)
    gap = state['last_close'] is not None and start != state['last_close'] + 1 or f['measurement_gap'] is True
    parameters = snapshot.get('feature_parameters', {})
    compatible = all(parameters.get(k) == expected for k, expected in
                     (('rangeLookback', cfg.range_length), ('measurementERLength', cfg.er_length), ('measurementChangeLength', cfg.change_length)))
    if not compatible:
        flags.append('INCOMPATIBLE_FEATURE_PARAMETERS')
    calendar = snapshot.get('market_metadata', {}).get('calendar') == '24/7 UTC'
    if not calendar:
        flags.append('UNSUPPORTED_MARKET_CALENDAR')
    shared = f['measurement_version'] == 'shared-v1' and bool(f['measurement_config_id'])
    if not shared:
        flags.append('SHARED_FEATURES_UNAVAILABLE')
    deps = {name: _dependency(snapshot, name, flags) for name in DEPENDENCIES}
    trend, structure, participation = (deps[name] for name in DEPENDENCIES)
    structural_events = _events(structure, start, end, flags)
    td = trend['classification'].get('direction') if trend else None
    sd = structure['classification'].get('direction') if structure else None
    required = (trend and structure and participation and td in ('BULLISH', 'BEARISH', 'NEUTRAL')
                and sd in ('BULLISH', 'BEARISH', 'NEUTRAL') and structural_events is not None)
    usable = closed and raw and not invalid and not gap and shared and compatible and calendar and bool(required)
    if not closed:
        flags.append('CLOSED_DEPENDENCIES_REQUIRED_FOR_PREVIEW')
    state['index'] += 1
    events = []

    def emit(kind, **details):
        event = dict(type=kind, origin_time=start, known_time=end + 1, **details)
        event['id'] = hashlib.sha256(json.dumps([identity, cfg.fingerprint, signature, event], sort_keys=True, allow_nan=False).encode()).hexdigest()
        events.append(event)
        return event

    geometry = (all(f[k] is not None for k in ('range_high', 'range_low', 'atr', 'efficiency_ratio', 'measurement_contiguous_bars'))
                and f['range_high'] > f['range_low'] and f['atr'] > 0 and f['measurement_contiguous_bars'] >= cfg.range_length)
    if not geometry:
        flags.append('RANGE_MEASUREMENTS_UNAVAILABLE')
    vol_ok = all(f[k] is not None for k in ('natr_change_fraction', 'bb_width_change_fraction'))
    classification = UNKNOWN.copy()
    candidate_bars, required_bars, status = 0, cfg.preceding_bars, 'UNAVAILABLE'
    if not usable:
        state.update(deepcopy(SEQUENCE_KEYS))
        if gap:
            flags.append('CANDLE_GAP')
        if not required:
            flags.append('REQUIRED_ENGINE_EVIDENCE_UNAVAILABLE')
    else:
        classification = dict(phase='TRANSITION', development='DEVELOPING', preceding_trend='UNKNOWN')
        active = state['range']
        # A resolved sequence is never retroactively relabelled; a later candle
        # can start a new directional state with its own known time.
        if active and active.get('resolved'):
            state['range'] = active = None
        prior = state['prior']
        if prior and state['index'] - prior['index'] > cfg.preceding_max_age and not active:
            state['prior'] = prior = None
        established = (td in ('BULLISH', 'BEARISH') and td == sd
                       and trend['classification'].get('condition') == 'ESTABLISHED'
                       and structure['classification'].get('condition') == 'CONFIRMED'
                       and trend.get('confirmation', {}).get('status') == 'CONFIRMED')
        range_ready = (geometry and vol_ok and f['efficiency_ratio'] <= cfg.range_er_max
                       and (td == 'NEUTRAL' or structure['classification'].get('active_structure') == 'RANGE')
                       and max(f['natr_change_fraction'], f['bb_width_change_fraction']) <= cfg.volatility_change_max)
        if not active and range_ready:
            width_atr = (f['range_high'] - f['range_low']) / f['atr']
            if not finite(width_atr) or width_atr > cfg.max_range_atr:
                flags.append('RANGE_TOO_WIDE')
            else:
                origin = emit('RANGE_STARTED', low=f['range_low'], high=f['range_high'])
                active = dict(id=origin['id'], origin_time=start, known_time=end + 1,
                              low=f['range_low'], high=f['range_high'], atr=f['atr'], bars=0,
                              prior=deepcopy(prior), demand=[], supply=[], hypothesis=None,
                              breakout_direction=None, breakout_count=0, structural_break=None, resolved=False)
                state['range'] = active
                state.update(trend_direction=None, trend_count=0, trend_origin_time=None)
        if active:
            active['bars'] += 1
            low, high, atr = active['low'], active['high'], active['atr']
            width = high - low
            prior = active['prior']
            classification['preceding_trend'] = prior['direction'] if prior else 'UNKNOWN'
            required_bars, candidate_bars, status = cfg.range_min_bars, min(active['bars'], cfg.range_min_bars), 'PENDING'
            direction = 'BULLISH' if prices[3] > high + cfg.breakout_buffer_atr * atr else 'BEARISH' if prices[3] < low - cfg.breakout_buffer_atr * atr else None
            # Evidence starts strictly after the range has developed. No historical
            # pivots are admitted just because they were confirmed on today's bar.
            pc = participation['classification']
            involved = pc.get('activity') in ('NORMAL', 'HIGH', 'EXTREME')
            strong_flow = pc.get('activity') in ('HIGH', 'EXTREME') and pc.get('confirmation') == 'CONFIRMING'
            if active['bars'] >= cfg.range_min_bars and start > active['origin_time'] and low <= prices[3] <= high:
                demand = (strong_flow and prices[2] < low and prices[3] > prices[0] and prices[3] >= low + cfg.reclaim_fraction * width)
                supply = (strong_flow and prices[1] > high and prices[3] < prices[0] and prices[3] <= high - cfg.reclaim_fraction * width)
                for event in structural_events:
                    if event['origin_time'] <= active['origin_time']:
                        continue
                    if involved and event.get('type') == 'PIVOT_LOW' and event.get('classification') == 'HIGHER_LOW' and low <= event['price'] <= high:
                        demand = True
                    if involved and event.get('type') == 'PIVOT_HIGH' and event.get('classification') == 'LOWER_HIGH' and low <= event['price'] <= high:
                        supply = True
                for side, observed in (('demand', demand), ('supply', supply)):
                    if observed:
                        evidence = emit('RANGE_' + side.upper() + '_EVIDENCE', range_id=active['id'])
                        active[side] = (active[side] + [evidence])[-cfg.evidence_bars:]
                if prior:
                    demand_ready, supply_ready = (len(active[k]) >= cfg.evidence_bars for k in ('demand', 'supply'))
                    active['hypothesis'] = ('REACCUMULATION' if prior['direction'] == 'BULLISH' else 'ACCUMULATION') if demand_ready and not supply_ready else ('DISTRIBUTION' if prior['direction'] == 'BULLISH' else 'REDISTRIBUTION') if supply_ready and not demand_ready else None
            if active['hypothesis']:
                classification['phase'] = active['hypothesis']
                flags.append('CYCLE_HYPOTHESIS_NOT_OBSERVED_INSTITUTIONAL_INTENT')
            if direction:
                if active['breakout_direction'] != direction:
                    if active['breakout_direction']:
                        emit('FAILED_BREAKOUT', direction=active['breakout_direction'], range_id=active['id'])
                    active.update(breakout_direction=direction, breakout_count=0, structural_break=None)
                active['breakout_count'] += 1
                for event in structural_events:
                    source_type = event.get('source_type')
                    source_type = source_type.lower() if isinstance(source_type, str) else ''
                    if event['origin_time'] >= active['origin_time'] and event['type'] in ('BOS', 'CHOCH') and source_type in (('bullishbos', 'bullishchoch') if direction == 'BULLISH' else ('bearishbos', 'bearishchoch')):
                        active['structural_break'] = deepcopy(event)
                hypothesis_direction = 'BULLISH' if active['hypothesis'] in ('ACCUMULATION', 'REACCUMULATION') else 'BEARISH' if active['hypothesis'] else None
                if hypothesis_direction and direction != hypothesis_direction:
                    classification['development'] = 'INVALIDATED'
                    active['resolved'] = True
                    state['last_resolution'] = emit('PHASE_INVALIDATED', phase=active['hypothesis'], range_id=active['id'], range_origin_time=active['origin_time'])
                    status, candidate_bars, required_bars = 'CONFIRMED', 1, 1
                elif hypothesis_direction:
                    required_bars, candidate_bars = cfg.breakout_bars, min(active['breakout_count'], cfg.breakout_bars)
                    if active['breakout_count'] >= cfg.breakout_bars and active['structural_break'] and td == direction:
                        classification['development'] = 'CONFIRMED'
                        active['resolved'] = True
                        state['last_resolution'] = emit('PHASE_CONFIRMED', phase=active['hypothesis'], range_id=active['id'], range_origin_time=active['origin_time'], structural_event_id=active['structural_break']['id'])
                        status = 'CONFIRMED'
                    elif not active['structural_break']:
                        flags.append('STRUCTURAL_BREAK_CONFIRMATION_UNAVAILABLE')
                else:
                    # An ordinary range can resolve directionally without any
                    # retrospective claim of accumulation/distribution.
                    required_bars, candidate_bars = cfg.breakout_bars, min(active['breakout_count'], cfg.breakout_bars)
                    if active['breakout_count'] >= cfg.breakout_bars and active['structural_break'] and td == direction:
                        classification.update(phase='MARKUP' if direction == 'BULLISH' else 'MARKDOWN', development='CONFIRMED')
                        active['resolved'] = True
                        state['last_resolution'] = emit('RANGE_BREAKOUT_CONFIRMED', direction=direction, range_id=active['id'], range_origin_time=active['origin_time'], structural_event_id=active['structural_break']['id'])
                        status = 'CONFIRMED'
                    elif not active['structural_break']:
                        flags.append('STRUCTURAL_BREAK_CONFIRMATION_UNAVAILABLE')
            elif active['breakout_direction']:
                emit('FAILED_BREAKOUT', direction=active['breakout_direction'], range_id=active['id'])
                active.update(breakout_direction=None, breakout_count=0, structural_break=None)
            if active['bars'] > cfg.range_max_bars and not active['resolved']:
                classification.update(phase=active['hypothesis'] or 'TRANSITION', development='INVALIDATED')
                active['resolved'] = True
                state['last_resolution'] = emit('RANGE_EXPIRED', range_id=active['id'])
                status, candidate_bars, required_bars = 'CONFIRMED', 1, 1
            if not prior:
                flags.append('PRECEDING_TREND_UNAVAILABLE')
        else:
            if not established or state['trend_direction'] != td:
                state['trend_origin_time'] = start if established else None
            state['trend_count'] = state['trend_count'] + 1 if established and state['trend_direction'] == td else 1 if established else 0
            state['trend_direction'] = td if established else None
            candidate_bars = min(state['trend_count'], cfg.preceding_bars)
            status = 'PENDING'
            if state['trend_count'] >= cfg.preceding_bars:
                state['prior'] = dict(direction=td, origin_time=state['trend_origin_time'], known_time=end + 1, index=state['index'])
                classification.update(phase='MARKUP' if td == 'BULLISH' else 'MARKDOWN', development='CONFIRMED', preceding_trend=td)
                status = 'CONFIRMED'
            elif state['prior']:
                classification['preceding_trend'] = state['prior']['direction']
    # All input families have a fixed budget. Missing/partial children never gain
    # weight through renormalization. Confidence measures sequence completion.
    weights = dict(trend=.25, structure=.25, participation=.20, range=.20, volatility=.10)
    parts = dict(trend=.25 * trend['coverage'] if usable else 0., structure=.25 * structure['coverage'] if usable else 0.,
                 participation=.20 * participation['coverage'] if usable else 0., range=.20 if usable and geometry else 0., volatility=.10 if usable and vol_ok else 0.)
    coverage = sum(parts.values())
    sequence_fraction = (1. if classification['development'] in ('CONFIRMED', 'INVALIDATED') else .5 if classification['phase'] in ('ACCUMULATION', 'DISTRIBUTION', 'REACCUMULATION', 'REDISTRIBUTION') else .25) if usable else 0.
    confidence = coverage * sequence_fraction
    if closed and classification != old and classification['phase'] != 'UNKNOWN':
        emit('PHASE_TRANSITION', classification=deepcopy(classification))
    if not closed:
        events = []
    quality = 'GAP' if gap else 'INVALID' if invalid or not raw else 'WARMUP' if not usable else 'VALID' if coverage >= 1 - 1e-12 else 'PARTIAL'
    if snapshot['provenance_mode'] == 'HISTORICAL_RECONSTRUCTION':
        flags.append('AVAILABILITY_RECONSTRUCTED')
    references = [snapshot['dependency_refs'][name] for name in DEPENDENCIES if deps[name]]
    result = dict(contract_version='1.0.0', engine='PHASE', engine_version=VERSION, state_schema_version=VERSION, identity=identity,
                  candle_open_time=start, candle_close_time=end, as_of=known, computed_at=computed, available_at=computed if closed else None,
                  mode='CONFIRMED' if closed else 'PROVISIONAL', classification=classification if closed else old, candidate_classification=classification,
                  strength=round(100 * sequence_fraction, 8) if usable else None, confidence=round(confidence, 8), coverage=round(coverage, 8), data_quality=quality,
                  quality_flags=sorted(set(flags)), measurements={**f, 'range_sequence': deepcopy(state['range']), 'last_resolution': deepcopy(state['last_resolution']),
                  'new_events': events, 'evidence_budget': weights, 'available_contributions': parts, 'sequence_completion_fraction': sequence_fraction},
                  confirmation=dict(status=status, candidate_bars=candidate_bars if closed else 0, required_bars=required_bars),
                  previous_state=dict(classification=old), evidence=[dict(code='ORDERED_CYCLE_SEQUENCE', inputs=list(FIELDS) + list(DEPENDENCIES),
                  description='Preceding established trend, frozen range and later corroboration precede structural confirmation. Labels are cycle hypotheses, never hidden-position measurements or win probabilities.')],
                  config_hash=cfg.fingerprint, input_signature=signature, provenance=dict(mode=snapshot['provenance_mode'], source_versions=deepcopy(snapshot['source_versions']), dependency_results=references))
    state.update(last_open=start, last_close=end, classification=classification)
    return result, state if closed else deepcopy(previous_state)
