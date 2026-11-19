"""Open the existing local pivot/strategy study, or start it if needed."""

if __package__ in (None, ""):
    import sys as _sys
    from pathlib import Path as _Path
    _sys.path.insert(0, str(_Path(__file__).resolve().parents[2]))


from Section_1_Global_Core.paths import REPO_ROOT
import argparse
import json
from pathlib import Path
import threading
from urllib.request import urlopen
import webbrowser

ROOT = REPO_ROOT


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--no-browser', action='store_true')
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error('Choose a port between 1 and 65535')
    url = f'http://127.0.0.1:{args.port}/'
    try:
        with urlopen(url + 'api/catalog', timeout=2) as response:
            running = json.load(response).get('kind') == 'pivot-strategy-workspace-v1'
    except (OSError, ValueError):
        running = False
    if running:
        print('Strategy study is already running:', url, flush=True)
        if not args.no_browser:
            webbrowser.open(url + '?input=default#pivot-title')
        return
    from Section_12_Research.cli.strategy_analyzer_workspace import serve
    try:
        if not args.no_browser:
            threading.Timer(.5, lambda: webbrowser.open(url + '?input=default#pivot-title')).start()
        serve(directory=ROOT / 'Section_12_Research/reports' / 'strategy_workspace', port=args.port,
              open_browser=False)
    except OSError as error:
        parser.exit(1, f'Could not start the study: {error}\nChoose another port with --port.\n')


if __name__ == '__main__':
    main()
