# Notifications and Sounds

These are separate **top-level Settings tabs**, alongside Features, Candles,
Timeframes and Coins. They are not chart features.

## Notifications

Click **Alerts** in the toolbar to open the alert window with three tabs:

- **Create Alert**: name the alert, choose its coin, timeframe and condition (or
  use a BUY/SELL preset), then click **Create alert**. The selectors start with
  the current chart. Both offer **ALL**, independently or together.
- **Edit Alerts**: view named saved rules, edit them, enable/disable or remove them.
  Saving switches to this tab without closing the window or showing a redirect message.
- **Recent Alert History**: read durable account history for the **Past 24 hours**,
  **Today**, or **Yesterday**. Load additional pages to view the entire period;
  viewing history does not replay notifications or sounds. This tab contains
  user-created alerts only. Automatic Decision Engine BUY/SELL messages remain
  on the live notification/mobile feed and do not appear in custom-alert history.

**ALL** follows active coins and active timeframes with stored/live data, including
newly activated pairs. Inactive markets remain suspended. One ALL rule stays one
editable rule, with independent per-pair cursors, crossing state and deduplication.
**Once** applies once per coin/timeframe; per-bar frequency applies independently
to each matching pair. Editing/removing the parent replaces/removes its private
workers while retaining durable history. The 50-rule account limit counts user rules.

Use **Settings → Notifications → Allow desktop notifications** to grant permission
and enable desktop delivery. The **Desktop notifications** checkbox controls
delivery. Opening the alert editor leaves delivery settings unchanged.
Permission/save/delivery errors are visible.
Previously denied permission must be changed in the browser site settings or
macOS System Settings → Notifications → Trading Indicator.

The Settings page has one custom-rule list and one **New notification** button
that also opens the editor, plus the automatic BUY/SELL switches.
Existing custom rows have an enabled checkbox, Edit and Remove. The rule editor
supports searchable numeric fields, BUY/SELL presets, comparisons, crossings and
once/per-candle frequency. The Settings shortcut opens the same three-tab window.
Its compact recent-activity summary is separate from the full-day history tab.

**Settings → Timeframes** puts Desktop and Mobile notification switches beside
status. **Settings → Coins** has the same switches per coin. Desktop delivery
requires the master switch AND the timeframe AND the coin to allow it. Switching
off Desktop suppresses OS popups and in-app toasts for that scope. It does not
change downloads, calculations, sound choices or durable activity recording.
Mobile stays disabled until the laptop HTTPS/push setup is complete. See MOBILE_SETUP.md for the private 4–5-person setup; no rented server is required.
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

App logout does not stop independent calculation/recording services. Desktop browser
sound/notifications still require an open, signed-in app. Enrolled mobile Web Push works with the phone app closed. Reopening shows history
without replaying old sounds. Existing login agents stop at macOS logout; see
SERVER_MODE.md for reviewed system-service exports. No phone services or system
jobs are installed by a code update.

Rules, preferences, uploads and events live in ~/.tradingbot/alerts.sqlite3,
separate from all market databases. Cross-account access and assignment of another
account's custom sound are rejected. Only the authenticated sound-upload endpoint
accepts a larger JSON body; ordinary API requests retain their prior size limit.


## Rich cards and mobile companion

In-app cards are dismissible with ×, expire after 20 seconds and link to the
original symbol/timeframe/signal candle, including older stored history. Desktop
browser notifications also close after 20 seconds when the browser supports it.
The installed Tauri desktop app sends native system notifications; macOS controls
their lifetime. The desktop shell registers `tauri-plugin-notification` and grants
only notification permission checks, permission requests and delivery to the main
window's local chart origins (localhost/127.0.0.1 on port 8000). Rebuild and replace
the installed app after changing the native shell; reloading the chart alone does
not update native plugins. From `Section_11_UI_UX/app`, run `npm run build -- --bundles app`.
They include signal price, directional confidence /100, nearest resistance upper
edge and nearest support lower edge. These values are captured from matching
anchored evidence; missing context is unavailable, never substituted from another
candle. Recent activity also links to the chart. Phone OS banner lifetime is
controlled by the phone, rather than an unreliable background JavaScript timer.

The companion is at /web_root/mobile.html. Once the private HTTPS address,
optional requirements-mobile.txt and VAPID configuration are ready, users install
it and explicitly enroll their phones. A separate worker performs encrypted Web
Push without blocking calculations or alert evaluation. Subscription ownership,
provider endpoint validation, retry/expiry and device removal are tested. Default
local-only desktop operation needs no mobile setup or additional dependencies.

Live delivery uses a single account event cursor independently of the current chart.
Startup history stays silent. Polling resumes immediately on page restore, return to
foreground/focus, or network reconnection, retaining the cursor so new notifications
are delivered without duplicating past ones. Temporary request failures retry without
advancing the cursor. The Notifications button tooltip reports feed retry errors.
Desktop permission and the existing sound enable/volume preferences still apply.

Regression checks:

```bash
node tests/alert_feed.test.mjs
PYTHONPATH=. python3 tests/browser_alert_delivery.py
```

The browser test uses the actual alert control with mocked API, OS notification and
audio objects. It verifies direct toolbar creation of named price/BUY/SELL alerts,
editing/retry, permission requests in Settings, native and browser BUY/SELL delivery,
visible failures, Settings recovery, unchanged mobile preferences,
and delivery after suspension/restoration or network failure. It does not test macOS
permissions or actual OS banners. Set `CHROMIUM_PATH` to use a local Chrome executable.
