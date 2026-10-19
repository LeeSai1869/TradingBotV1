"""Full audit of Section 1. Read-only. No changes."""
import sqlite3
from pathlib import Path

P = "PASS"; F = "FAIL"

def sec(t):
    print()
    print("=" * 70)
    print(t)
    print("=" * 70)

def chk(label, cond, extra=""):
    print(f"  [{P if cond else F}] {label}" + (f" — {extra}" if extra else ""))
    return cond

SECTION_1 = Path("/Users/jhanzeebakbar/Scalp Indicator V1/Section_1_Global_Core")
STORAGE   = SECTION_1 / "memory_storage" / "Storage"


sec("1. Section 1 file inventory")
for name in ["__init__.py", "orchestrator.py", "processors.json",
             "global_packet.py", "symbols.json", "section_1_9_state.json"]:
    p = SECTION_1 / name
    chk(name, p.exists(), p.stat().st_size if p.exists() else "MISSING")

sec("2. Storage folder files")
for name in ["__init__.py", "db.py", "klines_store.py", "features_store.py",
             "adcn_store.py", "klines.db", "features.db", "ADCN.db", "metadata.db"]:
    p = STORAGE / name
    chk(name, p.exists(), p.stat().st_size if p.exists() else "MISSING")

sec("3. db.py — function list")
try:
    import importlib.util, sys
    spec = importlib.util.spec_from_file_location("db_only", STORAGE / "db.py")
    print("  (skipping direct load — db.py uses package-relative imports)")
    from Section_1_Global_Core.memory_storage.Storage import db as d
    for fn in sorted([f for f in dir(d) if not f.startswith("_") and callable(getattr(d, f))]):
        print(f"    {fn}")
    chk("db.py imports", True)
except Exception as e:
    chk("db.py imports", False, e)

sec("4. klines_store — function list")
from Section_1_Global_Core.memory_storage.Storage import klines_store as k
print("  functions:")
for fn in sorted([f for f in dir(k) if not f.startswith("_") and callable(getattr(k, f))]):
    print(f"    {fn}")

sec("5. features_store — function list")
from Section_1_Global_Core.memory_storage.Storage import features_store as f
for fn in sorted([x for x in dir(f) if not x.startswith("_") and callable(getattr(f, x))]):
    print(f"    {fn}")

sec("6. adcn_store — function list")
from Section_1_Global_Core.memory_storage.Storage import adcn_store as a
for fn in sorted([x for x in dir(a) if not x.startswith("_") and callable(getattr(a, x))]):
    print(f"    {fn}")

sec("7. db.py read functions return sanity")
try:
    print("  read_klines(BTCUSDT,15m,None,None) len:",
          len(d.read_klines("BTCUSDT", "15m", None, None)))
    print("  read_last_klines(BTCUSDT,15m,5) len:",
          len(d.read_last_klines("BTCUSDT", "15m", 5)))
    print("  last_kline_time:", d.last_kline_time("BTCUSDT", "15m"))
    print("  last_feature_time:", d.last_feature_time("BTCUSDT", "15m"))
    print("  last_adcn_time:", d.last_adcn_time("BTCUSDT", "15m"))
    print("  read_signals(BTCUSDT,15m,5) len:",
          len(d.read_signals("BTCUSDT", "15m", 5)))
except Exception as e:
    print("  ERROR:", e)

sec("8. features_store.read_range — does it exist?")
print("  has read_range:", hasattr(f, "read_range"))
print("  has read_row:  ", hasattr(f, "read_row"))
print("  has read_last_n:", hasattr(f, "read_last_n"))
print("  has last_open_time:", hasattr(f, "last_open_time"))

sec("9. adcn_store — does it have read_range?")
print("  has read_range:", hasattr(a, "read_range"))
print("  has read_signals:", hasattr(a, "read_signals"))
print("  has last_open_time:", hasattr(a, "last_open_time"))
print("  has last_signal_for:", hasattr(a, "last_signal_for"))

sec("10. Files modified in the last 2 hours under Section 1")
import time as _t
now = _t.time()
for p in sorted(SECTION_1.rglob("*")):
    if p.is_file() and p.suffix in (".py", ".json", ".db"):
        age_min = (now - p.stat().st_mtime) / 60
        if age_min < 120:
            print(f"  {age_min:6.1f} min ago  {p.relative_to(SECTION_1)}")

sec("AUDIT COMPLETE")
