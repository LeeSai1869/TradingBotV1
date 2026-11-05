"""Independent spot sell scenarios. No candle-price gates or exchange actions."""
from dataclasses import dataclass

EARLY_TRAIL = 'S1_EARLY_SELL_TRAIL'
MATURITY = 'S2_BULLISH_SPREAD_MATURITY'
CONTROL = 'S3_EMERGING_BUYER_CONTROL_LOSS'
RULE_IDS = (EARLY_TRAIL, MATURITY, CONTROL)


@dataclass(frozen=True)
class SellConfig:
    enabled: tuple = RULE_IDS
    maturity_spread: float = 40.
    trailing_atr: float = 1.5

    def __post_init__(self):
        if set(self.enabled) - set(RULE_IDS) or len(set(self.enabled)) != len(self.enabled):
            raise ValueError('Unknown or duplicate sell rule')
        if self.maturity_spread != 40. or self.trailing_atr != 1.5:
            raise ValueError('This controlled baseline fixes spread maturity at 40 and trailing at 1.5 ATR')


def initial_state(entry_context):
    plus, minus, spread = (entry_context[k] for k in ('di_plus', 'di_minus', 'spread'))
    return dict(entry_scenario='BELOW_BOTH' if plus < minus and plus < spread else 'OTHER',
                control_gained=False, spread_mature=False, trailing_armed=False)


def evaluate(state, current, previous, dominant_plus_peak, config):
    """Evaluate each rule independently; choose one exit by declared priority.

    Context values are closed-bar DI measurements. Trailing price maintenance is
    separate: once armed, the engine updates it without further DI permissions.
    """
    state = dict(state)
    notes = []
    plus, minus, spread = (current[k] for k in ('di_plus', 'di_minus', 'spread'))
    if EARLY_TRAIL in config.enabled and dominant_plus_peak:
        notes.append(dict(type='EARLY_SELL_SETUP', rule_id=EARLY_TRAIL, action='ARM_TRAIL'))
        if not state['trailing_armed']:
            state['trailing_armed'] = True
            notes.append(dict(type='TRAIL_ARMED', rule_id=EARLY_TRAIL, action='STATE'))

    was_mature = state['spread_mature']
    if MATURITY in config.enabled:
        if not state['spread_mature'] and plus > minus and spread > config.maturity_spread:
            state['spread_mature'] = True
            notes.append(dict(type='BULLISH_SPREAD_MATURE', rule_id=MATURITY, action='STATE'))
        if was_mature and previous is not None and spread < previous['spread']:
            notes.append(dict(type='BULLISH_SPREAD_DECREASE', rule_id=MATURITY, action='EXIT',
                              previous_spread=previous['spread'], spread=spread, delta_spread=spread-previous['spread']))

    if CONTROL in config.enabled and state['entry_scenario'] == 'BELOW_BOTH':
        if not state['control_gained'] and plus > minus:
            state['control_gained'] = True
            notes.append(dict(type='BUYER_CONTROL_GAINED', rule_id=CONTROL, action='STATE'))
        if state['control_gained'] and previous is not None:
            crossed = []
            if previous['di_minus'] <= previous['di_plus'] and minus > plus:
                crossed.append('DI_MINUS')
            if previous['spread'] <= previous['di_plus'] and spread > plus:
                crossed.append('ABS_DI_SPREAD')
            if crossed:
                notes.append(dict(type='BUYER_CONTROL_LOST', rule_id=CONTROL, action='EXIT', crossed=crossed, previous_context=dict(previous)))

    # Stops are processed before these close-time rules. Among signal exits,
    # maturity has priority over control loss; all matching evidence is retained.
    exits = {note['rule_id'] for note in notes if note['action'] == 'EXIT'}
    selected = next((rule for rule in (MATURITY, CONTROL) if rule in exits), None)
    return state, notes, selected


def manifest(config):
    return [dict(id=EARLY_TRAIL, enabled=EARLY_TRAIL in config.enabled,
                 situation='Holding BTC; dominant DI+ three-candle peak', action='Arm trailing only; no direct sell'),
            dict(id=MATURITY, enabled=MATURITY in config.enabled,
                 situation='Bullish absolute spread exceeded 40; first subsequent decrease', action='Exit next open', priority=20),
            dict(id=CONTROL, enabled=CONTROL in config.enabled,
                 situation='DI+ below DI- and spread at entry; later gained control, then lost it by crossover',
                 action='Exit next open', priority=30)]
