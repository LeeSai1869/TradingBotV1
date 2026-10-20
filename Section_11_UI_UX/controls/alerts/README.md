# Alerts

The toolbar Alerts button opens an account-owned rule editor and recent activity.
Both normal users and administrators can manage their own alerts. Other users'
rules/events cannot be read, edited or deleted through the API.

Choose a registered coin, timeframe, field, condition, numeric threshold or
comparison field, frequency, notification flag and sound. Supported conditions
are above, at/above, below, at/below, exact equality and crossings in either
direction. Signed thresholds and comparisons such as +DI > -DI are supported.

Two evaluation modes:
- Live candle: high, low and close from the existing shared backend live feed.
  Features cannot be selected in this mode. A crossing needs two observed
  snapshots; a level condition can trigger on the first available snapshot.
- Closed candle / stored features: candle fields and every numeric permanent
  features-store field, including ADX, DI direction/spread, RSI, EMA, ATR, etc.
  Feature-dependent rules wait for stored features. No mutable decision-memory
  fields are exposed. Unsupported/null feature values do not create alerts.

Examples:
- ETHUSDT / 1m / live / candle high / crosses above / a chosen price.
- BTCUSDT / 15m / closed / +DI / crosses above / comparison field -DI.
- BTCUSDT / 1h / closed / RSI / below / 30.

The local UI backend evaluates enabled rules on a worker thread independently of
chart selection, historical navigation and browser polling. Keep that backend
and the runner running. Events persist in ~/.tradingbot/alerts.sqlite3, separate
from all three market memories. A restarted backend resumes rules/cursors.
Closed rules start with newly closed candles after creation or edit; historical
bootstrap does not trigger new alerts. Dataset deletion/rebuild and resuming an
inactive scope re-arm closed rules from the current time rather than replaying
paused history. Inactive coins/timeframes suspend evaluation.

Once pauses a rule after its first match. Re-arm/edit seeds a new baseline.
Per candle allows at most one event per rule, dataset epoch and candle; repeated
polls and crossings within the same candle do not duplicate an alert. Editing a
live rule does not allow another event on a candle that already fired. Events
retain the fired rule description even after the rule is edited/deleted.

Live evaluation uses approximately one-second sampled snapshots, not a tick
stream: a brief close-price excursion between samples can be missed. High/low
rules are useful for detecting retained candle extremes. Closed rules are
checked after local ingestion/feature calculation, so download/compute lag also
means alert lag. No old EMA, RSI, DI or ADX value is substituted for missing data.

Delivery uses in-app toasts/activity and optional browser/system notifications.
Click Enable notifications and sound to grant permission and unlock Web Audio.
Three built-in tones (Chime, Bell, Alarm) and None are selectable per rule; a
per-account volume control and Test selected sound are provided. Simultaneous
tones are queued (up to 20); at most five toasts appear at once, while activity
keeps the events. Sound also
unlocks when saving a rule. User audio-file imports can be added to the sound
catalog later; this version does not upload/download external sound files.

Keep the app open and signed into the owning account for sound/notification
delivery. Background tabs still poll, subject to OS/browser suspension. System
notifications depend on WebView/browser support and permission; in-app activity
works without them. Backend events continue while the backend runs, but reopening
the app loads recent activity without replaying stale alarms. The sound catalog
is extensible; oscillator presets are in index.js and the backend validates IDs.

The API enforces account ownership, JSON validation, a 50-rule/account limit,
finite numeric thresholds, supported fields, mode compatibility and same-origin
writes. Evaluation uses revision checks inside a SQLite write transaction so an
old worker snapshot cannot fire an edited/deleted rule. Data-policy locking and
storage epochs prevent stale post-deletion closed-bar evaluation.
