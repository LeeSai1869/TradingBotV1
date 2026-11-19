"""Offline, resumable feature-file compaction. Default is a read-only preflight.

Retains all columns, legacy values, rowids, auxiliary tables and checkpoints.
No indicator replay. Keeps a hard-linked original after a fully verified swap.
"""

if __package__ in (None, ""):
    import sys as _sys
    from pathlib import Path as _Path
    _sys.path.insert(0, str(_Path(__file__).resolve().parents[2]))


from Section_1_Global_Core.paths import REPO_ROOT
import argparse
from contextlib import closing,contextmanager,nullcontext
import json
import os
import plistlib
from pathlib import Path
import shutil
import sqlite3
import stat
import subprocess
import sys
import time
from Section_1_Global_Core import data_policy
from Section_1_Global_Core.memory_storage.Storage import features_store

WORK='__feature_compaction_work'


def q(name):return '"'+name.replace('"','""')+'"'


def identity(path):
    s=path.stat()
    return dict(path=str(path.resolve()),device=s.st_dev,inode=s.st_ino,size=s.st_size,mtime_ns=s.st_mtime_ns)


def assert_idle(path):
    try:r=subprocess.run(['lsof','-t','--',str(path)],capture_output=True,text=True,timeout=10)
    except (OSError,subprocess.TimeoutExpired) as error:raise RuntimeError('Cannot prove database is idle with lsof') from error
    if r.returncode not in (0,1):raise RuntimeError('lsof failed: '+r.stderr[:300])
    others=[int(pid) for pid in r.stdout.split() if pid.isdecimal() and int(pid)!=os.getpid()]
    if others:raise RuntimeError(f'Database is still open by PIDs {others}; stop chart/runner services before compaction')


def write_report(path,state):
    temporary=path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(json.dumps(state,indent=2));temporary.replace(path)


def preflight(path):
    source=identity(path)
    target=path.with_name(path.name+'.compact-building')
    return dict(source=source,target=str(target),backup=str(path)+'.before-compaction',
        free_GiB=round(shutil.disk_usage(path.parent).free/1024**3,2),
        source_GiB=round(source['size']/1024**3,2),partial_GiB=round(target.stat().st_size/1024**3,2) if target.exists() else 0,
        mode='check',columns_removed=0,indicator_replay=False)


def compact(path,*,batch=10000,report=None):
    path=Path(path).resolve();target=path.with_name(path.name+'.compact-building')
    backup=path.with_name(path.name+'.before-compaction')
    report=Path(report) if report else path.with_name(path.name+'.compaction.json')
    if backup.exists():raise RuntimeError('Original backup already exists; refusing to overwrite it: '+str(backup))
    assert_idle(path)
    for suffix in ('-wal','-journal'):
        side=Path(str(path)+suffix)
        if side.exists() and side.stat().st_size:raise RuntimeError('Live/recovery journal exists; close and checkpoint the source safely first')
    if target.exists():assert_idle(target)
    source_id=identity(path)
    required=max(0,int(source_id['size']*1.1)-(target.stat().st_size if target.exists() else 0))+2*1024**3
    if shutil.disk_usage(path.parent).free<required:raise RuntimeError('Insufficient free space for a separate compacted file plus reserve')
    with data_policy.locked(timeout=1),data_policy.snapshot_guard(exclusive=True,timeout=1):
        assert_idle(path)
        with closing(sqlite3.connect(path.as_uri()+'?mode=ro',uri=True,timeout=2)) as source:
            if source.execute('PRAGMA journal_mode').fetchone()[0].lower()=='wal':
                raise RuntimeError('WAL mode requires an offline checkpoint and switch to DELETE mode before this compaction')
            objects=source.execute("SELECT type,name,sql FROM sqlite_master WHERE sql IS NOT NULL AND name NOT LIKE 'sqlite_%' ORDER BY type,name").fetchall()
            tables=[(name,sql) for kind,name,sql in objects if kind=='table']
            if any(name==WORK or 'CREATE VIRTUAL TABLE' in sql.upper() for name,sql in tables):raise RuntimeError('Unsupported virtual/reserved table in source')
            if not any(name=='features' for name,_ in tables):raise RuntimeError('Missing features table')
            state=dict(source=source_id,stage='copy',last_rowid=0,rows_copied=0,verified_rowid=0,rows_verified=0,
                target_rowid=source.execute('SELECT max(rowid) FROM features').fetchone()[0] or 0,complete=False)
            if not target.exists() or not target.stat().st_size:write_report(report,state)
            with closing(sqlite3.connect(target.as_uri()+'?mode=rwc',uri=True,timeout=2)) as out:
                out.execute('PRAGMA cache_size=-32768');out.execute('PRAGMA synchronous=FULL')
                out.execute('ATTACH DATABASE ? AS old',(path.as_uri()+'?mode=ro',))
                exists=out.execute('SELECT 1 FROM sqlite_master WHERE name=?',(WORK,)).fetchone()
                if exists:
                    state=json.loads(out.execute('SELECT state FROM '+q(WORK)).fetchone()[0])
                elif target.stat().st_size and out.execute("SELECT 1 FROM sqlite_master WHERE name='features'").fetchone():
                    # Recover a crash after removing the private progress table.
                    state=json.loads(report.read_text())
                    if state.get('stage') not in ('verified','no_savings'):raise RuntimeError('Unrecognized partial compacted file')
                    state.update(stage='copy',verified_rowid=0,rows_verified=0)
                    with out:
                        out.execute('CREATE TABLE '+q(WORK)+' (state TEXT NOT NULL)')
                        out.execute('INSERT INTO '+q(WORK)+' VALUES (?)',(json.dumps(state),))
                else:
                    encoding=source.execute('PRAGMA encoding').fetchone()[0]
                    out.execute('PRAGMA encoding='+q(encoding))
                    with out:
                        for name,sql in tables:out.execute(sql)
                        out.execute('CREATE TABLE '+q(WORK)+' (state TEXT NOT NULL)')
                        out.execute('INSERT INTO '+q(WORK)+' VALUES (?)',(json.dumps(state),))
                if state['source']!=source_id:raise RuntimeError('Source changed; refusing stale compaction progress')
                # Reverify committed target data on every invocation, including
                # portions checked by an interrupted earlier run.
                state.update(verified_rowid=0,rows_verified=0)
                def save():out.execute('UPDATE '+q(WORK)+' SET state=?',(json.dumps(state),))
                def columns(name):return [r[1] for r in source.execute('PRAGMA table_xinfo('+q(name)+')') if r[6]==0]
                names=columns('features');projection=','.join(q(c) for c in names)
                printed=time.monotonic()
                while state['last_rowid']<state['target_rowid']:
                    ids=out.execute('SELECT rowid FROM old.features WHERE rowid>? AND rowid<=? ORDER BY rowid LIMIT ?',
                        (state['last_rowid'],state['target_rowid'],batch)).fetchall()
                    end=ids[-1][0] if ids else state['target_rowid']
                    with out:
                        out.execute('INSERT INTO main.features(rowid,'+projection+') SELECT rowid,'+projection+
                            ' FROM old.features WHERE rowid>? AND rowid<=?',(state['last_rowid'],end))
                        state['rows_copied']+=len(ids);state['last_rowid']=end;save()
                    if time.monotonic()-printed>=15:
                        write_report(report,state);print(json.dumps(state),flush=True);printed=time.monotonic()
                # Metadata is copied exactly; trigger/index definitions follow data.
                with out:
                    for kind,name,sql in objects:
                        if kind=='trigger':out.execute('DROP TRIGGER IF EXISTS main.'+q(name))
                    for name,sql in tables:
                        if name=='features':continue
                        cols=columns(name);rowid=[] if 'WITHOUT ROWID' in sql.upper() else ['rowid']
                        selection=','.join(q(c) for c in rowid+cols)
                        out.execute('DELETE FROM main.'+q(name))
                        out.execute('INSERT INTO main.'+q(name)+'('+selection+') SELECT '+selection+' FROM old.'+q(name))
                    sequence=source.execute("SELECT 1 FROM sqlite_master WHERE name='sqlite_sequence'").fetchone()
                    if sequence:
                        out.execute('DELETE FROM main.sqlite_sequence')
                        out.execute('INSERT INTO main.sqlite_sequence SELECT * FROM old.sqlite_sequence')
                    for kind,name,sql in objects:
                        if kind!='table' and not out.execute('SELECT 1 FROM main.sqlite_master WHERE name=?',(name,)).fetchone():out.execute(sql)
                    for pragma in ('user_version','application_id'):
                        value=source.execute('PRAGMA '+pragma).fetchone()[0];out.execute(f'PRAGMA main.{pragma}={value}')
                    state['stage']='verify';save()
                for name,sql in tables:
                    if name=='features':continue
                    cols=columns(name);selection=','.join(q(c) for c in ([] if 'WITHOUT ROWID' in sql.upper() else ['rowid'])+cols)
                    for left,right in (('main','old'),('old','main')):
                        mismatch=out.execute('SELECT '+selection+' FROM '+left+'.'+q(name)+' EXCEPT SELECT '+selection+' FROM '+right+'.'+q(name)+' LIMIT 1').fetchone()
                        if mismatch:raise RuntimeError('Auxiliary/checkpoint mismatch: '+name)
                counts=[out.execute('SELECT count(*) FROM '+schema+'.features').fetchone()[0] for schema in ('main','old')]
                if counts[0]!=counts[1]:raise RuntimeError('Feature row count mismatch')
                mismatch=' OR '.join('n.'+q(c)+' IS NOT o.'+q(c) for c in names)
                while state['verified_rowid']<state['target_rowid']:
                    ids=out.execute('SELECT rowid FROM old.features WHERE rowid>? AND rowid<=? ORDER BY rowid LIMIT ?',
                        (state['verified_rowid'],state['target_rowid'],batch)).fetchall()
                    end=ids[-1][0] if ids else state['target_rowid']
                    bad=out.execute('SELECT o.rowid FROM old.features o LEFT JOIN main.features n ON n.rowid=o.rowid '
                        'WHERE o.rowid>? AND o.rowid<=? AND (n.rowid IS NULL OR '+mismatch+') LIMIT 1',
                        (state['verified_rowid'],end)).fetchone()
                    if bad:raise RuntimeError('Feature value/rowid mismatch: '+str(bad[0]))
                    with out:
                        state['rows_verified']+=len(ids);state['verified_rowid']=end;save()
                    if time.monotonic()-printed>=15:
                        write_report(report,state);print(json.dumps(state),flush=True);printed=time.monotonic()
                schema=out.execute("SELECT type,name,sql FROM sqlite_master WHERE sql IS NOT NULL AND name NOT LIKE 'sqlite_%' AND name<>? ORDER BY type,name",(WORK,)).fetchall()
                if schema!=objects:raise RuntimeError('Schema objects differ from source')
                print(json.dumps(dict(stage='quick_check',rows_verified=state['rows_verified'])),flush=True)
                if out.execute('PRAGMA main.quick_check').fetchall()!=[('ok',)]:raise RuntimeError('Compacted database failed quick_check')
                if identity(path)!=source_id:raise RuntimeError('Source changed during compaction')
                state['stage']='verified';write_report(report,state)
                with out:out.execute('DROP TABLE '+q(WORK))
                out.execute('DETACH DATABASE old')
        assert_idle(path)
        if identity(path)!=source_id:raise RuntimeError('Source changed before switch')
        os.chmod(target,stat.S_IMODE(path.stat().st_mode))
        with target.open('rb') as stream:os.fsync(stream.fileno())
        if target.stat().st_size>=source_id['size']:
            state.update(stage='no_savings',complete=False,saved_GiB=0)
            write_report(report,state);print(json.dumps(state),flush=True)
            print('Verified copy is not smaller. Original database left unchanged.',flush=True)
            return state
        os.link(path,backup)
        try:os.replace(target,path)
        except BaseException:
            backup.unlink();raise
        state.update(complete=True,stage='complete',new_source=identity(path),backup=str(backup),
            saved_GiB=round((source_id['size']-path.stat().st_size)/1024**3,3),finished_at=time.time())
        write_report(report,state);print(json.dumps(state),flush=True)
        return state


def service_belongs_to_checkout(config,label,module,root):
    root=Path(root).resolve()
    directory=config.get('WorkingDirectory')
    args=config.get('ProgramArguments',[])
    if not directory or not isinstance(args,list):return False
    directory=Path(directory).resolve()
    if directory==root and any(args[i:i+2]==['-m',module] for i in range(len(args)-1)):
        return True
    # The installed chart app also supports the repository's shell launcher.
    # Match its exact script and directory; never accept arbitrary shell text.
    launcher=(root/'Section_11_UI_UX'/'binance_chart'/'run_chart.sh').resolve()
    return (label=='com.tradingindicator.chart' and len(args)==2 and args[0]=='/bin/bash'
        and launcher.is_relative_to(root) and launcher.is_file()
        and directory==launcher.parent and Path(args[1]).is_absolute()
        and Path(args[1]).resolve()==launcher)


@contextmanager
def stopped_services():
    if sys.platform!='darwin':raise RuntimeError('--manage-services requires macOS launchd')
    domain=f'gui/{os.getuid()}'
    root=REPO_ROOT
    selected=[];stopped=[]
    for label,module in (('com.tradingindicator.chart','Section_11_UI_UX.server.ui_server'),
                         ('com.tradingindicator.liverunner','Section_1_Global_Core.memory_storage.Runner.live_runner')):
        loaded=subprocess.run(['launchctl','print',domain+'/'+label],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        if loaded.returncode:continue
        path=Path.home()/'Library'/'LaunchAgents'/(label+'.plist')
        with path.open('rb') as stream:config=plistlib.load(stream)
        if not service_belongs_to_checkout(config,label,module,root):
            raise RuntimeError('Service does not belong to this checkout: '+label)
        selected.append((label,path))
    try:
        for label,path in selected:
            subprocess.run(['launchctl','bootout',domain+'/'+label],check=True)
            stopped.append((label,path));print('Stopped '+label,flush=True)
        deadline=time.monotonic()+30
        while True:
            try:assert_idle(features_store.DB_PATH.resolve());break
            except RuntimeError:
                if time.monotonic()>=deadline:raise
                time.sleep(.5)
        yield
    finally:
        failures=[]
        for label,path in reversed(stopped):
            result=subprocess.run(['launchctl','bootstrap',domain,str(path)],capture_output=True,text=True)
            if result.returncode:failures.append(label+': '+result.stderr.strip())
            else:print('Restarted '+label,flush=True)
        if failures:raise RuntimeError('Database operation ended, but service restart failed: '+'; '.join(failures))


def running_compactions():
    try:
        result=subprocess.run(['ps','-axo','pid=,etime=,stat=,%cpu=,command='],capture_output=True,text=True,timeout=5)
    except (OSError,subprocess.TimeoutExpired) as error:return [dict(error=str(error))]
    if result.returncode:return [dict(error=result.stderr.strip())]
    processes=[]
    for line in result.stdout.splitlines():
        parts=line.strip().split(None,4)
        if len(parts)==5 and ('compact_feature_storage.py' in parts[4] or 'Section_14_Operations.storage.compact_feature_storage' in parts[4]) and '--apply' in parts[4] and '--status' not in parts[4]:
            processes.append(dict(pid=parts[0],elapsed=parts[1],state=parts[2],cpu_percent=parts[3],command=parts[4]))
    return processes


def read_status(path):
    path=Path(path).resolve();target=path.with_name(path.name+'.compact-building')
    report=path.with_name(path.name+'.compaction.json')
    result=dict(mode='status',running=running_compactions(),files={},state=None)
    for name,file in (('source',path),('building',target),('backup',path.with_name(path.name+'.before-compaction'))):
        if file.exists():
            info=file.stat();result['files'][name]=dict(GiB=round(info.st_size/1024**3,3),seconds_since_modified=round(time.time()-info.st_mtime))
        else:result['files'][name]=None
    if report.exists():
        try:result['state']=json.loads(report.read_text())
        except (OSError,ValueError) as error:result['report_error']=str(error)
    if target.exists():
        try:
            with closing(sqlite3.connect(target.as_uri()+'?mode=ro',uri=True,timeout=.5)) as conn:
                conn.execute('PRAGMA query_only=ON')
                if conn.execute('SELECT 1 FROM sqlite_master WHERE name=?',(WORK,)).fetchone():
                    row=conn.execute('SELECT state FROM '+q(WORK)).fetchone()
                    if row:result['state']=json.loads(row[0])
        except (sqlite3.Error,ValueError,OSError) as error:result['building_state_unavailable']=str(error)
    state=result['state']
    expected=state.get('new_source') if state and state.get('complete') else state.get('source') if state else None
    current=identity(path) if path.exists() else None
    if expected and current and state.get('complete'):
        result['source_matches']=all(expected[key]==current[key] for key in ('path','device','inode'))
    else:result['source_matches']=bool(expected and current and expected==current)
    result['can_resume']=bool(state and not state.get('complete') and target.exists() and result['source_matches'] and not result['running'])
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    mode=parser.add_mutually_exclusive_group()
    mode.add_argument('--apply',action='store_true')
    mode.add_argument('--status',action='store_true',help='Read progress and process status without stopping services')
    parser.add_argument('--manage-services',action='store_true',help='Stop/restart only this checkout’s loaded chart and writer services')
    parser.add_argument('--batch-size',type=int,default=10000)
    args=parser.parse_args()
    if not 1<=args.batch_size<=20000:parser.error('Batch size must be 1..20000')
    path=features_store.DB_PATH.resolve()
    if args.manage_services and not args.apply:parser.error('--manage-services requires --apply')
    if args.status:print(json.dumps(read_status(path),indent=2));return
    if not args.apply:print(json.dumps(preflight(path),indent=2));return
    with stopped_services() if args.manage_services else nullcontext():
        compact(path,batch=args.batch_size)


if __name__=='__main__':main()
