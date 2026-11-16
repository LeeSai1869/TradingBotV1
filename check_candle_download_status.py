import sqlite3, subprocess
from pathlib import Path
from datetime import datetime, timezone

BASE    = Path("/Users/jhanzeebakbar/Scalp Indicator V1")
STORAGE = BASE / "Section_1_Global_Core/memory_storage/Storage"
KLINES  = STORAGE / "klines.db"
META    = STORAGE / "metadata.db"

INTERVAL_MS = {
    "1m":60_000, "3m":180_000, "5m":300_000, "15m":900_000, "30m":1_800_000,
    "1h":3_600_000, "2h":7_200_000, "4h":14_400_000, "6h":21_600_000,
    "8h":28_800_000, "12h":43_200_000, "1d":86_400_000,
}

def ts(ms):
    if ms is None: return "-"
    return datetime.fromtimestamp(ms/1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

def klines_status():
    if not KLINES.exists():
        print(f"[!] missing {KLINES}"); return
    print(f"\n=== klines.db ({KLINES.stat().st_size/1e6:.1f} MB) ===")
    conn = sqlite3.connect(f"file:{KLINES}?mode=ro", uri=True)
    cur = conn.cursor()
    cur.execute("""
        SELECT symbol, interval, COUNT(*), MIN(open_time), MAX(open_time)
        FROM klines GROUP BY symbol, interval ORDER BY symbol, interval
    """)
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    print(f"{'symbol':<12}{'tf':<5}{'rows':>9}  {'first':<21}{'last':<21}{'lag':>8}")
    print("-"*82)
    for sym, tf, n, tmin, tmax in cur.fetchall():
        step = INTERVAL_MS.get(tf)
        lag = ""
        if step and tmax:
            lag = f"{max(0, (now_ms - tmax) // step)}bar"
        print(f"{sym:<12}{tf:<5}{n:>9,}  {ts(tmin):<21}{ts(tmax):<21}{lag:>8}")
    conn.close()

def compromised_status():
    if not META.exists():
        return
    conn = sqlite3.connect(f"file:{META}?mode=ro", uri=True)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM compromised_pairs WHERE resolved_at IS NULL")
    open_gaps = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM compromised_pairs")
    total = cur.fetchone()[0]
    print(f"\n=== metadata.db ===")
    print(f"compromised_pairs: {total} total, {open_gaps} unresolved")
    if open_gaps:
        cur.execute("""SELECT symbol, interval, reason, first_seen FROM compromised_pairs
                       WHERE resolved_at IS NULL ORDER BY first_seen DESC LIMIT 10""")
        for r in cur.fetchall():
            print(f"  {r[0]:<10} {r[1]:<5} {r[2]:<30} {r[3]}")
    conn.close()

def running_downloader():
    print(f"\n=== running downloader processes ===")
    try:
        out = subprocess.check_output(
            ["pgrep", "-fl", "download_binance_history|update_klines"],
            text=True, stderr=subprocess.DEVNULL
        ).strip()
        print(out if out else "  (none — download is NOT currently running)")
    except subprocess.CalledProcessError:
        print("  (none — download is NOT currently running)")

def main():
    print(f"Download status @ {datetime.now(timezone.utc).isoformat()}")
    running_downloader()
    klines_status()
    compromised_status()
    print("\nNote: no persisted queue. 'Status' = last open_time per pair vs now,")
    print("      plus any live stdout from download_binance_history.py.")

if __name__ == "__main__":
    main()
