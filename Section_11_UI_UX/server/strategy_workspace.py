"""Start the existing local strategy research workspace on demand."""
from errno import EADDRINUSE
from http.client import HTTPConnection, HTTPException
from importlib import import_module
from pathlib import Path
from threading import Lock, Thread

PORT = 8765
URL = f"http://127.0.0.1:{PORT}/"
_ROOT = Path(__file__).resolve().parents[2]
_lock = Lock()
_server = None


def _running_workspace():
    connection = HTTPConnection("127.0.0.1", PORT, timeout=1)
    try:
        connection.request("GET", "/")
        response = connection.getresponse()
        return response.status == 200 and b"<title>Strategy research workspace</title>" in response.read(8192)
    except (OSError, HTTPException):
        return False
    finally:
        connection.close()


class StartupError(RuntimeError):
    """A startup problem that can be shown in the local app."""


def ensure_running():
    global _server
    with _lock:
        if _server is not None:
            return f"http://127.0.0.1:{_server.server_port}/"
        if _running_workspace():
            return URL
        module = ("Section_12_Research.cli.strategy_analyzer_workspace"
                  if (_ROOT / "Section_12_Research/cli/strategy_analyzer_workspace.py").is_file()
                  else "strategy_analyzer_workspace")
        try:
            analyzer = import_module(module)
        except ModuleNotFoundError as error:
            if error.name == module:
                raise StartupError("Strategy Analyzer is missing from this checkout.") from error
            raise StartupError(f"Strategy Analyzer needs the Python module {error.name}.") from error
        if not (analyzer.ASSETS / "index.html").is_file():
            raise StartupError("Strategy Analyzer’s interface files are missing from this checkout.")
        workspace = analyzer.Workspace()
        try:
            server = analyzer.make_server(workspace, port=PORT)
        except OSError as error:
            if error.errno != EADDRINUSE:
                raise
            # The preferred port belongs to another service. Leave it alone.
            server = analyzer.make_server(workspace, port=0)
        Thread(target=server.serve_forever, name="strategy-workspace", daemon=True).start()
        _server = server
        return f"http://127.0.0.1:{server.server_port}/"
