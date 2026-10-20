"""A6 — Audit orchestrator.

Runs A1, A2, A4, A5 every call. Runs A3 daily (per config).
Writes a manifest JSON + updates metadata.db.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import sqlite3
import time
from pathlib import Path
from Section_1_Global_Core import data_policy

from . import (
    audit_config as cfg,
    audit_schema,
    audit_continuity,
    audit_cross_source,
    audit_consistency,
    audit_freshness,
)


# ------------------------------------------------------------------
# Metadata DB
# ------------------------------------------------------------------

_METADATA_SCHEMA = """
CREATE TABLE IF NOT EXISTS audit_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT NOT NULL,
    finished_at TEXT NOT NULL,
    duration_ms INTEGER NOT NULL,
    klines_sha256 TEXT,
    pass INTEGER NOT NULL,
    summary TEXT
);

CREATE TABLE IF NOT EXISTS compromised_pairs (
    symbol TEXT NOT NULL,
    interval TEXT NOT NULL,
    reason TEXT NOT NULL,
    first_seen TEXT NOT NULL,
    resolved_at TEXT,
    PRIMARY KEY (symbol, interval, first_seen)
);
"""


def _open_metadata():
    conn = sqlite3.connect(str(cfg.METADATA_DB))
    conn.executescript(_METADATA_SCHEMA)
    return conn


def is_compromised(symbol: str, interval: str) -> bool:
    if not cfg.METADATA_DB.exists():
        return False
    conn = sqlite3.connect(str(cfg.METADATA_DB))
    try:
        cur = conn.execute(
            "SELECT 1 FROM compromised_pairs "
            "WHERE symbol=? AND interval=? AND resolved_at IS NULL LIMIT 1",
            (symbol, interval),
        )
        return cur.fetchone() is not None
    finally:
        conn.close()


def mark_compromised(symbol: str, interval: str, reason: str) -> None:
    conn = _open_metadata()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO compromised_pairs "
            "(symbol, interval, reason, first_seen) VALUES (?,?,?,?)",
            (symbol, interval, reason, _now()),
        )
        conn.commit()
    finally:
        conn.close()


def unblock(symbol: str, interval: str) -> bool:
    conn = _open_metadata()
    try:
        cur = conn.execute(
            "UPDATE compromised_pairs SET resolved_at=? "
            "WHERE symbol=? AND interval=? AND resolved_at IS NULL",
            (_now(), symbol, interval),
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def list_compromised() -> list[dict]:
    if not cfg.METADATA_DB.exists():
        return []
    conn = sqlite3.connect(str(cfg.METADATA_DB))
    try:
        cur = conn.execute(
            "SELECT symbol, interval, reason, first_seen FROM compromised_pairs "
            "WHERE resolved_at IS NULL ORDER BY first_seen"
        )
        return [
            {"symbol": r[0], "interval": r[1], "reason": r[2], "first_seen": r[3]}
            for r in cur.fetchall()
        ]
    finally:
        conn.close()


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _file_sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _active_pairs() -> list[tuple[str, str]]:
    """(symbol, interval) pairs currently stored in klines.db."""
    if not cfg.KLINES_DB.exists():
        return []
    conn = sqlite3.connect(str(cfg.KLINES_DB))
    try:
        cur = conn.execute(
            "SELECT DISTINCT symbol, interval FROM klines ORDER BY symbol, interval"
        )
        return [(r[0], r[1]) for r in cur.fetchall()]
    finally:
        conn.close()


def _last_daily_audit_iso() -> str | None:
    if not cfg.LOG_DIR.exists():
        return None
    files = sorted(cfg.LOG_DIR.glob("*_daily.json"))
    if not files:
        return None
    return files[-1].stem.split("_")[0]


def _should_run_a3() -> bool:
    last = _last_daily_audit_iso()
    if last is None:
        return True
    try:
        last_dt = _dt.datetime.strptime(last, "%Y-%m-%dT%H-%M-%SZ")
    except ValueError:
        return True
    now_dt = _dt.datetime.utcnow()
    return (now_dt - last_dt).total_seconds() >= cfg.A3_RUN_INTERVAL_HOURS * 3600


# ------------------------------------------------------------------
# Main entry points
# ------------------------------------------------------------------

def summarize(manifest):
    """Keep integrity, source verification and freshness distinct in reports."""
    a3 = manifest.get('A3') or {}
    source = ('failed' if a3.get('issues') else 'disabled' if a3.get('enabled') is False
              else 'passed' if a3.get('samples_checked',0)>0 else 'not-verified') if a3.get('ran') else 'not-run'
    result = {
        'schema_pass': (manifest.get('A1') or {}).get('failed',0)==0,
        'continuity_pass': not manifest.get('A2'),
        'source_verification': source,
        'consistency_pass': None if manifest.get('A4_ran') is False else not any(pair.get('mismatch_count',0) for item in manifest.get('A4') or [] for pair in item.get('pairs',[])),
        'stale_count': (manifest.get('A5') or {}).get('stale_count',0),
        'missing_count': (manifest.get('A5') or {}).get('missing',0),
    }
    result['freshness_pass'] = result['stale_count']==0 and result['missing_count']==0
    result['pass'] = (result['schema_pass'] and result['continuity_pass'] and source!='failed'
                      and result['consistency_pass'] is not False and result['freshness_pass'])
    return result


def run(*, sample_rows_per_pair: int = 200,
        continuity_refetch: bool | None = None,
        include_daily: bool | None = None) -> dict:
    """Full audit run.

    sample_rows_per_pair: how many recent rows per pair go to A1.
    continuity_refetch: override A2 auto-refetch behavior.
    include_daily: force A3 on/off; None = per schedule.
    """
    started = time.time()
    started_iso = _now()
    klines_sha = _file_sha256(cfg.KLINES_DB)

    pairs = _active_pairs()
    manifest: dict = {
        "started_at": started_iso,
        "klines_sha256": klines_sha,
        "pairs": len(pairs),
        "A1": None, "A2": [], "A3": None, "A4": [], "A5": None,
    }

    # -------- A1: sample recent rows per pair --------
    a1_failures = []
    a1_checked = 0
    conn = sqlite3.connect(str(cfg.KLINES_DB))
    try:
        for sym, iv in pairs:
            cur = conn.execute(
                "SELECT symbol, interval, open_time, open, high, low, close, "
                "volume, close_time FROM klines WHERE symbol=? AND interval=? "
                "ORDER BY open_time DESC LIMIT ?",
                (sym, iv, sample_rows_per_pair),
            )
            rows = cur.fetchall()
            r = audit_schema.run(rows)
            a1_checked += r["checked"]
            a1_failures.extend(r["failures"])
    finally:
        conn.close()
    manifest["A1"] = {
        "checked": a1_checked,
        "failed": len(a1_failures),
        "failures": a1_failures[:cfg.A1_MAX_FAILURES_REPORTED],
    }

    # -------- A2: continuity per pair --------
    a2_results = []
    for sym, iv in pairs:
        r = audit_continuity.run(sym, iv, refetch=continuity_refetch)
        if r.get("gap_count", 0) or r.get("overlap_count", 0):
            a2_results.append(r)
        if r.get("still_broken") and cfg.A2_MARK_COMPROMISED_AFTER_FAILED_REFETCH:
            mark_compromised(sym, iv, "continuity_gap")
    manifest["A2"] = a2_results

    # -------- A3: cross-source (daily) --------
    do_a3 = include_daily if include_daily is not None else _should_run_a3()
    if do_a3:
        a3_results = []
        samples_checked = 0
        for sym, iv in pairs:
            r = audit_cross_source.run(sym, iv)
            samples_checked += r.get("sampled",0)
            if r.get("mismatch_count", 0) or r.get("error_count", 0):
                a3_results.append(r)
        manifest["A3"] = {
            "ran": True, "enabled": cfg.A3_ENABLED, "samples_checked": samples_checked,
            "pairs_checked": len(pairs),
            "issues": a3_results,
        }
    else:
        manifest["A3"] = {"ran": False}

    # -------- A4: cross-interval consistency --------
    symbols = sorted({s for s, _ in pairs})
    a4_results = []
    for sym in symbols:
        r = audit_consistency.run(sym)
        if r.get("enabled"):
            a4_results.append(r)
    manifest["A4"] = a4_results

    # -------- A5: freshness --------
    manifest["A5"] = audit_freshness.run([pair for pair in pairs if data_policy.enabled(*pair)])

    finished_iso = _now()
    duration_ms = int((time.time() - started) * 1000)
    manifest["finished_at"] = finished_iso
    manifest["duration_ms"] = duration_ms

    manifest['summary'] = summarize(manifest)
    passed = manifest['summary']['pass']
    manifest['pass'] = passed

    # -------- Write manifest --------
    cfg.LOG_DIR.mkdir(parents=True, exist_ok=True)
    tag = "daily" if do_a3 else "cycle"
    fname = started_iso.replace(":", "-") + "_" + tag + ".json"
    (cfg.LOG_DIR / fname).write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )

    # -------- Record in metadata DB --------
    try:
        conn = _open_metadata()
        conn.execute(
            "INSERT INTO audit_runs "
            "(started_at, finished_at, duration_ms, klines_sha256, pass, summary) "
            "VALUES (?,?,?,?,?,?)",
            (started_iso, finished_iso, duration_ms, klines_sha,
             1 if passed else 0,
             json.dumps({
                 "A1_failed": manifest["A1"]["failed"],
                 "A2_issues": len(manifest["A2"]),
                 "A3_ran": manifest["A3"]["ran"] if manifest["A3"] else False,
                 "A5_stale": manifest["A5"]["stale_count"],
             })),
        )
        conn.commit()
        conn.close()
    except Exception:
        pass

    return manifest


def run_fast(*, sample_rows_per_pair: int = 200) -> dict:
    """Bounded recent-row A1/A2 plus A5. No full scan, hash or inline repair.

    Full-history continuity, source comparison, consistency and repairs remain in
    run(). They must not monopolize the runner's incremental download loop.
    """
    limit = max(2, min(int(sample_rows_per_pair), 1000))
    started = time.time()
    pairs = [(symbol, interval) for symbol in data_policy.active_symbols()
             for interval in data_policy.active_intervals()]
    failures, issues, checked = [], [], 0
    conn = (sqlite3.connect(cfg.KLINES_DB.resolve().as_uri()+'?mode=ro',uri=True,timeout=1)
            if cfg.KLINES_DB.exists() else None)
    try:
        for symbol, interval in pairs:
            rows = conn.execute(
                'SELECT symbol,interval,open_time,open,high,low,close,volume,close_time '
                'FROM klines WHERE symbol=? AND interval=? ORDER BY open_time DESC LIMIT ?',
                (symbol,interval,limit)).fetchall() if conn else []
            result = audit_schema.run(rows)
            checked += result['checked']; failures.extend(result['failures'])
            if not cfg.A2_ENABLED or not rows:
                continue
            times = sorted(row[2] for row in rows)
            gaps = (audit_continuity._find_monthly_gaps(times) if interval=='1M'
                    else audit_continuity._find_gaps(times,audit_continuity.INTERVAL_MS[interval]))
            gaps = [(start,end) for start,end in gaps if not audit_continuity._is_known(symbol,interval,start,end)]
            overlaps = audit_continuity._find_overlaps(times)
            if gaps or overlaps:
                issues.append({'symbol':symbol,'interval':interval,'gap_count':len(gaps),
                               'overlap_count':len(overlaps),'gaps':gaps,'overlaps':overlaps,
                               'repair_deferred':True,'scope':'recent rows'})
    finally:
        if conn: conn.close()
    manifest = {'started_at':_now(),'finished_at':_now(),'mode':'fast','scope':'recent rows only',
                'sample_rows_per_pair':limit,'klines_sha256':None,'pairs':len(pairs),
                'A1':{'checked':checked,'failed':len(failures),'failures':failures[:cfg.A1_MAX_FAILURES_REPORTED]},
                'A2':issues,'A3':{'ran':False},'A4':[],'A4_ran':False,
                'A5':audit_freshness.run(pairs)}
    manifest['duration_ms']=int((time.time()-started)*1000)
    manifest['summary']=summarize(manifest);manifest['pass']=manifest['summary']['pass']
    cfg.LOG_DIR.mkdir(parents=True,exist_ok=True)
    (cfg.LOG_DIR/f"{time.time_ns()}_fast.json").write_text(json.dumps(manifest,indent=2)+'\n')
    metadata = _open_metadata()
    try:
        metadata.execute('INSERT INTO audit_runs(started_at,finished_at,duration_ms,klines_sha256,pass,summary) VALUES(?,?,?,?,?,?)',
            (manifest['started_at'],manifest['finished_at'],manifest['duration_ms'],None,int(manifest['pass']),json.dumps(manifest['summary'])))
        metadata.commit()
    finally:metadata.close()
    return manifest
