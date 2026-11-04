"""Preserve executable bits and bundle symlinks when uploading CI artifacts."""
from pathlib import Path
import platform
import sys
import tarfile
root=Path('dist');app=root/'TradingIndicator.app' if sys.platform=='darwin' else root/'TradingIndicator'
archive=root/('TradingIndicator-'+sys.platform+'-'+platform.machine()+'.tar.gz')
with tarfile.open(archive,'w:gz') as output:
    output.add(app,arcname=app.name)
    output.add('STANDALONE_APP.md',arcname='README.md')
print(archive)
