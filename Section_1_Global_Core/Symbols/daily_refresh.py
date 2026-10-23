"""Daily proposer check, off the download thread; no automatic coin approval."""
import datetime
import json
import threading
import time
from pathlib import Path

STATE=Path(__file__).with_name('daily_refresh_state.json')
_lock=threading.Lock()
_worker=None
_next_attempt=0


def _run():
    global _next_attempt
    try:
        from . import symbol_proposer
        # Existing proposer also supports manual macOS notifications. A background
        # data refresh needs only registry updates, so suppress its UI notification.
        symbol_proposer.propose(notify=False)
        payload={'last_success':datetime.datetime.now(datetime.timezone.utc).isoformat()}
        temp=STATE.with_suffix('.tmp');temp.write_text(json.dumps(payload)+'\n');temp.replace(STATE)
        _next_attempt=time.time()+86400
        print('[symbols] daily top-50 refresh complete; new coins remain pending approval',flush=True)
    except Exception as error:
        _next_attempt=time.time()+3600
        print(f'[symbols] daily top-50 refresh failed; retry in one hour: {error}',flush=True)


def tick():
    global _worker,_next_attempt
    with _lock:
        if _worker is not None and _worker.is_alive():return
        if time.time()<_next_attempt:return
        try:
            last=datetime.datetime.fromisoformat(json.loads(STATE.read_text())['last_success']).timestamp()
            if time.time()<last+86400:
                _next_attempt=last+86400;return
        except (OSError,ValueError,KeyError,TypeError):pass
        _worker=threading.Thread(target=_run,name='daily-top50',daemon=True);_worker.start()
