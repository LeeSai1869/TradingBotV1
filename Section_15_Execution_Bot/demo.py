"""Deterministic offline walkthrough. Uses only a disposable temporary ledger."""
from pathlib import Path
import tempfile
from .config import Config
from .engine import Ledger
from .quotes import Quote


def demonstrate():
    with tempfile.TemporaryDirectory(prefix='spot-paper-demo-') as folder:
        ledger=Ledger(Path(folder)/'demo.sqlite3')
        ledger.create(Config('demo','ENAUSDT','5m','demo-instance','100','110','2','4'),1000000)
        ledger.enabled('demo',True,1000000)
        turns=[]
        for now,price,side in ((1000001,'10','BUY'),(1005000,'10.6',None),(1010000,'10','BUY'),(1015000,'9.5',None)):
            feed=dict(epoch='demo',events=[dict(side=side,open_time=now-1,close_time=now-1)] if side else [])
            turns.append(ledger.step('demo',Quote('ENAUSDT',price,price,now),feed,now))
        return dict(mode='PAPER OFFLINE DEMO',network_requests=0,turns=turns,
                    final_account=ledger.report()[0],fills=ledger.history('demo'),temporary_ledger_deleted_on_return=True)
