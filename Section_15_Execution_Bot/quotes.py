"""Public Binance Spot book quotes only; deliberately no API keys/order endpoint."""
from dataclasses import dataclass
import json
import time
from urllib.request import urlopen
from urllib.parse import urlencode
from .config import money


@dataclass(frozen=True)
class Quote:
    symbol: str
    bid: str
    ask: str
    observed_ms: int

    def validate(self,symbol,now):
        if self.symbol!=symbol or not 0<money(self.bid)<=money(self.ask):raise ValueError('Invalid quote identity or spread')
        if type(self.observed_ms) is not int or not 0<=now-self.observed_ms<=10000:raise ValueError('Quote is stale or from the future')


def fetch(symbol):
    # Binance public bookTicker has no exchange timestamp. observed_ms records
    # local receipt time; reject requests taking over five seconds.
    start=time.monotonic()
    with urlopen('https://api.binance.com/api/v3/ticker/bookTicker?'+urlencode({'symbol':symbol}),timeout=5) as response:
        packet=json.loads(response.read(65536))
    if time.monotonic()-start>5:raise ValueError('Quote request took too long')
    result=Quote(packet['symbol'],packet['bidPrice'],packet['askPrice'],int(time.time()*1000))
    result.validate(symbol,result.observed_ms)
    return result
