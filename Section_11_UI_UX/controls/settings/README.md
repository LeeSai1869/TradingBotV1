# Settings structure

The top-right gear opens one modal with top-level tabs, category navigation on
its left, and the selected category's controls on its right. Escape or Cancel
discards edits; Apply stores chart preferences in this browser. Tabs support
arrow keys, Home and End. The native dialog traps focus and restores it on close.

Connected controls:
- General: stored flags panel and BUY/SELL marker visibility.
- Candles: candle and current-price-line visibility.
- Features > EMA: visibility, periods 7/25/50/100/200/300, independent color, width and
  solid/dotted/dashed style per output. Values come from the existing combined bar stream.

Settings apply through Composer and the existing render coordinator, preserving
market selection, cached history and viewport. Preferences use the versioned
`tradingbot.chart-settings.v1` localStorage key. They do not modify calculations.

Features have Display and Style submenus. `feature_styles.js` declares each
output's identity, default color and presentation (line or histogram). The same
row builder renders each output independently. RSI, ADX (+DI, -DI, spread,
direction), ATR, Volume and VWAP already expose saved style preferences, but
their visibility switches stay disabled until their renderers are connected.
Histogram outputs have color and disable line-only controls. Adding an output
requires a catalog entry and connecting its renderer to `config.featureStyles`.
Existing shared EMA preferences migrate to independent rows without changing
the selected periods or saved styling; styles are retained when hidden.

Inputs reserve space for later connections. Timeframes now have immediate
Active/Inactive controls and administrator-only Delete data. Inactive keeps data.
Delete requires typing the exact scope, pauses it, and deletes raw candles,
features and decisions without removing the setting/registry entry. Re-activation
bootstraps history from Binance a page per runner cycle, then computes features.

General > Account provides local login. No default passwords exist. Before using
policy controls after updating, restart the runner and UI server, then provision:

```bash
python3 -m Section_11_UI_UX.server.auth
```

This prompts privately for separate `admin` and `user` passwords (12 characters
minimum). Salted PBKDF2 hashes live at `~/.tradingbot/users.json` (mode 600), outside
the served repository. Never commit/copy that file. Re-running provisioning
resets both passwords; restart the UI server afterward to clear old sessions.
Browser sessions expire after eight hours and are HttpOnly, SameSite=Strict.
Requests changing policy are checked on the backend. The UI server remains a
loopback service, not an externally hosted authentication service.

| Role | Chart preferences | Timeframe Active/Inactive | Coin approvals/status | Delete data |
|---|---|---|---|---|
| Signed out | Yes | No | No | No |
| user | Yes | Yes | No | No |
| admin | Yes | Yes | Yes | Yes, typed confirmation |

Coin changes apply immediately; they are independent of Apply/Cancel for chart
styles. Approved/active means approved, not manually paused, within the eligible
top50 and active cap. Inactive includes manual pauses, rank drops and cap overflow.
Administrators can approve/activate eligible candidates, pause approved coins,
and disapprove them. Ineligible, Pending and Staged follow registry rules; these
are not arbitrary manual destinations. An ineligible coin cannot be activated.
Deletion preserves its current registry entry. Reactivate it via Approve/activate
when eligible, or select Active for the relevant timeframe. Other inactive
scopes remain inactive; activating a timeframe does not override paused coins.

Core `data_policy.py` is shared by ingestion, processing and admin operations.
Policy persists in ignored `runtime_policy.json`. New code must be running in
both server and runner; an already running old runner does not reload Python
source after git pull. `bash restart_runner.sh` restarts the launchd runner.
Avoid parallel legacy writer processes. All deployed writer entry points must
use the new policy/coordination code before using deletion.

Deletion and writer batches use one cross-process lock; three-store deletes use
one attached SQLite transaction. Failed deletes leave the scope paused. Epochs
cancel stale catch-up writes and reset runner cursors/transient feature state
on replay. Chart windows invalidate cached rows when a changed epoch is observed
on their next refresh/history request. Historical browsing still pauses polling.
Normal integrity audits retain inactive history; freshness audits skip inactive
pairs. Audit logs and registry history are preserved.

Initial chart framing shows 200 candles and eight bars of right padding; the
active cache remains 1000, with older buffered pages. EMA uses the standard
`ewm(span=length, adjust=False)` formula and straight line segments. It is not
additionally smoothed. The current feature engine uses a 500-bar warmup window,
which can differ from a full-history EMA, particularly for EMA300. Formula and
warmup changes should be reviewed independently, rather than hiding differences
with visual interpolation.

The chart status `waiting for stored bar` means a live snapshot is ahead of the
last locally stored closed candle. It does not indicate whether features are
running. The UI server and feature runner are separate processes. From the
project root, inspect `launchctl list | grep com.scalp.liverunner`. If launchd
already runs it, use `bash restart_runner.sh`. Otherwise, start it in another
terminal with `python3 -u -m Section_1_Global_Core.memory_storage.Runner.live_runner`.
Keep that terminal open and inspect processor/catch-up messages. Do not run two
writers. A desktop UI launcher need not start the runner.
