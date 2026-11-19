# Buy/sell placement against confirmed native BTC 1h pivots

14 November 2026 (Asia/Karachi). This is a retrospective alignment audit of the executed trades in the fixed bearish +1% target / unchanged bullish trailing study. It does not replay entries or use hindsight pivots as new signals.

An entry is classified by the hourly candle containing its actual BUY time. A SELL is classified by its execution minute/5m bar, rather than an upper timestamp bound that could fall at the next hourly open. The pivot origin candle and the time when that pivot became known are different.

## Main comparison

No optional RSI gate; same low-first execution scenario as the latest headline table. Counts in “next candle” exclude already-counted origin matches. SELL placement uses native pivot HIGHs.

| Strategy | Trades | BUY low candle | BUY next candle | BUY combined | SELL high candle | SELL next candle | SELL combined |
| --- | --- | --- | --- | --- | --- | --- | --- |
| DI− >40, immediate | 336 | 104 | 89 | 193/336 (57.44%) | 29 | 15 | 44/336 (13.10%) |
| DI− >45, immediate | 301 | 90 | 82 | 172/301 (57.14%) | 24 | 14 | 38/301 (12.62%) |
| DI− >50, immediate | 147 | 41 | 43 | 84/147 (57.14%) | 10 | 5 | 15/147 (10.20%) |
| DI− >45, avoid recent crash | 248 | 61 | 75 | 136/248 (54.84%) | 20 | 11 | 31/248 (12.50%) |
| DI− >45, wait micro-high reclaim | 178 | 43 | 64 | 107/178 (60.11%) | 19 | 11 | 30/178 (16.85%) |
| DI− >45 + RSI <20, immediate | 216 | 63 | 49 | 112/216 (51.85%) | 13 | 11 | 24/216 (11.11%) |

## DI− >45 baseline detail

- Executed BUYs near a LOW: **172/301 (57.14%)**. Of these, **0** matched lows had already become confirmed at the BUY time.
- SELLs near a HIGH: **38/301 (12.62%)**. Another 45 sells fall in the hour immediately before a confirmed high; this is separate from the requested high/next category.
- Both ends near any appropriate native pivot: **33** trades. BUY near a native low and SELL near its first strictly later native high: **27** trades.
- BUYs near lows that subsequently had a complete native low→immediate-high move ≥1% gross: **163** trades, capturing **144** distinct qualifying lows.
- There are 12,966 native lows / 12,966 native highs in the frozen trade-origin window, including 8,300 complete ≥1% low→immediate-high swings. These are market-opportunity labels, not trade counts.
- Matched-origin/next entries have median reference entry price **1.048% above** the final hourly pivot low. Being inside that candle does not establish a fill at the bottom.
- Win rate for entries near a native low: 33.72%; other entries: 12.40%. Both retain their original protective stops and exits.

## Confirmation timing

Native pivots in this audit have median origin-open→known delay 2.00 hours. Main placement counts use where the eventual confirmed pivot is drawn. A trade can align with that origin while the confirmation is still in the future. It must not be described as buying an already-known confirmed low.

As a separate definition, the DI− >45 baseline has 28/301 (9.30%) buys in the first hourly candle when a native low is already known or its following candle. This measures post-confirmation placement, not origin/next placement.

## Provenance

The archived native pivots and frozen trade source matched current feature metadata exactly. 25,893 archived native events were reused; only 212 newer hourly event rows were read. No pivot algorithm or parameter was changed.
Pivot labels are observed as of **2026-11-14T17:06:16.350000+05:00**. Trade prices/outcomes remain frozen through **2026-11-13T20:59:59.999000+05:00**. 1 origin-window pivots were confirmed after the trade cutoff and are used only as retrospective labels.
All event prices were checked against frozen hourly highs/lows. Per-trade origin/confirmation matches and all 72 entry variants are retained in pivot_alignment.json. The setup-candle versus actual-fill placement is retained separately; no filter, signal, stop or winning label was changed.
