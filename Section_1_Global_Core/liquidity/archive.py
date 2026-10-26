"""Bounded compressed raw archive owned exclusively by the liquidity recorder."""
from collections import OrderedDict
from datetime import datetime,timezone
import gzip
import json
from pathlib import Path
import time

class Archive:
    def __init__(self,root,*,budget=2*1024**3,max_handles=64,chunk_bytes=10*1024**2):
        self.root=Path(root);self.budget=budget;self.handles=OrderedDict();self.paths={}
        self.max_handles=max_handles;self.chunk_bytes=chunk_bytes;self.writes={}
    def append(self,symbol,record):
        stamp=datetime.fromtimestamp(record['received_ms']/1000,timezone.utc)
        key=(symbol,stamp.strftime('%Y-%m-%d/%H'))
        if key in self.handles and self.writes.get(key,0)%256==0:
            self.handles[key].flush()
            if self.paths[key].stat().st_size>=self.chunk_bytes:
                self.handles.pop(key).close();self.paths.pop(key,None)
        if key not in self.handles:
            for old in list(self.handles):
                if old[0]==symbol and old!=key:self.handles.pop(old).close()
            while len(self.handles)>=self.max_handles:
                _,handle=self.handles.popitem(last=False);handle.close()
            directory=self.root/'binance'/'usdt_perpetual'/symbol/stamp.strftime('%Y-%m-%d');directory.mkdir(parents=True,exist_ok=True)
            path=self.paths.get(key)
            if path is None or path.exists() and path.stat().st_size>=self.chunk_bytes:
                path=directory/f'{stamp:%H}-{time.time_ns()}.jsonl.gz';self.paths[key]=path
            self.handles[key]=gzip.open(path,'at',encoding='utf-8',compresslevel=3)
        self.handles.move_to_end(key);self.writes[key]=self.writes.get(key,0)+1
        self.handles[key].write(json.dumps(record,separators=(',',':'),allow_nan=False)+'\n')
    def flush(self):
        for handle in self.handles.values():handle.flush()
    def prune(self,now_ms):
        self.flush();active={Path(h.name) for h in self.handles.values()}
        files=sorted(self.root.glob('binance/usdt_perpetual/*/*/*.jsonl.gz'),key=lambda p:p.stat().st_mtime)
        total=sum(p.stat().st_size for p in files)
        for path in files:
            size=path.stat().st_size
            if path in active:continue
            if total<=self.budget and path.stat().st_mtime*1000>=now_ms-7*86400000:continue
            path.unlink();total-=size
        # Do not retain a path per hour forever.
        self.paths={key:path for key,path in self.paths.items() if key in self.handles}
        self.writes={key:value for key,value in self.writes.items() if key in self.handles}
    def close(self):
        error=None
        for handle in self.handles.values():
            try:handle.close()
            except OSError as failure:error=error or failure
        self.handles.clear()
        if error:raise error
