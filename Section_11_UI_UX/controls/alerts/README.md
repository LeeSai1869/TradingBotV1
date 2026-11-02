# Notifications and sounds

The toolbar **Notifications** button opens **Settings → Features → Notifications**.
Use **Allow desktop notifications** there. Permission state and errors are visible.
If permission was denied, change the browser site permission and macOS System
Settings → Notifications. Browser delivery requires an open, signed-in app;
it cannot show notifications in a closed macOS session.

**Features → Sounds** owns all tones and local volume. Click **Enable sound**
after opening the app, then test BUY, SELL or a custom rule. Choose **Silent**
to mute an item. Sound controls no longer appear in Momentum or the custom-rule
editor. Delivery settings save immediately; Apply remains for chart preferences.
New custom rules start silent until assigned a tone on Sounds.

Automatic monitoring follows every active symbol/timeframe regardless of chart
visibility. Notifications has monitoring, desktop signal and individual BUY/SELL
notification switches. Muting a notification does not mute its sound. Disabling
monitoring stops both automatic delivery types. Evaluation reads current committed
DI_TURNING_POINT_V3 decisions; missing rows wait, WAIT rows advance. New pairs and
re-armed subscriptions do not announce old downloaded history. Durable event IDs
deduplicate each rule/dataset epoch/candle.

**Add / edit / delete custom notifications** opens the rule manager. It supports
searchable fields, BUY/SELL presets, numeric comparisons/crossings and repeat
frequency. Each custom notification toggle/deletion is also available directly on
Notifications; its tone is on Sounds. Activity is collapsed, with ten compact
entries and expandable details. Clearing displayed activity leaves stored events.

App logout does not stop the independent runner, recorder or backend alert worker.
The backend must remain running to record events. Reopening the app shows history
without replaying old sounds. Existing macOS login agents stop at macOS logout;
see SERVER_MODE.md for system-service exports. No system jobs or phone-push
services are installed by a repository update.

Live rules use sampled price/EMA/RSI; brief excursions may be missed. Other rules
wait for stored closed features/decisions, so calculation/download lag means alert
lag. Rules/preferences/events are account-owned in ~/.tradingbot/alerts.sqlite3,
separate from all market memories. Cross-account access is rejected.
