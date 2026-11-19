"""Loopback-only browser workspace for offline strategy research; no live writes."""

if __package__ in (None, ""):
    import sys as _sys
    from pathlib import Path as _Path
    _sys.path.insert(0, str(_Path(__file__).resolve().parents[2]))


from Section_1_Global_Core.paths import REPO_ROOT
import base64
from collections import OrderedDict
from datetime import datetime, timezone
import gzip
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
from pathlib import Path
import sqlite3
import threading
import time
from urllib.parse import parse_qs, urlparse
import uuid
import webbrowser

from Section_1_Global_Core.paths import data_path
from Section_8_Decision_Engine import strategy_analyzer as analyzer
from Section_8_Decision_Engine.pivot_candle_source import unpack
from Section_8_Decision_Engine.strategy_catalog import field_catalog

ROOT = REPO_ROOT
ASSETS = ROOT / 'Section_12_Research/ui' / 'strategy_analyzer'
REPORTS = ROOT / 'Section_12_Research/reports' / 'BTC_1h_sequences'
MAX_BODY = 100 * 1024 * 1024
MAX_JSON = 1024 * 1024 * 1024


def decode(data):
    if data[:2] == b'\x1f\x8b':
        with gzip.GzipFile(fileobj=io.BytesIO(data)) as stream:
            data = stream.read(MAX_JSON + 1)
    if len(data) > MAX_JSON:
        raise ValueError('Input expands beyond the 1 GiB workspace limit')
    return json.loads(data)


def read(path):
    return decode(path.read_bytes())


def write(path, value):
    data = json.dumps(value, separators=(',', ':'), allow_nan=False).encode()
    if path.suffix == '.gz':
        data = gzip.compress(data, mtime=0)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.partial')
    temporary.write_bytes(data)
    temporary.replace(path)




class Workspace:
    def __init__(self, directory=None, input_path=None):
        self.explicit_input=bool(input_path)
        self.directory = Path(directory) if directory else data_path('strategy_analyzer', Path.home() / '.tradingbot' / 'strategy_analyzer')
        self.directory.mkdir(parents=True, exist_ok=True)
        self.input_paths = {}
        for path in sorted(set(REPORTS.rglob('source*.json*')) | set(REPORTS.rglob('memory_source.json*')) | set((ROOT / 'Section_12_Research/reports' / 'pivot_discovery').glob('*_source.json.gz'))):
            if not path.name.endswith('.partial'):
                self.input_paths['input-' + hashlib.sha256(str(path).encode()).hexdigest()[:16]] = path
        if input_path:
            path = Path(input_path).resolve()
            self.input_paths['selected-input'] = path
        for path in (self.directory / 'inputs').glob('*.json.gz'):
            self.input_paths[path.stem.removesuffix('.json')] = path
        self.input_names = {}
        for key, path in self.input_paths.items():
            meta = path.with_name(path.name + '.meta.json')
            self.input_names[key] = read(meta).get('name', path.name) if meta.is_file() else str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else path.name
        preferred = ROOT / 'Section_12_Research/reports' / 'pivot_discovery' / 'BTCUSDT_15m_source.json.gz'
        self.default_input = 'selected-input' if input_path else next((key for key, path in self.input_paths.items() if path == preferred), next((key for key, path in self.input_paths.items() if path == REPORTS / 'source_v1.json.gz'), next(iter(self.input_paths), None)))
        self.cache = OrderedDict()
        self.lock = threading.Lock()
        self.discovery_lock = threading.Lock()
        self.discovery_cache = OrderedDict()
        self.memory_discovery = {}
        self.jobs = {}
        self.active_job = None

    def configurations(self):
        result = {}
        for path in sorted((REPORTS / 'strategy_configs').glob('*.json')) + sorted((self.directory / 'configs').glob('*.json')):
            config = analyzer.validate_config(read(path))
            result[analyzer.digest(config)] = config
        return [dict(key=key, config=value) for key, value in result.items()]

    def report_paths(self):
        result = {}
        published = REPORTS / 'strategy_analyzer' / 'strategy_analysis.json.gz'
        if published.exists():
            result['published'] = published
        for path in sorted((self.directory / 'runs').glob('*/strategy_analysis.json.gz')):
            result[path.parent.name] = path
        return result

    def catalog(self):
        reports = []
        for key, path in reversed(self.report_paths().items()):
            meta_path = path.parent / 'metadata.json'
            meta = read(meta_path) if meta_path.exists() else {}
            name = 'Published example' if key == 'published' else meta.get('name', key)
            reports.append(dict(id=key, name=name))
        from Section_8_Decision_Engine import strategy_memory
        try:memory=strategy_memory.universe()
        except (OSError,ValueError,RuntimeError,sqlite3.Error) as error:memory=dict(symbols=[],timeframes=[],pairs=[],error=str(error))
        memory_inputs=[dict(id=strategy_memory.key(p['symbol'],p['timeframe']),name=p['symbol']+' · '+p['timeframe']+' · Memory') for p in memory['pairs']]
        preferred='memory:BTCUSDT:15m'
        default=preferred if not self.explicit_input and any(i['id']==preferred for i in memory_inputs) else self.default_input
        return dict(kind='pivot-strategy-workspace-v1', default_input=default, memory=memory,
                    inputs=memory_inputs+[dict(id=key, name=self.input_names[key]) for key in self.input_paths],
                    configurations=self.configurations(),
                    reports=reports)

    def source(self, key):
        if key.startswith('memory:'):
            from Section_8_Decision_Engine import strategy_memory
            symbol,frame=strategy_memory.parse(key)
            requested=['feature.'+f for f in ('rsi','rsi_change','natr_pct','efficiency_ratio','relative_volume','volume_ratio','atr_ma_ratio','atr_change','candle_range_atr','displacement_atr','body_percent','close_location','ema50','ema200','ema50_slope_atr','ema200_slope_atr','bb_width_percentile','bb_width_change_fraction','positive_return_fraction','negative_return_fraction')]
            requested += [f'context.{frame}.{engine}.direction' for engine in ('REGIME','TREND')]
            source=strategy_memory.load(symbol,frame,fields=requested,include_pivots=True)
            return source,field_catalog(source)
        if key not in self.input_paths:
            raise ValueError('Unknown input selection')
        path = self.input_paths[key]
        signature = (str(path), path.stat().st_mtime_ns, path.stat().st_size)
        with self.lock:
            item = self.cache.get(signature)
        if item is None:
            source = unpack(read(path))
            item = (source, field_catalog(source))
            with self.lock:
                self.cache[signature] = item
                while len(self.cache) > 2:
                    self.cache.popitem(last=False)
        return item

    def discovery(self, key):
        from Section_8_Decision_Engine.pivot_discovery import Dataset
        if key.startswith('memory:') and key in self.memory_discovery:return self.memory_discovery[key]
        source, _ = self.source(key)
        signature = (key, source['source_id'], source['observed_as_of'])
        with self.discovery_lock:
            if signature not in self.discovery_cache:
                self.discovery_cache[signature] = Dataset(source)
                while len(self.discovery_cache) > 2:
                    self.discovery_cache.popitem(last=False)
            dataset=self.discovery_cache[signature]
            if key.startswith('memory:'):
                self.memory_discovery={key:dataset}
            return dataset

    def upload(self, body):
        try:
            raw = base64.b64decode(body['data'], validate=True)
        except (ValueError, KeyError, TypeError) as error:
            raise ValueError('Choose a JSON or gzip row-source file') from error
        source = decode(raw)
        metadata = field_catalog(source)
        key = 'uploaded-' + hashlib.sha256(raw).hexdigest()[:20]
        path = self.directory / 'inputs' / (key + '.json.gz')
        write(path, source)
        name = Path(str(body.get('name', 'Imported row source'))).name[:200]
        write(path.with_name(path.name + '.meta.json'), dict(name=name))
        self.input_paths[key] = path
        self.input_names[key] = name
        return dict(id=key, metadata=metadata)

    def save_config(self, body):
        config = analyzer.validate_config(body['config'])
        key = analyzer.digest(config)
        write(self.directory / 'configs' / (key + '.json'), config)
        return dict(key=key, config=config)

    def start(self, body):
        config = analyzer.validate_config(body['config'])
        baseline = analyzer.validate_config(body['baseline_config']) if body.get('baseline_config') else None
        if baseline:
            # Both rule sets are re-evaluated with the user's selected costs.
            baseline = dict(baseline, execution=analyzer.EXECUTION | config.get('execution', {}))
        memory_input=str(body.get('input_id','')).startswith('memory:')
        if memory_input:
            from Section_8_Decision_Engine import strategy_memory
            symbol,frame=strategy_memory.parse(body['input_id'])
            symbols=body.get('symbols',[symbol])
            if not isinstance(symbols,list) or not symbols or len(symbols)>500 or len(symbols)!=len(set(symbols)):
                raise ValueError('Choose one or more distinct stored coins')
            available=strategy_memory.universe()['symbols']
            if any(s not in available for s in symbols):raise ValueError('Choose coins available in memory')
        elif body.get('input_id') not in self.input_paths:
            raise ValueError('Choose an available input')
        since, until = body.get('since'), body.get('until')
        if any(value is not None and type(value) is not int for value in (since, until)) or since is not None and until is not None and since >= until:
            raise ValueError('Choose a valid replay date range')
        fields = body.get('report_fields', [])
        if not isinstance(fields, list) or len(fields) > 100 or any(not isinstance(field, str) for field in fields):
            raise ValueError('Select at most 100 report inputs')
        with self.lock:
            if self.active_job is not None:
                raise RuntimeError('A replay is already running; wait for it to complete')
            key = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex[:8]
            self.jobs[key] = dict(id=key, state='running', stage='Loading input', complete=0, total=0)
            self.active_job = key
        target=self.run_memory if memory_input else self.run
        args=(key,symbols,frame,config,baseline,since,until,fields) if memory_input else (key,body['input_id'],config,baseline,since,until,fields)
        thread = threading.Thread(target=target, args=args, daemon=True)
        thread.start()
        return dict(id=key)

    def run_memory(self,key,symbols,frame,config,baseline,since,until,fields):
        from Section_8_Decision_Engine import strategy_memory
        import gc
        try:
            market_cutoff=min(until,int(time.time()*1000)) if until is not None else int(time.time()*1000)
            requested=set(fields)
            lag=2
            for strategy in [config]+([baseline] if baseline else []):
                for branch in strategy['branches']:
                    requested.update(analyzer.expression_fields(branch['when']))
                    lag=max(lag,*(n for _,n in analyzer.expression_operands(branch['when'])))
            summaries=[]
            for index,symbol in enumerate(symbols):
                def progress(stage,counts=None):
                    with self.lock:self.jobs[key].update(stage=f'{symbol} ({index+1}/{len(symbols)}) · '+stage,coin=symbol,coin_index=index+1,coin_total=len(symbols),**(counts or {}))
                try:
                    source=strategy_memory.load(symbol,frame,fields=requested,since=since,until=market_cutoff,warmup=lag,
                                                progress=lambda counts:progress(counts['stage'],{k:v for k,v in counts.items() if k=='complete'}))
                    progress('Replaying stored memory',dict(complete=0,total=len(source['candles'])))
                    result=analyzer.analyze(source,config,since=since,until=until,report_fields=fields,progress=lambda counts:progress('Replaying strategy',counts))
                    if baseline:
                        original=analyzer.analyze(source,baseline,since=since,until=until,report_fields=fields)
                        result['comparison']=analyzer.compare(original,result)
                    report_id=key+'-'+symbol
                    result['workspace']=dict(input_id=strategy_memory.key(symbol,frame),input_name=symbol+' '+frame+' · stored memory',run_id=report_id)
                    result['memory']=source['memory']
                    directory=self.directory/'runs'/report_id
                    write(directory/'strategy_analysis.json.gz',result)
                    write(directory/'metadata.json',dict(name=config['id']+' · '+symbol+' '+frame+' · memory'))
                    from Section_12_Research.cli.analyze_btc_hour_strategy import visual
                    (directory/'strategy_analysis.html').write_text(visual(result),encoding='utf-8')
                    summaries.append(dict(symbol=symbol,timeframe=frame,state='complete',report_id=report_id,summary=result['summary'],candles=result['candles_scanned']))
                    del source,result
                    if baseline:del original
                    gc.collect()
                except Exception as error:
                    summaries.append(dict(symbol=symbol,timeframe=frame,state='failed',error=str(error)))
                with self.lock:self.jobs[key]['coins']=list(summaries)
            write(self.directory/'runs'/key/'batch_summary.json',dict(config=config,timeframe=frame,coins=summaries,market_cutoff=market_cutoff,capital_model='Each coin is replayed independently with its own starting capital; no combined portfolio return'))
            successful=[s for s in summaries if s['state']=='complete']
            with self.lock:self.jobs[key].update(state='complete' if successful else 'failed',stage='Complete' if successful else 'Replay failed',report_id=successful[0]['report_id'] if successful else None,error=None if successful else summaries[0]['error'])
        except Exception as error:
            with self.lock:self.jobs[key].update(state='failed',stage='Replay failed',error=str(error))
        finally:
            with self.lock:self.active_job=None

    def run(self, key, input_id, config, baseline, since, until, fields):
        def progress(stage, counts=None):
            with self.lock:
                self.jobs[key].update(stage=stage, **(counts or {}))
        try:
            source, _ = self.source(input_id)
            progress('Replaying strategy', dict(complete=0, total=len(source['candles'])))
            result = analyzer.analyze(source, config, since=since, until=until, report_fields=fields,
                                      progress=lambda counts: progress('Replaying strategy', counts))
            if baseline:
                progress('Replaying baseline', dict(complete=0, total=len(source['candles'])))
                original = analyzer.analyze(source, baseline, since=since, until=until, report_fields=fields,
                                            progress=lambda counts: progress('Replaying baseline', counts))
                result['comparison'] = analyzer.compare(original, result)
            result['workspace'] = dict(input_id=input_id, input_name=self.input_names[input_id], run_id=key)
            progress('Saving report')
            directory = self.directory / 'runs' / key
            write(directory / 'strategy_analysis.json.gz', result)
            write(directory / 'metadata.json', dict(name=config['id'] + ' · ' + self.input_names[input_id] + ' · ' + datetime.now(timezone.utc).strftime('%d %b %Y %H:%M UTC')))
            from Section_12_Research.cli.analyze_btc_hour_strategy import visual
            (directory / 'strategy_analysis.html').write_text(visual(result), encoding='utf-8')
            with self.lock:
                self.jobs[key].update(state='complete', stage='Complete', report_id=key)
        except Exception as error:
            with self.lock:
                self.jobs[key].update(state='failed', stage='Replay failed', error=str(error))
        finally:
            with self.lock:
                self.active_job = None


def make_server(workspace, port=8765):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def send(self, status, data, content_type='application/json; charset=utf-8', attachment=None):
            if not isinstance(data, bytes):
                data = json.dumps(data, allow_nan=False).encode()
            self.send_response(status)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(data)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            if attachment:
                self.send_header('Content-Disposition', f'attachment; filename="{attachment}"')
            self.end_headers()
            try:
                self.wfile.write(data)
            except (BrokenPipeError, ConnectionResetError):
                pass

        def valid_host(self):
            return self.headers.get('Host') in (f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}')

        def do_GET(self):
            if not self.valid_host():
                return self.send(403, dict(error='Invalid Host'))
            parsed = urlparse(self.path)
            qs = parse_qs(parsed.query)
            try:
                if parsed.path == '/assets/lightweight-charts.js':
                    return self.send(200, (ROOT / 'packaging' / 'vendor' / 'lightweight-charts.js').read_bytes(), 'text/javascript; charset=utf-8')
                if parsed.path in ('/', '/assets/style.css', '/assets/builder.js', '/assets/report.js', '/assets/pivot.js'):
                    path = ASSETS / ('index.html' if parsed.path == '/' else parsed.path.rsplit('/', 1)[1])
                    kind = 'text/html' if path.suffix == '.html' else 'text/css' if path.suffix == '.css' else 'text/javascript'
                    return self.send(200, path.read_bytes(), kind + '; charset=utf-8')
                if parsed.path == '/api/catalog':
                    return self.send(200, workspace.catalog())
                if parsed.path == '/api/input':
                    if qs.get('id',[''])[0].startswith('memory:'):
                        from Section_8_Decision_Engine import strategy_memory
                        workspace.memory_discovery.pop(qs['id'][0],None)
                        return self.send(200,strategy_memory.metadata(*strategy_memory.parse(qs['id'][0])))
                    return self.send(200, workspace.source(qs.get('id', [''])[0])[1])
                if parsed.path in ('/api/discovery', '/api/chart'):
                    if parsed.path=='/api/chart' and qs.get('id',[''])[0].startswith('memory:'):
                        from Section_8_Decision_Engine import strategy_memory
                        from Section_8_Decision_Engine.pivot_discovery import Dataset
                        symbol,frame=strategy_memory.parse(qs['id'][0]);center=int(qs['center'][0]) if 'center' in qs else None
                        source=strategy_memory.load(symbol,frame,limit=260,center=center,all_fields=True,all_context=True,include_pivots=True)
                        packet=Dataset(source).chart(center=center,feature=qs.get('feature',['rsi'])[0])
                        packet.update(first=source['memory']['first'],last=source['memory']['last'])
                        return self.send(200,packet)
                    dataset = workspace.discovery(qs.get('id', [''])[0])
                    if parsed.path == '/api/chart':
                        return self.send(200, dataset.chart(center=int(qs['center'][0]) if 'center' in qs else None,
                                                            feature=qs.get('feature', ['rsi'])[0]))
                    return self.send(200, dataset.compare(side=qs.get('side', ['BUY'])[0],
                                                          control=qs.get('control', ['ordinary'])[0],
                                                          regime=qs.get('regime', ['ALL'])[0], trend=qs.get('trend', ['ALL'])[0],
                                                          offset=int(qs.get('offset', ['0'])[0]), page=int(qs.get('page', ['0'])[0]),
                                                          since=int(qs['since'][0]) if 'since' in qs else None,
                                                          until=int(qs['until'][0]) if 'until' in qs else None))
                if parsed.path == '/api/job':
                    with workspace.lock:
                        job = dict(workspace.jobs.get(qs.get('id', [''])[0], {}))
                    return self.send(200 if job else 404, job or dict(error='Unknown replay'))
                if parsed.path in ('/api/report', '/api/download'):
                    path = workspace.report_paths().get(qs.get('id', [''])[0])
                    if path is None:
                        raise ValueError('Unknown report')
                    if parsed.path == '/api/report':
                        return self.send(200, read(path))
                    if qs.get('format', ['json'])[0] == 'html':
                        from Section_12_Research.cli.analyze_btc_hour_strategy import visual
                        return self.send(200, visual(read(path)).encode(), 'text/html; charset=utf-8', 'strategy_analysis.html')
                    return self.send(200, path.read_bytes(), 'application/gzip', 'strategy_analysis.json.gz')
                return self.send(404, dict(error='Not found'))
            except (ValueError, KeyError, TypeError, OSError, sqlite3.Error, RuntimeError) as error:
                return self.send(400, dict(error=str(error)))

        def do_POST(self):
            if not self.valid_host():
                return self.send(403, dict(error='Invalid Host'))
            origin = self.headers.get('Origin')
            if origin and origin not in (f'http://127.0.0.1:{self.server.server_port}', f'http://localhost:{self.server.server_port}'):
                return self.send(403, dict(error='Cross-origin requests are not permitted'))
            if self.headers.get_content_type() != 'application/json':
                return self.send(415, dict(error='Expected JSON request'))
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= MAX_BODY:
                    raise ValueError('Upload exceeds the 100 MiB request limit')
                body = json.loads(self.rfile.read(length))
                if self.path == '/api/upload':
                    return self.send(200, workspace.upload(body))
                if self.path == '/api/config':
                    return self.send(200, workspace.save_config(body))
                if self.path == '/api/run':
                    return self.send(202, workspace.start(body))
                return self.send(404, dict(error='Not found'))
            except RuntimeError as error:
                return self.send(409, dict(error=str(error)))
            except (ValueError, KeyError, TypeError, OSError, sqlite3.Error) as error:
                return self.send(400, dict(error=str(error)))

    return ThreadingHTTPServer(('127.0.0.1', port), Handler)


def serve(*, directory=None, input_path=None, port=8765, open_browser=True):
    workspace = Workspace(directory, input_path)
    server = make_server(workspace, port)
    url = f'http://127.0.0.1:{server.server_port}/'
    print('Strategy analyzer workspace:', url, flush=True)
    print('Research files:', workspace.directory, flush=True)
    if open_browser:
        threading.Timer(.3, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
