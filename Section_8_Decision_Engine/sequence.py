"""Shared signal policy: one direction may only follow the opposite direction.

WAIT, unavailable features and gaps never erase the last accepted direction.
Callers own an independent, persistent last_signal for each symbol/timeframe.
"""


def alternate(decision,last_signal=None):
    signal=decision.get('signal_type')
    if signal not in ('BUY','SELL'):return decision,last_signal
    if signal==last_signal:
        return {**decision,'signal_type':None,'decision_state':'SUPPRESSED','trigger':None},last_signal
    return decision,signal
