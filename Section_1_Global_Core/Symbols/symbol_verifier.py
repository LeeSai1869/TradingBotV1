# ============================================================
# section_1_11_symbol_verifier.py — v2
# Human-in-the-loop symbol approval CLI
# ============================================================
#
# Commands:
#   status
#   list-pending
#   set-cap N
#   approve SYM [--force] [--drop SYM]
#   reactivate SYM [--drop SYM]
#   disapprove SYM --reason "..."
#   move SYM approved|disapproved
# ============================================================

from __future__ import annotations

import argparse
import datetime as _dt
import json
import sys
from pathlib import Path
from Section_1_Global_Core import data_policy


_DIR = Path(__file__).resolve().parent
_JSON = _DIR / "symbols.json"
_LOG = _DIR / "symbols_audit.log"


def _now():
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _read():
    global _read_snapshot
    _read_snapshot = _JSON.read_text(encoding="utf-8")
    return json.loads(_read_snapshot)


def _write(data):
    with data_policy.locked():
        if _JSON.read_text(encoding="utf-8") != _read_snapshot:
            raise RuntimeError("Coin registry changed during operation; rerun the command")
        data["updated_at"] = _now()
        tmp = _JSON.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        tmp.replace(_JSON)


def _log(action, symbol, detail):
    with _LOG.open("a", encoding="utf-8") as f:
        f.write(_now() + "\t" + action + "\t" + symbol + "\t" + detail + "\n")


def _n(s): return s.strip().upper()


def _active(data):
    top = {e["symbol"] for e in data.get("top50", [])}
    return [e["symbol"] for e in data["approved"] if e["symbol"] in top]


def _find(lst, symbol):
    for e in lst:
        if e["symbol"] == symbol:
            return e
    return None


def _drop_approved_to_inactive(data, symbol):
    """No-op for data model (approved list already holds it). Just log."""
    data.setdefault("inactive_log", []).append(
        {"symbol": symbol, "event": "deactivated", "at": _now()}
    )


# ------------------------------------------------------------
# Commands
# ------------------------------------------------------------

def cmd_status(args):
    data = _read()
    act = _active(data)
    app = data["approved"]
    inact = [e["symbol"] for e in app if e["symbol"] not in act]
    print("schema_version :", data.get("schema_version"))
    print("updated_at     :", data.get("updated_at"))
    print("active_cap     :", data.get("active_cap"))
    print("approved       :", len(app))
    print("  active       :", len(act), "->", act)
    print("  inactive     :", len(inact), "->", inact)
    print("disapproved    :", len(data["disapproved"]))
    print("pending        :", len(data["pending"]))
    for e in data["pending"]:
        tag = "REACTIVATION" if e.get("reactivation") else "NEW"
        print("    [" + tag + "]", e["symbol"], "rank=" + str(e.get("rank")))
    return 0


def cmd_list_pending(args):
    data = _read()
    if not data["pending"]:
        print("No pending approvals.")
        return 0
    for e in data["pending"]:
        tag = "REACTIVATION" if e.get("reactivation") else "NEW"
        print("=" * 60)
        print("  [" + tag + "]", e["symbol"])
        print("  rank          :", e.get("rank"))
        print("  market_cap    :", e.get("market_cap_usd"))
        print("  coingecko_id  :", e.get("coingecko_id"))
        print("  categories    :", ", ".join(e.get("categories") or []))
        print("  requires_swap :", e.get("requires_swap"))
        if e.get("swap_candidates"):
            print("  swap_options  :", ", ".join(e["swap_candidates"]))
        print("  proposed_at   :", e.get("proposed_at"))
    return 0


def cmd_set_cap(args):
    data = _read()
    if args.n < 1:
        print("ERROR: cap must be >= 1")
        return 1
    old = data.get("active_cap")
    data["active_cap"] = args.n
    _write(data)
    _log("set_cap", "-", "old=" + str(old) + " new=" + str(args.n))
    print("active_cap:", old, "->", args.n)
    return 0


def _require_capacity(data, symbol):
    """Returns (ok, error_msg, swap_candidates)."""
    act = _active(data)
    cap = int(data.get("active_cap", 50))
    if symbol in act:
        return True, None, []
    if len(act) < cap:
        return True, None, []
    # need to drop one
    low_rank = sorted(data["approved"], key=lambda e: e.get("rank", 9999),
                      reverse=True)
    cands = [e["symbol"] for e in low_rank if e["symbol"] in act]
    return False, ("active set is full (" + str(cap) + "). Use --drop SYM.",
                   ), cands[:10]


def cmd_approve(args):
    symbol = _n(args.symbol)
    data = _read()

    if _find(data["approved"], symbol):
        print(symbol, "is already approved. Use 'reactivate' if inactive.")
        return 0

    if _find(data["disapproved"], symbol) and not args.force:
        print("ERROR:", symbol, "is disapproved. Use --force to override.")
        return 1

    if args.drop:
        drop_sym = _n(args.drop)
        if not _find(data["approved"], drop_sym):
            print("ERROR: --drop", drop_sym, "is not in approved list.")
            return 1
        if drop_sym == symbol:
            print("ERROR: cannot drop the symbol you're approving.")
            return 1
        _drop_approved_to_inactive(data, drop_sym)
        print("Dropped to inactive:", drop_sym)

    ok, msg, cands = _require_capacity(data, symbol)
    if not ok:
        print("ERROR:", msg)
        print("Lowest-ranked active coins you could drop with --drop:")
        for c in cands:
            print("   ", c)
        return 1

    pend = _find(data["pending"], symbol)
    rank = pend.get("rank") if pend else 999
    data["approved"].append({
        "symbol": symbol,
        "rank": rank,
        "approved_at": _now(),
        "tags": [],
        "note": "manual" if not pend else (
            "reactivation" if pend.get("reactivation") else "approved from pending"
        ),
    })
    data["pending"] = [e for e in data["pending"] if e["symbol"] != symbol]
    dis = _find(data["disapproved"], symbol)
    if dis:
        data["disapproved"] = [e for e in data["disapproved"]
                               if e["symbol"] != symbol]
        _log("approve_force", symbol, "was disapproved:" + str(dis.get("reason")))
    _write(data)
    _log("approve", symbol, "rank=" + str(rank))
    print("Approved:", symbol)
    return 0


def cmd_reactivate(args):
    symbol = _n(args.symbol)
    data = _read()
    if not _find(data["approved"], symbol):
        print("ERROR:", symbol, "not in approved list — use 'approve' instead.")
        return 1
    args.force = False
    return cmd_approve(args)


def cmd_disapprove(args):
    symbol = _n(args.symbol)
    if not args.reason:
        print("ERROR: --reason required.")
        return 1
    data = _read()
    data["disapproved"] = [e for e in data["disapproved"]
                           if e["symbol"] != symbol]
    data["disapproved"].append({
        "symbol": symbol,
        "reason": args.reason,
        "disapproved_at": _now(),
    })
    data["approved"] = [e for e in data["approved"]
                        if e["symbol"] != symbol]
    data["pending"] = [e for e in data["pending"]
                       if e["symbol"] != symbol]
    _write(data)
    _log("disapprove", symbol, "reason=" + args.reason)
    print("Disapproved:", symbol, "—", args.reason)
    return 0


def cmd_move(args):
    symbol = _n(args.symbol)
    target = args.target.lower()
    if target not in ("approved", "disapproved"):
        print("ERROR: target must be 'approved' or 'disapproved'.")
        return 1
    data = _read()
    src_list = "approved" if target == "disapproved" else "disapproved"
    entry = _find(data[src_list], symbol)
    if not entry:
        print("ERROR:", symbol, "not in", src_list, "list.")
        return 1
    data[src_list] = [e for e in data[src_list] if e["symbol"] != symbol]
    if target == "approved":
        data["approved"].append({
            "symbol": symbol,
            "rank": entry.get("rank", 999),
            "approved_at": _now(),
            "tags": [],
            "note": "moved from disapproved (forced)",
        })
    else:
        data["disapproved"].append({
            "symbol": symbol,
            "reason": entry.get("reason", "moved"),
            "disapproved_at": _now(),
        })
    data["pending"] = [e for e in data["pending"] if e["symbol"] != symbol]
    _write(data)
    _log("move", symbol, src_list + "->" + target)
    print("Moved", symbol, "from", src_list, "to", target)
    return 0


def cmd_stage_list(args):
    data = _read()
    staged = data.get("staged", [])
    if not staged:
        print("No staged symbols.")
        return 0
    for e in staged:
        print(e.get("symbol", "?"), "rank=" + str(e.get("rank", "?")))
    return 0


def cmd_promote(args):
    """Move a staged symbol back into approved."""
    symbol = _n(args.symbol)
    data = _read()
    staged = data.get("staged", [])

    entry = None
    for e in staged:
        if e["symbol"] == symbol:
            entry = e
            break
    if entry is None:
        print("ERROR:", symbol, "not in staged list.")
        return 1

    if _find(data["approved"], symbol):
        print(symbol, "already approved. Removing from staged.")
        data["staged"] = [e for e in staged if e["symbol"] != symbol]
        _write(data)
        return 0

    data["approved"].append({
        "symbol": symbol,
        "rank": entry.get("rank", 999),
        "approved_at": _now(),
        "tags": [],
        "note": "promoted from staged",
    })
    data["staged"] = [e for e in staged if e["symbol"] != symbol]
    _write(data)
    _log("promote", symbol, "")
    print("Promoted:", symbol)
    return 0


# ------------------------------------------------------------

def _parser():
    p = argparse.ArgumentParser(prog="section_1_11_symbol_verifier")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("status")
    sub.add_parser("list-pending")

    sc = sub.add_parser("set-cap"); sc.add_argument("n", type=int)

    sub.add_parser("stage-list")

    pp = sub.add_parser("promote")
    pp.add_argument("symbol")

    ap = sub.add_parser("approve")
    ap.add_argument("symbol")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--drop")

    ra = sub.add_parser("reactivate")
    ra.add_argument("symbol")
    ra.add_argument("--drop")

    dp = sub.add_parser("disapprove")
    dp.add_argument("symbol")
    dp.add_argument("--reason", required=True)

    mv = sub.add_parser("move")
    mv.add_argument("symbol")
    mv.add_argument("target", choices=["approved", "disapproved"])

    return p


def main(argv=None):
    args = _parser().parse_args(argv)
    fn = {
        "status": cmd_status,
        "list-pending": cmd_list_pending,
        "set-cap": cmd_set_cap,
        "approve": cmd_approve,
        "reactivate": cmd_reactivate,
        "disapprove": cmd_disapprove,
        "move": cmd_move,
        "stage-list": cmd_stage_list,
        "promote": cmd_promote,
    }[args.cmd]
    return fn(args)


if __name__ == "__main__":
    sys.exit(main())
