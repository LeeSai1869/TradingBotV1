"""A5 — Freshness audit.

For each (symbol, interval) pair, verifies that the latest stored
bar is within `multiplier × interval_ms` of now.
"""

from __future__ import annotations

import sqlite3
import time

from . import audit_config as cfg
from .audit_schema import INTERVAL_MS


def run(pairs: list[tuple[str, str]]) -> dict:
    """Audit closed-candle availability with one explicitly closed read handle."""
    if not cfg.A5_ENABLED:return {'enabled':False}
    from ..Storage import klines_store
    now_ms=int(time.time()*1000);stale=[];missing=[];waiting=[];fresh=0
    conn=sqlite3.connect(cfg.KLINES_DB.resolve().as_uri()+'?mode=ro',uri=True,timeout=1) if cfg.KLINES_DB.exists() else None
    try:
        waits=klines_store.first_close_waits(conn,now_ms) if conn else {}
        for symbol,interval in pairs:
            step=INTERVAL_MS.get(interval)
            if step is None:continue
            row=conn.execute('SELECT close_time FROM klines WHERE symbol=? AND interval=? ORDER BY open_time DESC LIMIT 1',(symbol,interval)).fetchone() if conn else None
            last=row[0] if row else None
            if last is None:
                if (symbol,interval) in waits:
                    waiting.append({'symbol':symbol,'interval':interval,'first_close_ms':waits[symbol,interval],
                                    'reason':'source has no completed candle yet'})
                else:missing.append({'symbol':symbol,'interval':interval,'reason':'no stored closed candles'})
                continue
            age_ms=now_ms-last;threshold=step*cfg.A5_FRESHNESS_MULTIPLIER
            if age_ms>threshold:
                stale.append({'symbol':symbol,'interval':interval,'last_close_ms':last,'age_ms':age_ms,
                              'threshold_ms':int(threshold),'age_intervals':round(age_ms/step,2)})
            else:fresh+=1
    finally:
        if conn:conn.close()
    return {'enabled':True,'checked':len(pairs),'fresh':fresh,'stale':stale,'stale_count':len(stale),
            'missing':len(missing),'missing_pairs':missing,'awaiting_first_close':waiting}
