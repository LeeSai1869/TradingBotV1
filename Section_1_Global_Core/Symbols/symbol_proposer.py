# ============================================================
# section_1_10_symbol_proposer.py — v5
# ============================================================
#
# Rule:
#   eligible = top-50 by market cap that pass filters
#     - on Binance USDT spot, status TRADING
#     - not stablecoin / RWA / meme (hardcoded blocklists)
#     - well-formed symbol
#   active = approved ∩ eligible  (capped at active_cap)
#   veto  -> next eligible promotes automatically
#
# Pages CoinGecko 250 at a time until 50 eligible found.
# ============================================================

from __future__ import annotations

import datetime as _dt
import json
import re
import subprocess
import sys
import urllib.request
from pathlib import Path
from Section_1_Global_Core import data_policy


_DIR = Path(__file__).resolve().parent
_JSON = _DIR / "symbols.json"
_ENV = _DIR / ".env"

_CG_BASE = ("https://api.coingecko.com/api/v3/coins/markets"
            "?vs_currency=usd&order=market_cap_desc&per_page=250&page=")
_BN_URL = "https://api.binance.com/api/v3/exchangeInfo"

_SYMBOL_RE = re.compile(r"^[A-Z0-9]{2,15}$")

TARGET_ELIGIBLE = 50
MAX_PAGES = 4

_STABLES_AND_RWA = {
    "USDC","USDT","DAI","FDUSD","TUSD","USDP","BUSD","USDD","PYUSD",
    "GUSD","USTC","FRAX","USDS","USDE","USD1","USDG","RLUSD","USYC",
    "USDY","BUIDL","USDF","USDX","USR","SUSD","MIM","LUSD",
    "XAUT","PAXG",
    "BFUSD",  # Binance futures USD — stablecoin
}
_MEMES = {
    "DOGE","SHIB","PEPE","WIF","BONK","FLOKI","PUMP","MOG","BRETT",
    "POPCAT","BOME","MEW","TRUMP","FARTCOIN","PNUT","ACT","NEIRO","GOAT",
}


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


def _key():
    for line in _ENV.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("COINGECKO_API_KEY="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise RuntimeError("COINGECKO_API_KEY not in .env")


def _fetch_cg_page(api_key, page):
    req = urllib.request.Request(_CG_BASE + str(page), headers={
        "x-cg-demo-api-key": api_key,
        "User-Agent": "ScalpV1-Proposer/5.0",
    })
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _fetch_binance_usdt_pairs():
    req = urllib.request.Request(_BN_URL, headers={
        "User-Agent": "ScalpV1-Proposer/5.0",
    })
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return {
        s["symbol"] for s in data.get("symbols", [])
        if s.get("quoteAsset") == "USDT" and s.get("status") == "TRADING"
    }


def _notify(title, msg):
    try:
        script = ('display notification "' + msg.replace('"', "'")
                  + '" with title "' + title.replace('"', "'") + '"')
        subprocess.run(["osascript", "-e", script], check=False)
    except Exception:
        pass


def _classify(raw, bsym, bn_pairs):
    """Return (kind, reason) where kind in {'skip','eligible'}."""
    if not _SYMBOL_RE.match(raw):
        return "skip", "malformed"
    if bsym not in bn_pairs:
        return "skip", "not_on_binance"
    if raw in _STABLES_AND_RWA:
        return "skip", "auto:stablecoin"
    if raw in _MEMES:
        return "skip", "auto:meme"
    return "eligible", None


def propose():
    api_key = _key()
    bn_pairs = _fetch_binance_usdt_pairs()

    eligible: list[dict] = []
    skipped_counts = {"malformed": 0, "not_on_binance": 0,
                      "auto:stablecoin": 0, "auto:meme": 0}

    pages_fetched = 0
    for page in range(1, MAX_PAGES + 1):
        coins = _fetch_cg_page(api_key, page)
        if not coins:
            break
        pages_fetched += 1
        for coin in coins:
            raw = (coin.get("symbol") or "").upper()
            bsym = raw + "USDT" if raw else ""
            kind, reason = _classify(raw, bsym, bn_pairs)
            if kind == "skip":
                skipped_counts[reason] = skipped_counts.get(reason, 0) + 1
                continue
            eligible.append({
                "symbol": bsym,
                "rank": coin.get("market_cap_rank"),
                "market_cap_usd": coin.get("market_cap"),
                "coingecko_id": coin.get("id"),
                "name": coin.get("name"),
            })
            if len(eligible) >= TARGET_ELIGIBLE:
                break
        if len(eligible) >= TARGET_ELIGIBLE:
            break

    eligible = eligible[:TARGET_ELIGIBLE]

    data = _read()
    approved = {e["symbol"] for e in data["approved"]}
    dis_by_sym = {e["symbol"]: e for e in data["disapproved"]}
    pend_by_sym = {e["symbol"]: e for e in data["pending"]}

    new_n = 0
    react_n = 0

    for ent in eligible:
        bsym = ent["symbol"]
        if bsym in dis_by_sym or bsym in approved or bsym in pend_by_sym:
            continue

        # New entrant into eligible set
        data["pending"].append({
            "symbol": bsym,
            "reactivation": False,
            "rank": ent["rank"],
            "market_cap_usd": ent["market_cap_usd"],
            "coingecko_id": ent["coingecko_id"],
            "name": ent["name"],
            "categories": [],
            "proposed_at": _now(),
        })
        new_n += 1

    eligible_syms = {e["symbol"] for e in eligible}
    prev_eligible_syms = {e["symbol"] for e in data.get("top50", [])}

    # Reactivations: approved coin now in eligible, wasn't in eligible last run
    for sym in sorted(approved):
        if sym in eligible_syms and sym not in prev_eligible_syms \
                and sym not in pend_by_sym:
            data["pending"].append({
                "symbol": sym,
                "reactivation": True,
                "rank": next((e["rank"] for e in eligible
                              if e["symbol"] == sym), None),
                "market_cap_usd": None,
                "coingecko_id": None,
                "name": None,
                "categories": [],
                "proposed_at": _now(),
            })
            react_n += 1

    active_n = len([s for s in approved if s in eligible_syms])
    active_cap = int(data.get("active_cap", 50))

    for e in data["pending"]:
        e["requires_swap"] = (
            (not e.get("reactivation")) and active_n >= active_cap
        )
        e["swap_candidates"] = []

    data["top50"] = [
        {"symbol": e["symbol"], "rank": e["rank"]} for e in eligible
    ]
    _write(data)

    print("Proposer run complete.")
    print("  pages fetched            :", pages_fetched)
    print("  eligible (filtered top)  :", len(eligible))
    print("  skipped malformed        :", skipped_counts.get("malformed", 0))
    print("  skipped not_on_binance   :", skipped_counts.get("not_on_binance", 0))
    print("  skipped stablecoin       :", skipped_counts.get("auto:stablecoin", 0))
    print("  skipped meme             :", skipped_counts.get("auto:meme", 0))
    print("  active set               :", active_n, "/", active_cap)
    print("  new pending              :", new_n)
    print("  reactivation pending     :", react_n)
    print("  total pending now        :", len(data["pending"]))

    if new_n + react_n > 0:
        _notify(
            "Global Core — symbol approval needed",
            str(new_n + react_n) + " pending. Run: "
            "python3 -m Section_1_Global_Core.Symbols.symbol_verifier list-pending",
        )
    return 0


if __name__ == "__main__":
    sys.exit(propose())
