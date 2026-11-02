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
