"""Configure this installation's HTTPS proxy origin independently of mobile push."""
import argparse
import os
from pathlib import Path


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--origin',required=True);parser.add_argument('--data-dir',type=Path)
    args=parser.parse_args()
    if args.data_dir:os.environ['TRADINGBOT_DATA_DIR']=str(args.data_dir.expanduser().resolve())
    from Section_11_UI_UX.server import public_access
    try:
        origin=public_access.save_origin(args.origin);path=public_access.CONFIG_FILE
        print('HTTPS access configured:',origin);print('Configuration:',path);print('No port was exposed and no mobile push was enabled. Restart the UI backend.')
    except (ValueError,OSError) as error:parser.exit(1,str(error)+'\n')

if __name__=='__main__':main()
