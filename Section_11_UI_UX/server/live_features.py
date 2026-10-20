"""Pure provisional indicators. Never invoke stateful processors or write storage."""
from dataclasses import asdict
import math
from Section_1_Global_Core.memory_storage.Storage import db


def calculate(symbol, interval, client):
    # Match the permanent processor's 500-bar window, replacing only its last bar.
    import pandas as pd
    from Section_4_Features.features import ema, rsi
    rows = db.read_klines_tail(symbol, interval, client['open_time'], 499)
    if not rows or rows[-1][8] + 1 != client['open_time']:
        return None
    if any(a[8] + 1 != b[2] for a, b in zip(rows, rows[1:])):
        return None
    current = tuple(client[key] for key in
                    ('symbol','interval','open_time','open','high','low','close','volume','close_time'))
    frame = pd.DataFrame([*rows, current], columns=
        ['symbol','interval','time','open','high','low','close','volume','close_time'])
    values = {**asdict(ema.compute(frame)), **asdict(rsi.compute(frame))}
    return {key: (value if isinstance(value, bool) or value is None or math.isfinite(value) else None)
            for key, value in values.items()}
