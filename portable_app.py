"""Standalone production launcher. Code and persistent memory have separate lifetimes."""
import argparse
from contextlib import ExitStack,closing
import json
import os
from pathlib import Path
import shutil
import signal
import socket
import sqlite3
import subprocess
import sys
import time
import tempfile
import webbrowser

ROOT=Path(__file__).resolve().parent
WORKERS={'backend':'Section_11_UI_UX.server.ui_server','runner':'Section_1_Global_Core.memory_storage.Runner.live_runner','liquidity':'Section_1_Global_Core.liquidity.runner'}


def initialize(folder):
    folder=Path(folder).expanduser().resolve()
    for name in ('config','accounts','storage/liquidity','state','locks','logs'):(folder/name).mkdir(parents=True,exist_ok=True,mode=0o700 if name=='accounts' else 0o755)
    seeds={'config/symbols.json':'Section_1_Global_Core/Symbols/symbols.json','config/ui_config.json':'Section_11_UI_UX/config/ui_config.json','config/runtime_policy.json':'Section_1_Global_Core/runtime_policy.json'}
    for destination,source in seeds.items():
        target=folder/destination
        if not target.exists():
            value=(ROOT/source).read_bytes() if (ROOT/source).is_file() else b'{"timeframes":{},"paused_coins":[],"epochs":{}}'
            with target.open('xb') as stream:stream.write(value)
    marker=folder/'profile.json'
    if marker.exists():
        if json.loads(marker.read_text()).get('format')!=1:raise ValueError('Unsupported portable profile format')
    else:marker.write_text(json.dumps(dict(format=1,layout='portable-v1'),indent=2))
    return folder


def import_legacy(source,target):
    """Explicit initial import only. Caller must stop ALL source services first."""
    source=Path(source).resolve();target=Path(target).resolve()
    if not (source/'Section_1_Global_Core').is_dir():raise ValueError('Choose the original project directory')
    if (target/'profile.json').exists():raise ValueError('Import requires a fresh destination profile')
    storage=source/'Section_1_Global_Core/memory_storage/Storage'
    if not storage.is_dir():raise ValueError('Source storage is missing')
    # Back up each SQLite file through SQLite, including committed WAL content.
    # This is not a live multi-database snapshot; source services must be stopped.
    allowed=('klines.db','features.db','ADCN.db','intelligence.db','sentiment_sources.db','liquidity/liquidity.db')
    for relative in allowed:
        db=storage/relative
        if not db.is_file():continue
        dest=target/'storage'/relative;dest.parent.mkdir(parents=True,exist_ok=True)
        if dest.exists():raise ValueError('Destination already contains imported memory')
        with closing(sqlite3.connect(db.as_uri()+'?mode=ro',uri=True)) as src,closing(sqlite3.connect(dest)) as out:src.backup(out)
    mapping={'Section_1_Global_Core/Symbols/symbols.json':'config/symbols.json','Section_1_Global_Core/runtime_policy.json':'config/runtime_policy.json','Section_1_Global_Core/feature_runtime.json':'config/feature_runtime.json','Section_1_Global_Core/section_1_9_state.json':'state/runner.json','Section_1_Global_Core/Symbols/daily_refresh_state.json':'state/daily_refresh.json','Section_11_UI_UX/config/ui_config.json':'config/ui_config.json'}
    for old,new in mapping.items():
        src=source/old
        if src.is_file():dest=target/new;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dest)
    # Credentials are deliberately not imported implicitly from the current user.


def import_accounts(source,folder):
    """Explicit private backend-to-backend transfer; never part of app binaries."""
    source=Path(source).expanduser().resolve();target=folder/'accounts';target.mkdir(parents=True,exist_ok=True,mode=0o700)
    for name in ('users.json','alerts.sqlite3','drawings.sqlite3'):
        src=source/name;dest=target/name
        if not src.is_file():continue
        if dest.exists():raise ValueError('Account destination is not empty')
        if name.endswith('.sqlite3'):
            with closing(sqlite3.connect(src.as_uri()+'?mode=ro',uri=True)) as reader,closing(sqlite3.connect(dest)) as writer:reader.backup(writer)
        else:shutil.copy2(src,dest)
        try:dest.chmod(0o600)
        except OSError:pass


def setup_account(folder,console=False):
    from Section_11_UI_UX.server import auth
    if auth.USERS_FILE.exists():return
    if console:return auth.main()
    import tkinter as tk
    from tkinter import simpledialog,messagebox
    import secrets
    window=tk.Tk();window.withdraw()
    try:
        password=simpledialog.askstring('Trading Indicator setup','Create an admin password (at least 12 characters):',show='*',parent=window)
        if password is None:raise ValueError('Setup cancelled; no account created')
        if len(password)<12:raise ValueError('Password must have at least 12 characters')
        repeat=simpledialog.askstring('Trading Indicator setup','Repeat the admin password:',show='*',parent=window)
        if password!=repeat:raise ValueError('Passwords do not match')
        salt=secrets.token_hex(16)
        with tempfile.NamedTemporaryFile(mode='w',dir=auth.USERS_FILE.parent,delete=False) as stream:
            temp=Path(stream.name)
            json.dump({'admin':dict(role='admin',salt=salt,hash=auth.digest(password,salt))},stream)
        temp.replace(auth.USERS_FILE)
        try:auth.USERS_FILE.chmod(0o600)
        except OSError:pass
        messagebox.showinfo('Trading Indicator','Admin account created. Sign in as admin.',parent=window)
    finally:window.destroy()


def check_compatibility(folder):
    """Refuse automatic production replay caused merely by a different build."""
    path=folder/'storage/features.db'
    if not path.is_file():return
    from Section_4_Features.execution.components import current_signature
    from Section_1_Global_Core import data_policy
    expected=current_signature()
    with closing(sqlite3.connect(path.as_uri()+'?mode=ro',uri=True)) as conn:
        tables={row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if 'features' not in tables or not conn.execute('SELECT 1 FROM features LIMIT 1').fetchone():return
        if 'feature_calculation_versions' not in tables:raise ValueError('Memory has no verified feature version; prepare it in development before production use')
        jobs={(s,t):v for s,t,v in conn.execute('SELECT symbol,interval,signature FROM feature_replay_jobs')} if 'feature_replay_jobs' in tables else {}
        versions={(s,t):v for s,t,v in conn.execute('SELECT symbol,interval,signature FROM feature_calculation_versions')}
        states=set(conn.execute('SELECT symbol,interval FROM feature_engine_state')) if 'feature_engine_state' in tables else set()
        if not versions and not states:raise ValueError('Memory has features without verified checkpoints; prepare it in development first')
        mismatches=[s+' '+t for s,t in sorted(set(versions)|states) if data_policy.enabled(s,t) and ((s,t) not in states or versions.get((s,t))!=expected and jobs.get((s,t))!=expected)]
        if mismatches:raise ValueError('Build/memory formula mismatch: '+', '.join(mismatches[:8])+'. Use the matching build or a verified prepared upgrade; production replay was not started.')


def worker_command(name,folder):
    prefix=[sys.executable] if getattr(sys,'frozen',False) else [sys.executable,str(Path(__file__).resolve())]
    return [*prefix,'--data-dir',str(folder),'--worker',name]


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir',type=Path,default=None)
    parser.add_argument('--worker',choices=WORKERS,help=argparse.SUPPRESS)
    parser.add_argument('--self-test',action='store_true');parser.add_argument('--setup',action='store_true')
    parser.add_argument('--no-browser',action='store_true');parser.add_argument('--import-legacy',type=Path)
    parser.add_argument('--source-stopped',action='store_true')
    parser.add_argument('--public-origin',help='Save this installation HTTPS proxy origin and exit; no push setup required')
    parser.add_argument('--accounts-from',type=Path)
    parser.add_argument('--include-raw-archive',action='store_true')
    args=parser.parse_args(argv)
    if (args.accounts_from or args.include_raw_archive) and not args.import_legacy:parser.error('Account/raw import requires --import-legacy')
    folder=(args.data_dir or Path(os.environ.get('TRADINGBOT_DATA_DIR',Path.home()/'TradingIndicatorData'))).expanduser().resolve()
    # Set before importing any storage, account or policy module.
    os.environ['TRADINGBOT_DATA_DIR']=str(folder)
    if getattr(sys,'frozen',False):
        import certifi
        os.environ.setdefault('SSL_CERT_FILE',certifi.where())
    folder.mkdir(parents=True,exist_ok=True);(folder/'locks').mkdir(exist_ok=True)
    from Section_1_Global_Core import data_policy
    lock_name=args.worker or 'application'
    with data_policy._file_lock(folder/'locks'/(lock_name+'.lock'),data_policy.fcntl.LOCK_EX,0):
        if args.import_legacy:
            if args.worker or not args.source_stopped:raise ValueError('Initial import requires --source-stopped and all original services stopped')
            import_legacy(args.import_legacy,folder)
            if args.accounts_from:import_accounts(args.accounts_from,folder)
            if args.include_raw_archive:
                raw=args.import_legacy/'Section_1_Global_Core/memory_storage/Storage/liquidity/raw'
                if raw.is_dir():shutil.copytree(raw,folder/'storage/liquidity/raw')
        initialize(folder)
        if args.public_origin:
            if args.worker:raise ValueError('Configure the origin through the main launcher')
            from Section_11_UI_UX.server import public_access
            print('HTTPS access configured:',public_access.save_origin(args.public_origin));return 0
        if args.worker:
            if args.worker=='runner':check_compatibility(folder)
            import runpy
            sys.argv=[WORKERS[args.worker]]
            runpy.run_module(WORKERS[args.worker],run_name='__main__');return 0
        if args.self_test:
            from Section_1_Global_Core.memory_storage.Storage import klines_store,features_store,adcn_store,engine_store
            from Section_11_UI_UX.server import auth,ui_server
            from Section_4_Features.execution.components import current_signature
            from Section_5_Market_Regime.engines import regime
            from Section_4_Features.execution.engine import Engine
            from Section_4_Features.execution import checkpoint
            import tkinter
            tkinter.Tcl().eval('info patchlevel')
            if getattr(sys,'frozen',False):
                import ssl
                assert ssl.create_default_context().get_ca_certs(), 'Bundled TLS trust roots missing'
            engine=Engine('BTCUSDT','5m')
            engine.step(dict(symbol='BTCUSDT',interval='5m',open_time=0,close_time=299999,open=100.,high=102.,low=99.,close=101.,volume=10.))
            assert checkpoint.restore('BTCUSDT','5m',checkpoint.dump(engine,(0,0)),(0,0)).context.last_time==0
            assert all(folder in p.parents for p in (klines_store.DB_PATH,features_store.DB_PATH,adcn_store.DB_PATH,engine_store.DB_PATH,auth.USERS_FILE))
            assert (ui_server.SECTION_11/'web_root/index.html').is_file()
            print(json.dumps(dict(status='PASS',profile=str(folder),formula_signature=current_signature(),engine=regime.VERSION)))
            return 0
        check_compatibility(folder)
        from Section_11_UI_UX.server import auth
        if args.setup:setup_account(folder,console=True);return 0
        if not auth.USERS_FILE.exists():
            if args.no_browser:raise ValueError('Create accounts first with --setup')
            setup_account(folder)
        with socket.socket() as port:port.bind(('127.0.0.1',8000))
        children=[];stopping=[False]
        for sig in (signal.SIGINT,signal.SIGTERM):signal.signal(sig,lambda *_:stopping.__setitem__(0,True))
        control=None
        if not args.no_browser:
            import tkinter as tk
            control=tk.Tk();control.title('Trading Indicator server')
            tk.Label(control,text='Trading Indicator — standalone server',font=('',14)).pack(padx=24,pady=12)
            tk.Label(control,text='Memory: '+str(folder),wraplength=550).pack(padx=24,pady=8)
            tk.Label(control,text='Closing the chart does not stop calculations. Use Stop server to exit.').pack(padx=24,pady=8)
            tk.Button(control,text='Open chart',command=lambda:webbrowser.open('http://127.0.0.1:8000/')).pack(pady=6)
            tk.Button(control,text='Stop server',command=lambda:stopping.__setitem__(0,True)).pack(pady=12)
            control.protocol('WM_DELETE_WINDOW',lambda:stopping.__setitem__(0,True));control.update()
        with ExitStack() as files:
            try:
                for name in WORKERS:
                    output=files.enter_context((folder/'logs'/(name+'.log')).open('ab',buffering=0))
                    child=subprocess.Popen(worker_command(name,folder),stdout=output,stderr=subprocess.STDOUT,cwd=ROOT)
                    children.append((name,child))
                print(f'Trading Indicator running. Memory: {folder}. Stop with Ctrl+C. Closing the chart does not stop the server.',flush=True)
                if not args.no_browser:
                    from urllib.request import urlopen
                    for _ in range(100):
                        if stopping[0] or any(child.poll() is not None for _,child in children):break
                        try:
                            with urlopen('http://127.0.0.1:8000/api/session',timeout=.5):pass
                            webbrowser.open('http://127.0.0.1:8000/');break
                        except OSError:time.sleep(.1)
                while not stopping[0]:
                    if control:control.update()
                    failed=[name for name,child in children if child.poll() is not None]
                    if failed:raise RuntimeError('Service exited: '+', '.join(failed)+'. See profile logs; remaining services will stop.')
                    time.sleep(.5)
            finally:
                for _,child in children:
                    if child.poll() is None:child.terminate()
                for _,child in children:
                    try:child.wait(timeout=10)
                    except subprocess.TimeoutExpired:child.kill();child.wait()
                if control:control.destroy()
    return 0

if __name__=='__main__':
    try:raise SystemExit(main())
    except (OSError,ValueError,RuntimeError,sqlite3.Error) as error:
        if os.environ.get('TRADINGBOT_DEBUG'):
            import traceback;traceback.print_exc()
        print('Trading Indicator:',error,file=sys.stderr);raise SystemExit(1)
