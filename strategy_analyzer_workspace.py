"""Loopback-only browser workspace for offline strategy research; no live writes."""
import base64
from collections import OrderedDict
from datetime import datetime, timezone
import gzip
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
from pathlib import Path
import threading
from urllib.parse import parse_qs, urlparse
import uuid
import webbrowser

from Section_1_Global_Core.paths import data_path
from Section_8_Decision_Engine import strategy_analyzer as analyzer

ROOT = Path(__file__).resolve().parent
ASSETS = ROOT / 'research_ui' / 'strategy_analyzer'
REPORTS = ROOT / 'research_reports' / 'BTC_1h_sequences'
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


def field_catalog(source):
    rows = source.get('candles', [])
    if (source.get('version') != 'btc-hour-sequence-source-v1' or source.get('symbol') != 'BTCUSDT'
            or source.get('timeframe') != '1h' or not rows):
        raise ValueError('Choose a nonempty BTCUSDT 1h row-source export, not an analysis or pivot report')
    sample = rows if len(rows) <= 2000 else rows[:1000] + rows[-1000:]
    fields = []

    def add(name, values, **extra):
        good = [v for v in values if (type(v) in (str, bool) or analyzer.number(v)) and v not in ('UNKNOWN', 'UNAVAILABLE')]
        kind = 'number' if good and all(analyzer.number(v) for v in good) else 'boolean' if good and all(type(v) is bool for v in good) else 'string'
        options = list(dict.fromkeys(v for v in good if isinstance(v, (str, bool)) and len(str(v)) <= 80))
        fields.append(dict(id=name, kind=kind, options=options[:30], sample_present=len(good), sample_total=len(values), **extra))

    names = sorted(set(source.get('exported_feature_columns', [])) | {key for row in rows for key in row.get('features', {})})
    for name in names:
        add('feature.' + name, [r['features'].get(name) for r in sample if r.get('feature_valid') and not r['features'].get('measurement_gap')], group='Stored features')
    for name in ('open', 'high', 'low', 'close', 'volume'):
        add('price.' + name, [r.get(name) for r in sample], group='Candle prices')
    for name in sorted(analyzer.DI_FIELDS):
        add('di.' + name, ['PLUS', 'MINUS', 'BALANCED'] if name == 'dominant' else [0.], group='DI measurements')
    for name in sorted(analyzer.EVENT_FIELDS):
        add('event.' + name, [True, False], group='DI events')
    histories = source.get('engine_history', {})
    for frame in ('1h', '4h', '1d'):
        for engine in ('REGIME', 'TREND', 'STRUCTURE', 'MOMENTUM', 'VOLATILITY', 'PARTICIPATION', 'PHASE', 'LIQUIDITY', 'SENTIMENT', 'BIAS'):
            history = histories.get(frame + ':' + engine, {})
            results = list(history.get('results', {}).values())
            values = {}
            for payload in results[:100] + results[-100:]:
                def walk(value, prefix=''):
                    for key, item in value.items():
                        name = prefix + key
                        if isinstance(item, dict):
                            walk(item, name + '.')
                        elif item is None or type(item) in (str, bool) or analyzer.number(item):
                            values.setdefault(name, []).append(item)
                walk(payload.get('classification') or {})
            for name in ({'primary', 'direction'} if engine == 'REGIME' else {'direction', 'strength_band'} if engine == 'TREND' else set()):
                values.setdefault(name, [])
            for name, samples in sorted(values.items()):
                add(f'context.{frame}.{engine}.{name}', samples, group=frame + ' ' + engine.title(), history_rows=len(history.get('results', {})))
    return dict(symbol='BTCUSDT', timeframe='1h', candles=len(rows), source_id=source['source_id'],
                first=rows[0]['open_time'], last=rows[-1]['close_time'] + 1, fields=fields,
                feature_columns=len(names), context_rows={key: len(value.get('results', {})) for key, value in histories.items()},
                note='Field choices come from this input. Sample availability uses up to 2,000 candles; replay diagnostics give exact unknown counts. Context is exact last-closed historical context, not today’s classification.')


class Workspace:
    def __init__(self, directory=None, input_path=None):
        self.directory = Path(directory) if directory else data_path('strategy_analyzer', Path.home() / '.tradingbot' / 'strategy_analyzer')
        self.directory.mkdir(parents=True, exist_ok=True)
        self.input_paths = {}
        for path in sorted(set(REPORTS.rglob('source*.json*')) | set(REPORTS.rglob('memory_source.json*'))):
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
        self.default_input = 'selected-input' if input_path else next((key for key, path in self.input_paths.items() if path == REPORTS / 'source_v1.json.gz'), next(iter(self.input_paths), None))
        self.cache = OrderedDict()
        self.lock = threading.Lock()
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
        return dict(default_input=self.default_input,
                    inputs=[dict(id=key, name=self.input_names[key]) for key in self.input_paths],
                    configurations=self.configurations(),
                    reports=reports)

    def source(self, key):
        if key not in self.input_paths:
            raise ValueError('Unknown input selection')
        path = self.input_paths[key]
        signature = (str(path), path.stat().st_mtime_ns, path.stat().st_size)
        with self.lock:
            item = self.cache.get(signature)
        if item is None:
            source = read(path)
            item = (source, field_catalog(source))
            with self.lock:
                self.cache[signature] = item
                while len(self.cache) > 2:
                    self.cache.popitem(last=False)
        return item

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
        if body.get('input_id') not in self.input_paths:
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
        thread = threading.Thread(target=self.run, args=(key, body['input_id'], config, baseline, since, until, fields), daemon=True)
        thread.start()
        return dict(id=key)

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
            from analyze_btc_hour_strategy import visual
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
                if parsed.path in ('/', '/assets/style.css', '/assets/builder.js', '/assets/report.js'):
                    path = ASSETS / ('index.html' if parsed.path == '/' else parsed.path.rsplit('/', 1)[1])
                    kind = 'text/html' if path.suffix == '.html' else 'text/css' if path.suffix == '.css' else 'text/javascript'
                    return self.send(200, path.read_bytes(), kind + '; charset=utf-8')
                if parsed.path == '/api/catalog':
                    return self.send(200, workspace.catalog())
                if parsed.path == '/api/input':
                    return self.send(200, workspace.source(qs.get('id', [''])[0])[1])
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
                        from analyze_btc_hour_strategy import visual
                        return self.send(200, visual(read(path)).encode(), 'text/html; charset=utf-8', 'strategy_analysis.html')
                    return self.send(200, path.read_bytes(), 'application/gzip', 'strategy_analysis.json.gz')
                return self.send(404, dict(error='Not found'))
            except (ValueError, KeyError, TypeError, OSError) as error:
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
            except (ValueError, KeyError, TypeError, OSError) as error:
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
