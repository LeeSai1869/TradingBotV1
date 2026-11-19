# Visible lag and app logout

13 November 2026. The earlier scheduling correction was insufficient for recent
updates on non-owner coins. This review distinguishes that regression from
indicator formulas and from browser rendering.

## Observed failure

At 20:12 PKT, BTC 1h features matched its 19:00 candle. ETH, SUI, ENA and many
other 1h feature checkpoints remained at 15:00 while their downloaded candles
already extended through 19:00. Several retained a history cursor at
15:00:00.001 even though all intervening closed candles were present.

The focused history change admitted deep source paging only for BTC. Those
recent interruption cursors therefore stayed in place. The feature worker
correctly refused to cross the recorded source prefix, but the recent-only
scheduler also rejected tails longer than twelve bars. Current prices could
advance while features, decisions and forming-candle previews stayed behind.

This was a scheduling/recovery regression, not evidence that the indicator
formulas had become faster or that downloaded MAX timestamps proved readiness.

## Correction

- Verify a contiguous stored closed-candle path before advancing a recent
  interruption cursor. A real missing candle keeps the cursor and blocks later
  feature progress. MAX(open_time) is never used alone to fast-forward it.
- Permit one bounded recent-gap fetch on any active coin. Deep historical
  network paging remains with the bulk owner.
- Recover recent feature and decision tails in bounded batches, even when the
  interruption exceeds twelve candles. The recovery window is the greater of
  one day and twelve source intervals; older large backlogs keep their explicit
  historical/repair status. Pending selective repairs are not bypassed.
- Retain BTC's deep history focus while servicing recent calculations first.
  Existing formulas and the BTC 1h feature signature/generation are unchanged.
- While recent features are recovering, lend the historical analytical time
  slice to one additional bounded recent-feature pass. Historical research
  resumes when that recent work goes quiet; live analytical/decision service
  remains available.

The chart also polled a 1,000-candle window every twelve requests even when
features were current. A measured BTC 1h response was 30,856,206 bytes; its
two-candle edge response was 58,808 bytes. Healthy charts now use edge polling.
Historical refresh remains available for active repairs, once after repair
completion, explicit opportunity settings changes and manual reloads. Failed
or queued full refresh requests are retained.

## Logout behavior

Chart sign-out revokes the account session. It does not pause the data policy,
stop the runner, or disable downloads/calculations. The runner is a separate
background service and does not depend on authenticated browser sessions.

The signed-out browser does not mount/poll the chart. Forming-candle previews
are requested by chart/live-alert consumers; they are distinct from permanent
closed-candle processing. This app-logout behavior does not imply that the
computer can calculate while asleep or powered off.

## Verification

93 targeted backend tests passed for source recovery, decisions, scheduler
fairness, live previews and feature-runtime behavior. A final 33-test subset
passed after adding pre-fetch cursor reconciliation and exercising feature
recovery after app logout. The standalone Node regression covers healthy edge
polling, active repair, repair completion, explicit settings refresh, history
navigation and failed-request retry.

A broader legacy conversion suite still encounters pre-existing deleted
`conversion/kernels.py` and `conversion/validate_export.py` files and an outdated
feature-packet golden hash; those were not changed to make this correction pass.
No production feature/ADCN data was deleted or rebuilt.

The existing approved runner restart loads the backend correction. Reloading
the chart page loads the lighter polling code. Formula-parity and preview
Section_13_Development/tests do not establish that every older selective-repair backlog is complete.

At 20:30 PKT after activation, BTC, SUI, ENA and ETH 5m and 1h feature
checkpoints matched their latest downloaded closed candles. The runner retained
BTC as bulk owner and produced no new error-log output in the observation
window. Some other scopes still had older historical tails or selective repairs;
those remain explicitly pending. The
[verification snapshot](../Section_12_Research/reports/visible_lag_fix_20261113/verification.json)
preserves all 400 inspected scopes and the measured polling payload sizes.
