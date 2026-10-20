"""Shared runtime policy and cross-process coordination for runner/admin writes."""
from contextlib import contextmanager
import fcntl
import json
from pathlib import Path
import tempfile
import time

ROOT = Path(__file__).resolve().parent
POLICY_FILE = ROOT / 'runtime_policy.json'
LOCK_FILE = ROOT / '.data-policy.lock'
INTERVALS = ['1m','3m','5m','15m','30m','1h','2h','4h','6h','8h','12h','1d','3d','1w','1M']


@contextmanager
def locked(*, timeout=None):
    with LOCK_FILE.open('a') as stream:
        if timeout is None:
            fcntl.flock(stream, fcntl.LOCK_EX)
        else:
            deadline = time.monotonic() + timeout
            while True:
                try:
                    fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    if time.monotonic() >= deadline:
                        raise TimeoutError('Market data is busy. Retry shortly.')
                    time.sleep(min(.02, max(0, deadline-time.monotonic())))
        try:
            yield
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)


def read():
    if not POLICY_FILE.exists():
        return {'timeframes': {}, 'paused_coins': [], 'epochs': {}}
    return json.loads(POLICY_FILE.read_text())


def write(policy):
    with tempfile.NamedTemporaryFile(mode='w', dir=POLICY_FILE.parent, delete=False) as stream:
        json.dump(policy, stream, indent=2)
        temp = Path(stream.name)
    temp.replace(POLICY_FILE)


def enabled(symbol, interval):
    from .Symbols import symbols
    policy = read()
    return (interval in INTERVALS and policy['timeframes'].get(interval, 'active') == 'active'
            and symbol not in policy['paused_coins'] and symbols.is_active(symbol))


def active_symbols():
    from .Symbols import symbols
    paused = set(read()['paused_coins'])
    return [s for s in symbols.get_active_symbols() if s not in paused]


def active_intervals():
    policy = read()
    return [iv for iv in INTERVALS if policy['timeframes'].get(iv, 'active') == 'active']
