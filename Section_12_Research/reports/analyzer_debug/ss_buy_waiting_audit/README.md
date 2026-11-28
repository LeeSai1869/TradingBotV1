# SS BUY waiting-candle audit

Input: Mac diagnostic commit 8e179893a, ENAUSDT 15m stored source and saved
SS BUY report from 20261128-174837. Replayed the saved configuration without
changing thresholds, stages, fees, stops, or candle ordering. All 62 trades and
accepted signals were reproduced identically.

Exactly 102 waiting candle evaluations were reproduced, all ACTIVATION_FALSE.
50 occurred on the trigger candle itself; 52 occurred on later candles. These
are repeated evaluations across 62 setups, not 102 distinct setups. Candle ages
since trigger: 0:50, 1:24, 2:11, 3:6, 4:5, 5:2, 6:1, 7:1, 8:1, 9:1.

Example: 2026-11-21 04:15–04:30 UTC. Previous RSI=10.051872674133179,
current RSI=9.12368664654204. The activation predicate previous RSI < current
RSI is false. DI− and spread decline predicates are both true. The AND group
therefore waits at that close. This is the same trade previously inspected.

waiting_evidence.json.gz contains all 102 timestamps, prices, original trigger
times, logical predicate paths, numeric operands and PASS/FAIL results. The
new report UI records this evidence during replay and can export it as JSON.
This audit uses the older uploaded data; later Mac runs need their own replay.
