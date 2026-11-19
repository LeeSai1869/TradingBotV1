"""Check post-compaction health and remove only its verified original backup."""
import argparse
import subprocess
import sys
import json
import sqlite3
from contextlib import closing
from pathlib import Path
import compact_feature_storage as job


def remove_backup(path,*,apply=False):
    path=Path(path).resolve()
    report=json.loads(path.with_name(path.name+'.compaction.json').read_text())
    backup=path.with_name(path.name+'.before-compaction')
    if not report.get('complete') or report.get('stage')!='complete' or report.get('rows_copied',0)<=0 or report.get('rows_verified')!=report['rows_copied']:
        raise RuntimeError('Compaction verification is incomplete; backup retained')
    if report.get('verified_rowid')!=report.get('target_rowid'):
        raise RuntimeError('Verification cursor is incomplete; backup retained')
    current=job.identity(path)
    if any(current[key]!=report['new_source'][key] for key in ('path','device','inode')):
        raise RuntimeError('Active database identity differs; backup retained')
    if not backup.exists():print('Backup already absent; nothing deleted.');return
    if backup.is_symlink() or report['backup']!=str(backup):
        raise RuntimeError('Unexpected backup path; nothing deleted')
    original=job.identity(backup)
    if any(original[key]!=report['source'][key] for key in ('device','inode','size','mtime_ns')):
        raise RuntimeError('Backup differs from the verified original; nothing deleted')
    with closing(sqlite3.connect(path.as_uri()+'?mode=ro',uri=True,timeout=2)) as conn:
        if not conn.execute('SELECT 1 FROM features WHERE rowid>? AND formula_version=3 LIMIT 1',(report['target_rowid'],)).fetchone():
            raise RuntimeError('New writer output not confirmed; backup retained')
    job.assert_idle(backup)
    size=backup.stat().st_size
    if not apply:
        print(f'Checks passed. Eligible backup: {backup} ({size/1024**3:.2f} GiB). Use --apply to remove it.')
        return
    backup.unlink()
    print(f'Deleted only {backup.name} ({size/1024**3:.2f} GiB file). Active database and compaction report retained.')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply',action='store_true',help='Remove the verified backup after both reader checks pass')
    args=parser.parse_args()
    root=Path(__file__).resolve().parent
    for script in ('check_ema_distance_readers.py','check_atr_slope_readers.py'):
        try:subprocess.run([sys.executable,str(root/script)],check=True,cwd=root)
        except subprocess.CalledProcessError:parser.exit(1,'Reader check failed; backup retained.\n')
    try:remove_backup(job.features_store.DB_PATH,apply=args.apply)
    except (RuntimeError,OSError,ValueError,KeyError,sqlite3.Error) as error:
        parser.exit(1,str(error)+'\n')


if __name__=='__main__':main()
