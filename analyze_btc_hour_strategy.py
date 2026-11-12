"""Replay configurable BTC 1h AND/OR branches over every stored closed candle."""
import argparse
from datetime import datetime
import gzip
import json
from pathlib import Path
import sqlite3

from Section_1_Global_Core import btc_hour_sequence_source
from Section_8_Decision_Engine import strategy_analyzer as analyzer


def read(path):
    data = path.read_bytes()
    return json.loads(gzip.decompress(data) if path.suffix == '.gz' else data)


def save(path, value):
    data = (json.dumps(value, separators=(',', ':'), allow_nan=False) + '\n').encode()
    if path.suffix == '.gz':
        data = gzip.compress(data, mtime=0)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.partial')
    temporary.write_bytes(data)
    temporary.replace(path)


def timestamp(value):
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if parsed.tzinfo is None:
            raise ValueError('Include an explicit timezone, e.g. 2025-01-01T00:00:00Z')
        return int(parsed.timestamp() * 1000)
    except ValueError as error:
        raise argparse.ArgumentTypeError(str(error)) from error


def visual(report):
    """Self-contained configurable report, shared with the browser workspace."""
    assets = Path(__file__).resolve().parent / 'research_ui' / 'strategy_analyzer'
    data = json.dumps(report, separators=(',', ':'), allow_nan=False).replace('<', '\\u003c')
    css = (assets / 'style.css').read_text(encoding='utf-8')
    script = (assets / 'report.js').read_text(encoding='utf-8')
    return ('<!doctype html><html lang="en"><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width"><title>BTC 1h strategy report</title>'
            '<style>' + css + '</style><body class="standalone"><main id="report-area"></main>'
            '<script>' + script + '\nStrategyReport.mount(document.getElementById("report-area"),'
            + data + ');</script></body></html>')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    inputs = parser.add_mutually_exclusive_group()
    inputs.add_argument('--input', type=Path, help='Existing row source; defaults to BTC_1h_sequences/source_v1.json.gz')
    inputs.add_argument('--report', type=Path, help='Read-only fresh export from market memory using the existing frozen pivot-cohort report')
    parser.add_argument('--config', type=Path)
    parser.add_argument('--serve', action='store_true', help='Open the interactive strategy editor and report workspace')
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--workspace-dir', type=Path, help='Local research configuration/run storage for --serve')
    parser.add_argument('--no-browser', action='store_true', help='Start workspace without automatically opening a browser')
    baseline = parser.add_mutually_exclusive_group()
    baseline.add_argument('--baseline-config', type=Path, help='Replay this baseline on the exact same memory/window/costs')
    baseline.add_argument('--baseline', type=Path, help='Previously saved analyzer report with identical input contract')
    parser.add_argument('--since', type=timestamp, help='Inclusive candle knowledge-time boundary with timezone')
    parser.add_argument('--until', type=timestamp, help='Exclusive candle knowledge-time boundary with timezone')
    parser.add_argument('--output-dir', type=Path, default=Path('research_reports/BTC_1h_sequences/strategy_analyzer'))
    args = parser.parse_args()
    if args.serve:
        if args.report:
            parser.error('--serve accepts --input row exports; export current memory first with --report in batch mode')
        if args.config or args.baseline or args.baseline_config or args.since is not None or args.until is not None:
            parser.error('With --serve, choose the strategy, baseline and dates inside the browser; use Import strategy for a configuration file')
        if not 1 <= args.port <= 65535:
            parser.error('Choose a workspace port between 1 and 65535')
        from strategy_analyzer_workspace import serve
        try:
            serve(directory=args.workspace_dir, input_path=args.input, port=args.port, open_browser=not args.no_browser)
        except OSError as error:
            parser.exit(1, 'Could not start the research workspace: ' + str(error) + '\nUse --port to select another port if it is already in use.\n')
        return
    if not args.config:
        parser.error('Use --serve for the browser editor, or --config for a batch replay')
    try:
        config = analyzer.validate_config(read(args.config))
        baseline_config = analyzer.validate_config(read(args.baseline_config)) if args.baseline_config else None
        if args.report:
            source = btc_hour_sequence_source.export(read(args.report), include_all_features=True,
                                                     progress=lambda r: print(r, flush=True))
            save(args.output_dir / 'memory_source.json.gz', source)
        else:
            source = read(args.input or Path('research_reports/BTC_1h_sequences/source_v1.json.gz'))
        report = analyzer.analyze(source, config, since=args.since, until=args.until)
        if baseline_config:
            original = analyzer.analyze(source, baseline_config, since=args.since, until=args.until)
        else:
            original = read(args.baseline) if args.baseline else None
        if original:
            report['comparison'] = analyzer.compare(original, report)
        save(args.output_dir / 'strategy_analysis.json.gz', report)
        page = args.output_dir / 'strategy_analysis.html'
        page.write_text(visual(report), encoding='utf-8')
        print(json.dumps(dict(strategy=config['id'], summary=report['summary'],
                              accepted_signals=len(report['signals']),
                              comparison=report.get('comparison', {}).get('counts')), indent=2))
        print('Report:', args.output_dir / 'strategy_analysis.json.gz')
        print('Dashboard:', page)
    except (OSError, ValueError, KeyError, TypeError, sqlite3.Error) as error:
        parser.exit(1, str(error) + '\n')


if __name__ == '__main__':
    main()
