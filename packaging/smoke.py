"""Verify a frozen build retains the source installation's exact formula identity."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from Section_4_Features.execution.components import current_signature
executable=Path('dist/TradingIndicator')/('TradingIndicator.exe' if os.name=='nt' else 'TradingIndicator')
with tempfile.TemporaryDirectory() as directory:
    result=subprocess.run([str(executable.resolve()),'--data-dir',str(Path(directory)/'Portable memory'),'--self-test'],text=True,capture_output=True,check=True)
    packet=json.loads(result.stdout)
    assert packet['formula_signature']==current_signature(),'Packaging changed formula identity'
    assert packet['status']=='PASS'
    print(result.stdout)
