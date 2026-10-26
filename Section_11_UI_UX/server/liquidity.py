"""Optional read-only liquidity attachment to the existing combined chart poll."""
import sqlite3
import zlib
from Section_1_Global_Core.liquidity import store


def snapshot(symbol):
    try:return store.snapshot(symbol)
    except (sqlite3.Error,OSError,ValueError,zlib.error) as error:
        return dict(venue='binance',market='usdt_perpetual',symbol=symbol,status='unavailable',
                    reason='Liquidity memory unavailable: '+str(error),latest=None,history=[])
