"""Start the existing local strategy research workspace on demand."""
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


def ensure_running():
    global _server
    with _lock:
        if _server is not None or _running_workspace():
            return URL
        module = ("Section_12_Research.cli.strategy_analyzer_workspace"
                  if (_ROOT / "Section_12_Research/cli/strategy_analyzer_workspace.py").is_file()
                  else "strategy_analyzer_workspace")
        workspace = import_module(module)
        _server = workspace.make_server(workspace.Workspace(), port=PORT)
        Thread(target=_server.serve_forever, name="strategy-workspace", daemon=True).start()
        return URL
