"""HTTP dispatch for /api/* endpoints."""
from __future__ import annotations
import json
from urllib.parse import urlparse, parse_qs

from Section_1_Global_Core.memory_storage.Storage import db
from Section_1_Global_Core import data_policy

from . import queries
from . import live_candle, admin_routes
from .settings_catalog import read_coin_catalog

HERE = None
UI_CONFIG = None


def clean(v):
    if v is None:
        return None
    return v.split("?", 1)[0]


def _int(qs, name, default=None):
    v = qs.get(name, [None])[0]
    if v is None:
        return default
    try:
        return int(v)
    except ValueError:
        return default


def handle_get(path, raw_qs, server):
    status, payload = admin_routes.handle_get(path, server)
    if status is not None:
        return status, payload
    qs = parse_qs(raw_qs)
    for k in list(qs.keys()):
        qs[k] = [clean(x) for x in qs[k]]

    if path == "/api/bars":
        symbol = qs.get("symbol", [None])[0]
        interval = qs.get("interval", [None])[0]
        try:
            limit = int(qs.get("limit", ["1000"])[0])
            before = int(qs["before"][0]) if "before" in qs else None
        except ValueError:
            return 400, {"error": "limit and before must be integers"}
        if not symbol or not interval or not 1 <= limit <= 1000:
            return 400, {"error": "symbol, interval and limit between 1 and 1000 required"}
        with data_policy.locked():
            epochs = data_policy.read()['epochs']
            packet = {"symbol": symbol, "interval": interval,
                      "storage_epoch": f"{epochs.get(f'symbol:{symbol}', 0)}:{epochs.get(f'interval:{interval}', 0)}",
                      **db.read_state_page(symbol, interval, limit, before=before)}
            active = data_policy.enabled(symbol, interval)
        if before is None and qs.get("live", ["0"])[0] == "1":
            packet["live"] = live_candle.get_snapshot(symbol, interval) if active else {
                "bar": None, "status": "inactive", "as_of": None, "error": None}
        return 200, packet

    # ---- complete chart window ----
    # One browser request returns every range-bound dataset required
    # to render the same chart window.
    if path == "/api/chart_window":
        symbol = qs.get("symbol", [None])[0]
        interval = qs.get("interval", [None])[0]
        start = _int(qs, "start")
        end = _int(qs, "end")

        if not symbol or not interval or start is None or end is None:
            return 400, {
                "error": "symbol, interval, start, end required"
            }

        # One Central Core read produces the complete canonical state
        # for this chart window. Klines own the timeline; features and
        # ADCN are already aligned by (symbol, interval, open_time).
        state = db.read_state_range(symbol, interval, start, end)

        klines = []
        features = []
        flags_history = []

        for bar in state:
            client = bar["client"]

            klines.append({
                "time": int(bar["open_time"]) // 1000,
                "open": client["open"],
                "high": client["high"],
                "low": client["low"],
                "close": client["close"],
                "volume": client["volume"],
            })

            feature = bar["features"]
            if feature is not None:
                features.append({
                    "time": int(bar["open_time"]) // 1000,
                    "ema50": feature.get("ema50"),
                    "ema200": feature.get("ema200"),
                })

            adcn = bar["adcn"]
            if (
                adcn is not None
                and adcn.get("signal_type") in ("BUY", "SELL")
            ):
                flags_history.append({
                    "symbol": bar["symbol"],
                    "tf": bar["interval"],
                    "bar_time": int(bar["open_time"]),
                    "signal_type": adcn["signal_type"],
                    "final_score": float(adcn.get("final_score") or 0.0),
                })

        return 200, {
            "symbol": symbol,
            "interval": interval,
            "start": start,
            "end": end,
            "klines": klines,
            "features": features,
            "flags_history": flags_history,
        }

    if path == "/api/flags_current":
        symbol = qs.get("symbol", [None])[0]
        interval = qs.get("interval", [None])[0]
        if not symbol or not interval:
            return 400, {"error": "symbol and interval required"}
        return 200, queries.get_flags_current(symbol, interval)

    # ---- symbols ----
    if path == "/api/symbols":
        return 200, {"symbols": queries.get_symbols()}

    if path == "/api/settings/coins":
        try:
            return 200, read_coin_catalog()
        except (OSError, ValueError, KeyError, TypeError):
            return 503, {"error": "Coin registry is unavailable"}

    if path == "/api/symbol_meta":
        symbol = qs.get("symbol", [None])[0]
        if not symbol:
            return 400, {"error": "symbol required"}
        # Compatibility endpoint; price formatting now comes from stored
        # bars/config in the UI. Never contact an exchange for chart metadata.
        precision = read_ui_config().get("price_precision", {}).get(symbol, 2)
        return 200, {"precision": precision, "tickSize": 10 ** -precision}

    # ---- live candle ----
    if path == "/api/live_candle":
        symbol = qs.get("symbol", [None])[0]
        interval = qs.get("interval", [None])[0]
        if not symbol or not interval:
            return 400, {"error": "symbol and interval required"}
        return 410, {"error": "Use /api/bars?live=1 for combined stored and provisional bars"}

    # ---- ui config ----
    if path == "/api/ui_config":
        return 200, read_ui_config()

    return None, None


def handle_post(path, body, server):
    status, payload = admin_routes.handle_post(path, body, server)
    if status is not None:
        return status, payload
    if path == "/api/ui_config":
        try:
            payload = json.loads(body)
        except Exception as e:
            return 400, {"error": str(e)}
        write_ui_config(payload)
        return 200, {"ok": True}
    return None, None


def read_ui_config():
    global UI_CONFIG
    if UI_CONFIG is None or not UI_CONFIG.exists():
        return {"timeframes": {"all": [], "favorites": []}}
    with open(UI_CONFIG, "r", encoding="utf-8") as f:
        return json.load(f)


def write_ui_config(payload):
    existing = read_ui_config()
    existing["timeframes"] = payload.get("timeframes", existing.get("timeframes", {}))
    tmp = UI_CONFIG.with_suffix(".json.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(existing, f, indent=2)
    tmp.replace(UI_CONFIG)
