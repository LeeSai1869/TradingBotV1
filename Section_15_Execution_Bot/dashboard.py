"""Independent loopback-only paper dashboard. Never imports or changes chart UI."""
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import secrets
import sqlite3
import time
from urllib.parse import urlsplit, parse_qs
from .config import Config, money
from .engine import Ledger, Conflict
from . import source, quotes
from .diagnostics import diagnose

WEB=Path(__file__).with_name('web')
EDITABLE={'capital_cap','stop_loss_pct','take_profit_pct','fee_bps','slippage_bps','max_signal_age_seconds'}


class Dashboard:
    def __init__(self,path):self.ledger=Ledger(path)

    def state(self,name=None):
        result=self.ledger.view(name);now=int(time.time()*1000)
        for account in result['accounts']:
            cfg=Config(**account['config']);s=account['state'];bid=s.get('last_bid')
            age=(now-s['last_quote_ms'])/1000 if s.get('last_quote_ms') is not None else None
            estimate=None
            if money(s['quantity'])==0:estimate=money(s['cash'])
            elif bid is not None:
                estimate=money(s['cash'])+money(s['quantity'])*money(bid)*(1-money(cfg.slippage_bps)/10000)*(1-money(cfg.fee_bps)/10000)
            account.update(quote_age_seconds=round(age,1) if age is not None else None,
                quote_fresh=age is not None and 0<=age<=10,
                estimated_equity=str(estimate) if estimate is not None else None,
                unrealized_pnl=str(estimate-money(s['cash'])-money(s['cost'])) if estimate is not None else None,
                activity_age_seconds=round((now-max(s.get('last_quote_ms',0),s.get('last_error_ms',0)))/1000,1)
                    if s.get('last_quote_ms') or s.get('last_error_ms') else None)
        result.update(server_time_ms=now,mode='paper',intervals=['1m','3m','5m','15m','30m','1h','2h','4h','6h','8h','12h','1d','3d','1w','1M'])
        return result

    def action(self,data):
        action=data.get('action');now=int(time.time()*1000)
        if action=='create':
            raw=data.get('config')
            allowed={'name','symbol','interval','initial_capital',*EDITABLE}
            if not isinstance(raw,dict) or set(raw)-allowed:raise ValueError('Use the supported paper allocation fields')
            config=dict(raw);config.update(instance_id='current',strategy_source='current')
            if isinstance(config.get('symbol'),str):config['symbol']=config['symbol'].upper().strip()
            cfg=source.bind_current(Config(**config))
            source.snapshot(cfg,-1,armed_at=now)
            try:self.ledger.create(cfg,now)
            except sqlite3.IntegrityError:raise ValueError('An allocation with this name already exists; choose another name') from None
            return dict(ok=True,name=cfg.name,message='Paper allocation created paused')
        name=data.get('name')
        if not isinstance(name,str):raise ValueError('Choose an allocation')
        current=next((a for a in self.ledger.view()['accounts'] if a['name']==name),None)
        if current is None:raise ValueError('Unknown paper account')
        if action in ('enable','pause','configure'):
            token=data.get('expected_config')
            if not isinstance(token,str) or not token:raise ValueError('Refresh the allocation before changing it')
            if action=='configure':self.ledger.configure(name,data.get('changes'),now,expected_config=token)
            else:
                if action=='enable' and token!=current['config_token']:raise Conflict('Configuration changed; refresh the dashboard')
                if action=='enable' and not current['state']['enabled']:source.snapshot(Config(**current['config']),-1,armed_at=now)
                self.ledger.enabled(name,action=='enable',now,expected_config=token if action=='enable' else None)
        elif action=='close':
            token=data.get('expected_position')
            if not isinstance(token,str) or not token:raise ValueError('Refresh the position before closing it')
            if token!=current['position_token'] or money(current['state']['quantity'])<=0:raise Conflict('Position changed; refresh before closing it')
            # No network/ledger lock overlap. A late quote must still match the
            # position token inside the transaction, even if the worker traded.
            quote=quotes.fetch(current['config']['symbol'])
            self.ledger.close_position(name,quote,int(time.time()*1000),expected_position=token)
        else:raise ValueError('Unknown dashboard action')
        return dict(ok=True,name=name)


class Server(ThreadingHTTPServer):
    daemon_threads=True
    def __init__(self,path,port=8002):
        self.dashboard=Dashboard(path);self.csrf=secrets.token_urlsafe(32)
        super().__init__(('127.0.0.1',port),Handler)


class Handler(BaseHTTPRequestHandler):
    def setup(self):
        super().setup();self.connection.settimeout(10)
    def log_message(self,*args):pass
    def trusted(self):
        host=self.headers.get('Host','');port=self.server.server_port
        if host not in (f'127.0.0.1:{port}',f'localhost:{port}'):return False
        origin=self.headers.get('Origin')
        return origin is None or origin=='http://'+host

    def send(self,status,payload,kind='application/json; charset=utf-8'):
        raw=json.dumps(payload,allow_nan=False).encode() if kind.startswith('application/json') else payload
        self.send_response(status)
        for key,value in {'Content-Type':kind,'Content-Length':str(len(raw)),'Cache-Control':'no-store',
            'X-Content-Type-Options':'nosniff','Referrer-Policy':'no-referrer',
            'Content-Security-Policy':"default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"}.items():self.send_header(key,value)
        self.end_headers();self.wfile.write(raw)

    def do_GET(self):
        if not self.trusted():return self.send(403,{'error':'Use the local dashboard address'})
        request=urlsplit(self.path);query=parse_qs(request.query)
        try:
            if request.path=='/favicon.ico':return self.send(204,b'','image/x-icon')
            if request.path=='/api/state':return self.send(200,self.server.dashboard.state(query.get('name',[None])[0]))
            if request.path=='/api/diagnostics':return self.send(200,diagnose(self.server.dashboard.ledger.path,name=query.get('name',[None])[0]))
            static={'/':('index.html','text/html; charset=utf-8'),'/dashboard.js':('dashboard.js','text/javascript; charset=utf-8'),'/dashboard.css':('dashboard.css','text/css; charset=utf-8')}
            if request.path not in static:return self.send(404,{'error':'Not found'})
            filename,kind=static[request.path];body=(WEB/filename).read_bytes()
            if filename=='index.html':body=body.replace(b'__CSRF__',self.server.csrf.encode())
            return self.send(200,body,kind)
        except (ValueError,TypeError,KeyError) as error:self.send(400,{'error':str(error)})
        except (OSError,sqlite3.Error):self.send(503,{'error':'Ledger or strategy data is temporarily unavailable; retry shortly'})

    def do_POST(self):
        if not self.trusted() or not hmac.compare_digest(self.headers.get('X-Dashboard-Token','').encode(),self.server.csrf.encode()):
            return self.send(403,{'error':'Dashboard session expired or request origin rejected; reload the page'})
        if urlsplit(self.path).path!='/api/action':return self.send(404,{'error':'Not found'})
        try:
            if self.headers.get('Content-Type','').split(';')[0]!='application/json':raise ValueError('JSON request required')
            length=int(self.headers.get('Content-Length','0'))
            if not 0<length<=16384:raise ValueError('Request must be within 16 KiB')
            data=json.loads(self.rfile.read(length))
            if not isinstance(data,dict):raise ValueError('JSON object required')
            return self.send(200,self.server.dashboard.action(data))
        except Conflict as error:self.send(409,{'error':str(error)})
        except (ValueError,TypeError,KeyError,sqlite3.IntegrityError) as error:self.send(400,{'error':str(error)})
        except (OSError,sqlite3.Error):self.send(503,{'error':'Quote or ledger unavailable; no action completed. Refresh before retrying'})


def serve(path,port=8002):
    with Server(path,port) as server:
        print(f'Paper bot dashboard: http://127.0.0.1:{server.server_port}/',flush=True)
        print('Paper ledger: '+str(Path(path).expanduser().resolve()),flush=True)
        print('Dashboard only. Keep the paper worker running separately; chart and market runner are unchanged.',flush=True)
        try:server.serve_forever()
        except KeyboardInterrupt:pass
