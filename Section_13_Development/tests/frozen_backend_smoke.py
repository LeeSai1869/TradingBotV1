"""Exercise actual frozen HTTP backend and locally bundled chart asset, no exchanges."""
from pathlib import Path
import subprocess
import tempfile
import time
from urllib.request import urlopen
import json

executable=Path('dist/TradingIndicator/TradingIndicator').resolve()
with tempfile.TemporaryDirectory() as directory:
    child=subprocess.Popen([str(executable),'--data-dir',directory,'--worker','backend'],stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    try:
        for _ in range(100):
            if child.poll() is not None:raise AssertionError(child.stdout.read().decode())
            try:
                with urlopen('http://127.0.0.1:8000/api/session',timeout=.3) as response:json.load(response)
                break
            except OSError:time.sleep(.1)
        else:raise AssertionError('Frozen backend did not start')
        with urlopen('http://127.0.0.1:8000/',timeout=2) as response:html=response.read().decode()
        assert '/web_root/vendor/lightweight-charts.js' in html
        with urlopen('http://127.0.0.1:8000/web_root/vendor/lightweight-charts.js',timeout=2) as response:assert b'TradingView' in response.read()
        assert (Path(directory)/'accounts').is_dir()
        print('PASS frozen backend HTTP session, isolated memory and local chart library')
    finally:
        child.terminate()
        try:child.wait(timeout=10)
        except subprocess.TimeoutExpired:child.kill();child.wait()
        child.stdout.close()
