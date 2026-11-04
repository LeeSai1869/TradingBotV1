import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules
root=Path(SPECPATH).parent
packages=['Section_1_Global_Core','Section_4_Features','Section_5_Market_Regime','Section_8_Decision_Engine','Section_9_Confidence_Engine','Section_10_Opportunity_Engine','Section_11_UI_UX']
hidden=[];datas=[];binaries=[]
# Some relocatable Linux Python distributions keep Tcl libraries outside the
# loader's default search path; make these explicit instead of relying on host paths.
if sys.platform.startswith('linux'):
    for pattern in ('libtcl*.so','libtk*.so'):
        binaries.extend((str(file),'.') for file in (Path(sys.base_prefix)/'lib').glob(pattern))
for package in packages:
    hidden+=collect_submodules(package)
    for p in (root/package).rglob('*'):
        if p.is_file() and '__pycache__' not in p.parts and p.suffix in ('.py','.json','.js','.css','.html','.md','.pine') and p.name not in ('section_1_9_state.json','feature_runtime.json','daily_refresh_state.json'):
            datas.append((str(p),str(p.parent.relative_to(root))))
# Bundle chart assets locally; development HTML and chart behavior stay unchanged.
vendor=root/'packaging/vendor'
for file in vendor.iterdir():datas.append((str(file),'Section_11_UI_UX/web_root/vendor'))
html=root/'build/portable-assets/index.html';html.parent.mkdir(parents=True,exist_ok=True)
html.write_text((root/'Section_11_UI_UX/web_root/index.html').read_text().replace('https://unpkg.com/lightweight-charts@5.2.1/dist/lightweight-charts.standalone.production.js','/web_root/vendor/lightweight-charts.js'))
datas=[item for item in datas if item[0]!=str(root/'Section_11_UI_UX/web_root/index.html')]
datas.append((str(html),'Section_11_UI_UX/web_root'))
# Carry third-party distribution licenses alongside the runtime.
from importlib.metadata import distribution,PackageNotFoundError
for name in ('requests','websocket-client','certifi','urllib3','idna','charset-normalizer','cryptography','cffi','PyInstaller'):
    try:
        dist=distribution(name)
        for file in dist.files or []:
            if any(word in Path(file).name.upper() for word in ('LICENSE','COPYING','NOTICE')):
                actual=Path(dist.locate_file(file))
                if actual.is_file():datas.append((str(actual),'licenses/'+name))
    except PackageNotFoundError:pass
a=Analysis([str(root/'portable_app.py')],pathex=[str(root)],binaries=binaries,datas=datas,hiddenimports=hidden,excludes=['pytest','playwright'],noarchive=False,module_collection_mode={**{name:'py' for name in packages},'json':'py'})
pyz=PYZ(a.pure)
exe=EXE(pyz,a.scripts,[],exclude_binaries=True,name='TradingIndicator',console=True)
coll=COLLECT(exe,a.binaries,a.datas,name='TradingIndicator')
if sys.platform=='darwin':
    app=BUNDLE(coll,name='TradingIndicator.app',bundle_identifier='com.tradingindicator.desktop')
