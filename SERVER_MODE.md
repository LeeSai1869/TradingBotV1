# Running this laptop as a local server

App logout does not stop the runner, independent liquidity recorder, or the UI
backend's stored-alert worker. Browser sounds/notifications require an open,
signed-in desktop app. Signal events remain recorded by the backend after app
logout and appear in activity after signing in again. They are not replayed as
old sounds. A phone/native push client is a separate delivery project.

The existing runner/liquidity LaunchAgents start at **macOS login** and stop at
macOS logout. For work after macOS logout and before the GUI session starts, use
system LaunchDaemons running as your normal user. `server_service_config.py`
exports three reviewable property lists; it never installs anything or changes
your system. On the Mac, using the same Python that has project dependencies:

```bash
python3 server_service_config.py --output ./server-launchd
```

Review the files, username, HOME, Python path, project directory and log paths.
Make sure the log directory exists under your account. Verify that this Python
can import the runner, UI server, liquidity recorder, pandas/numpy/requests and
websocket. System services must run as your user, not root. The backend remains
bound to localhost; this does not expose it to the internet.

Installation is a macOS administrator operation, performed on your laptop:

1. Stop the existing login runner/liquidity jobs and existing UI backend. Remove
   their login startup registrations so they cannot compete with system jobs.
   Identify and stop the app's UI startup registration too, if one is installed.
2. Copy the reviewed plists into `/Library/LaunchDaemons/`, owned by `root:wheel`
   with mode `644`. Keep their original filenames.
3. For each reviewed label run `sudo launchctl bootstrap system /Library/LaunchDaemons/LABEL.plist`,
   followed by `sudo launchctl enable system/LABEL` and
   `sudo launchctl kickstart system/LABEL`.
4. Inspect `sudo launchctl print system/LABEL` and its configured logs. Verify a
   single runner, backend and recorder, then test macOS logout/login and reboot.

After switching, restart using `sudo launchctl kickstart -k system/LABEL`, rather
than the login-agent restart scripts. To revert, boot out the system jobs and
remove their system plists before reinstalling the login jobs. Never enable both
copies. No system services are installed by this repository update.

A sleeping or powered-off laptop cannot collect or calculate. FileVault can
prevent access before the first disk unlock after reboot. Home-folder privacy
permissions can also block a daemon; verify on your Mac rather than assuming
boot-time access. For continuous unattended service, an awake always-on machine
is more reliable. No sleep settings, root services or network exposure are
changed automatically.

## Optional idle-sleep prevention

To export the same user-owned system jobs with `caffeinate -i` wrapping each
service, use:

```bash
python3 server_service_config.py --output ./server-launchd --prevent-idle-sleep
```

This only writes reviewable plists. Install them using the steps above on the Mac;
it does not install daemons, request administrator access or change sleep settings
from the development workspace. The assertion lasts while the wrapped service runs.
It prevents **idle system sleep**, while allowing the display to sleep. Explicit
Sleep, lid closure, shutdown and battery exhaustion are not overridden. Closing the
chart window does not stop these KeepAlive services. To stop a service deliberately,
use `sudo launchctl bootout system/LABEL`; killing its process alone restarts it.

After exporting at a new location or choosing a new Python environment, reinstall
the reviewed service files; installed launchd paths do not relocate themselves.
A copied virtual environment is not portable across machines; recreate it there.
Keep source/data and private `~/.tradingbot` configuration separate from distributions.
Never ship Firebase service-account keys to phone users or commit them to Git.

## Diagnose stalled charts and delivery before changing scheduling

On the actual laptop, run these from the project root:

```bash
python3 check_coin.py BTCUSDT --logs
python3 notification_status.py --output notification_readiness.json
```

Repeat `check_coin.py BTCUSDT --logs` after 60 seconds. Compare the 5m candle,
formula-replay and feature checkpoints, alongside current-start log messages.
A running PID does not prove progress; recent candle timestamps alone do not prove
feature/decision progress. Preserve both outputs when reporting a stall. The existing
intelligence readiness report already identifies substantial Section 4 replay and
checkpoint blockers; that is distinct from a mobile push delivery failure.

`notification_status.py` is read-only and sends no alerts. It reports configured
transports, registered/enabled/retrying device counts, per-account delivery switches,
muted coin/timeframe counts, latest stored event time and rule-status counts. It
omits device tokens, event payloads, private keys and credentials. Run it on the
laptop that actually hosts the backend; the development workspace's configuration
cannot establish your laptop's readiness. Setup readiness does not prove an FCM
message was delivered or that Android/macOS permission is granted.

A separate mobile-app directory is not automatically part of this repository. Supply
its accessible source path/repository so package identity, token registration and
notification handling can be reviewed before enabling its sender. Existing Android
integration setup is documented in `mobile/android/README.md`; installing an APK
alone does not configure a sender or a reachable HTTPS laptop address.
