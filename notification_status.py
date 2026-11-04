"""Read-only desktop/mobile setup and signal-delivery diagnostics; no test alerts sent."""
import argparse
import json
from pathlib import Path
import sqlite3
from Section_11_UI_UX.server.delivery_diagnostics import report


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path);args=parser.parse_args()
    try:packet=report()
    except (OSError,ValueError,sqlite3.Error):parser.exit(1,'Cannot read notification configuration/store; check local file access.\n')
    text=json.dumps(packet,indent=2,allow_nan=False)+'\n'
    if args.output:args.output.write_text(text)
    print(text,end='')

if __name__=='__main__':main()
