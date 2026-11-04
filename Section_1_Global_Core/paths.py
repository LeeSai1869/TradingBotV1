"""Portable profile paths, opt-in; existing source installations keep their paths."""
import os
from pathlib import Path


def data_path(relative,legacy):
    root=os.environ.get('TRADINGBOT_DATA_DIR')
    return Path(root).expanduser().resolve()/relative if root else Path(legacy)
