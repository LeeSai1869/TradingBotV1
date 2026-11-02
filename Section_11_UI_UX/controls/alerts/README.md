# Notifications and Sounds

These are separate **top-level Settings tabs**, alongside Features, Candles,
Timeframes and Coins. They are not chart features.

## Notifications

Use **Settings → Notifications → Allow desktop notifications** to grant browser/OS
permission. Previously denied permission must be changed in the browser site
settings and macOS System Settings → Notifications.

The toolbar **Notifications: on/off** button only toggles desktop delivery. It
does not open a menu or pause calculations. The Settings page has one custom-rule
list and one **New notification** button, plus the automatic BUY/SELL switches.
Existing custom rows have an enabled checkbox, Edit and Remove. The rule editor
supports searchable numeric fields, BUY/SELL presets, comparisons, crossings and
once/per-candle frequency. No intermediate rule-manager window is needed.
Recent activity stays collapsed and shows ten compact entries with details.

**Settings → Timeframes** puts Desktop and Mobile notification switches beside
status. **Settings → Coins** has the same switches per coin. Desktop delivery
requires the master switch AND the timeframe AND the coin to allow it. Switching
off Desktop suppresses OS popups and in-app toasts for that scope. It does not
change downloads, calculations, sound choices or durable activity recording.
Mobile is disabled and explicitly deferred; no mobile push service is installed.
Notification switches are per account; download policy retains its admin checks.

## Sounds

All tone controls live only in **Settings → Sounds**. Click **Enable sound** after
opening the app. Choose Silent to mute BUY, SELL or a custom rule. Local volume,
built-in tones and previews are here too. Delivery settings save immediately;
Apply remains for chart preferences. New custom rules start silent.

Under **Your sounds**, choose an audio file, preview it, name it and click
**Add sound**. Select it from a BUY/SELL or custom-rule dropdown. Your uploads are
stored privately in the account's alerts database and remain after reopening the
app. Delete removes the upload and sets references to Silent without re-arming
rules or resetting their cursors. Supported headers: WAV, MP3, OGG, FLAC and M4A;
the browser must also be able to decode the selected file. The UI limits clips to
30 seconds; the server enforces 2 MB per upload and 10 files / 10 MB per account.
Custom playback uses Web Audio with the same gesture requirement as built-ins.

## Operation

Automatic monitoring reads current committed DI_TURNING_POINT_V3 decisions on
all active pairs, independently of chart selection. Missing rows wait; WAIT rows
advance. Durable IDs deduplicate rule/epoch/candle events. Download/calculation
lag also means alert lag. No old downloaded history is announced as a new signal.

App logout does not stop independent calculation/recording services. Browser
sound/notifications still require an open, signed-in app. Reopening shows history
without replaying old sounds. Existing login agents stop at macOS logout; see
SERVER_MODE.md for reviewed system-service exports. No phone services or system
jobs are installed by a code update.

Rules, preferences, uploads and events live in ~/.tradingbot/alerts.sqlite3,
separate from all market databases. Cross-account access and assignment of another
account's custom sound are rejected. Only the authenticated sound-upload endpoint
accepts a larger JSON body; ordinary API requests retain their prior size limit.
