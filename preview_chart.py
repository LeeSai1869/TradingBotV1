"""Serve this checkout's chart using another checkout's existing local data."""
import argparse
from pathlib import Path
from urllib.parse import urlparse


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-from', type=Path, required=True,
                        help='project checkout containing the existing chart data')
    parser.add_argument('--port', type=int, default=8001)
    args = parser.parse_args()
    checkout = Path(__file__).resolve().parent
    source = args.data_from.expanduser().resolve()
    if not (source / 'Section_1_Global_Core').is_dir():
        parser.error('--data-from must point to an existing TradingBotV1 checkout')
    if not 1024 <= args.port <= 65535:
        parser.error('--port must be between 1024 and 65535')

    # Portable profiles already resolve independently of the code checkout.
    # Remap only source-installation paths originally inside this repository.
    from Section_1_Global_Core import paths
    resolve_data_path = paths.data_path

    def preview_data_path(relative, legacy):
        legacy = Path(legacy)
        if legacy.is_relative_to(checkout):
            legacy = source / legacy.relative_to(checkout)
        return resolve_data_path(relative, legacy)

    paths.data_path = preview_data_path
    from Section_11_UI_UX.server.ui_server import Handler, ThreadingHTTPServer

    class PreviewHandler(Handler):
        def do_POST(self):
            if urlparse(self.path).path in ('/api/login', '/api/logout'):
                return super().do_POST()
            self._json({'error': 'Changes to server settings are disabled in chart preview'}, 403)

    with ThreadingHTTPServer(('127.0.0.1', args.port), PreviewHandler) as server:
        print(f'Chart preview: http://127.0.0.1:{args.port}/', flush=True)
        print(f'Chart data: {source} (or the configured TRADINGBOT_DATA_DIR profile)', flush=True)
        print('This preview does not start any background workers. Press Ctrl+C to stop.', flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == '__main__':
    main()
