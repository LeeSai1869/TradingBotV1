import sqlite3, subprocess, sys
from pathlib import Path
from datetime import datetime, timezone

BASE    = Path("/Users/jhanzeebakbar/Scalp Indicator V1")
STORAGE = BASE / "Section_1_Global_Core/memory_storage/Storage"
KLINES  = STORAGE / "klines.db"
FEAT    = STORAGE / "features.db"
META    = STORAGE / "metadata.db"

EXPECTED_SYMBOLS = ['BTCUSDT','SUIUSDT','ETHUSDT','BNBUSDT','XRPUSDT','SOLUSDT','TRXUSDT',
    'ZECUSDT','HYPEUSDT','LINKUSDT','ADAUSDT','NEARUSDT','XLMUSDT','BCHUSDT','LTCUSDT',
    'AVAXUSDT','UNIUSDT','GRAMUSDT','HBARUSDT','QNTUSDT','TAOUSDT','ENAUSDT','AAVEUSDT',
    'ONDOUSDT','DOTUSDT','WLDUSDT','ASTERUSDT','WLFIUSDT','SKYUSDT','ICPUSDT','MORPHOUSDT',
    'ETCUSDT','ARBUSDT','JSTUSDT','RENDERUSDT','JUPUSDT','POLUSDT','ALGOUSDT','ATOMUSDT',
    'FILUSDT','AEROUSDT','ZROUSDT','NEXOUSDT','STXUSDT','NIGHTUSDT','INJUSDT','CAKEUSDT',
    'APTUSDT','ETHFIUSDT']

INTERVAL_MS = {"15m":900_000,"1h":3_600_000,"4h":14_400_000,"1d":86_400_000,"1w":604_800_000,
               "1m":60_000,"3m":180_000,"5m":300_000,"30m":1_800_000,"2h":7_200_000,
               "6h":21_600_000,"8h":28_800_000,"12h":43_200_000,"3d":259_200_000,"1M":2_592_000_000}

def ts(ms):
    if ms is None: return "-"
    return datetime.fromtimestamp(ms/1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M")

def running():
    print("=== processes ===")
    for pat, label in [("download_binance_history","downloader"), ("update_klines","updater"),
                       ("live_runner|historical_runner|process_candle","feature/runner")]:
        try:
            out = subprocess.check_output(["pgrep","-fl",pat], text=True, stderr=subprocess.DEVNULL).strip()
            print(f"  {label:<16}: {'RUNNING' if out else 'not running'}")
            if out:
                for line in out.splitlines()[:3]: print(f"      {line}")
        except subprocess.CalledProcessError:
            print(f"  {label:<16}: not running")

def klines_status():
    print(f"\n=== downloads (klines.db) ===")
    if not KLINES.exists():
        print(f"  [!] missing {KLINES}"); return
    conn = sqlite3.connect(f"file:{KLINES}?mode=ro", uri=True)
    cur = conn.cursor()
    cur.execute("SELECT DISTINCT symbol FROM klines")
    present = {r[0] for r in cur.fetchall()}
    missing = [s for s in EXPECTED_SYMBOLS if s not in present]
    print(f"  symbols: {len(present)} present / {len(EXPECTED_SYMBOLS)} expected")
    if missing: print(f"  [!] MISSING: {missing}")

    now_ms = int(datetime.now(timezone.utc).timestamp()*1000)
    cur.execute("""SELECT symbol, interval, COUNT(*), MAX(open_time) FROM klines
                   GROUP BY symbol, interval ORDER BY symbol, interval""")
    stale = []
    for sym, tf, n, tmax in cur.fetchall():
        step = INTERVAL_MS.get(tf)
        if not step or not tmax: continue
        lag = max(0, (now_ms - tmax)//step)
        if lag > 3: stale.append((sym, tf, n, tmax, lag))
    if stale:
        print(f"  [!] {len(stale)} pair/TF stale (>3 bars behind):")
        for sym, tf, n, tmax, lag in stale[:25]:
            print(f"      {sym:<10} {tf:<4} rows={n:>8,} last={ts(tmax)} lag={lag}bar")
        if len(stale) > 25: print(f"      … and {len(stale)-25} more")
    else:
        print("  ✓ all pair/TF current (≤3 bars behind)")
    conn.close()

def features_status():
    print(f"\n=== features (features.db) ===")
    if not FEAT.exists():
        print(f"  [!] missing {FEAT}"); return
    conn = sqlite3.connect(f"file:{FEAT}?mode=ro", uri=True)
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [r[0] for r in cur.fetchall()]
    if not tables:
        print("  (no tables — features never written)"); conn.close(); return
    for t in tables:
        cur.execute(f"PRAGMA table_info({t})")
        cols = [c[1] for c in cur.fetchall()]
        tcol = next((c for c in cols if c.lower() in ("timestamp","open_time","ts","time","created_at")), None)
        scol = next((c for c in cols if c.lower() in ("symbol","pair")), None)
        cur.execute(f"SELECT COUNT(*) FROM {t}"); total = cur.fetchone()[0]
        info = f"  table {t}: {total:,} rows"
        if tcol:
            cur.execute(f"SELECT MAX({tcol}) FROM {t}"); last = cur.fetchone()[0]
            info += f"  last={ts(last) if isinstance(last,int) and last>1e12 else last}"
        if scol:
            cur.execute(f"SELECT COUNT(DISTINCT {scol}) FROM {t}"); info += f"  symbols={cur.fetchone()[0]}"
        print(info)
    conn.close()

def compromised():
    if not META.exists(): return
    conn = sqlite3.connect(f"file:{META}?mode=ro", uri=True)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM compromised_pairs WHERE resolved_at IS NULL")
    n = cur.fetchone()[0]
    print(f"\n=== metadata.db ===")
    print(f"  unresolved compromised_pairs: {n}")
    conn.close()

if __name__ == "__main__":
    print(f"Pipeline status @ {datetime.now(timezone.utc).isoformat()}\n")
    running(); klines_status(); features_status(); compromised()
