# Standalone production app

This is a complete local application: the existing chart interface, HTTP backend,
calculation runner and independent liquidity recorder. It includes Python in the
built distribution; the destination does not need a Python installation. It has no
execution bot or mobile companion. Mobile push remains optional/deferred.

## Platforms and builds

Executables are OS/CPU-specific. A Mac `.app` cannot run on Windows or Linux.
The **portable memory layout** and application code are shared; build the same
release for the destination's OS and CPU architecture. The Linux executable was
built and smoke-tested in this development environment. Native macOS/Windows
artifacts must be built/tested there; their presence in the build workflow is not
proof of a completed native test or a signed/notarized release.

On your Mac, from the repository root, use the Python version that created your
current memory (check `python3 --version`):

```bash
python3 -m venv .venv-build
.venv-build/bin/python -m pip install -r requirements-standalone.txt
.venv-build/bin/python -m PyInstaller --clean --noconfirm packaging/TradingIndicator.spec
.venv-build/bin/python packaging/smoke.py
.venv-build/bin/python packaging/archive.py
```

The result is `dist/TradingIndicator.app` on macOS, `dist/TradingIndicator` on
Linux, or a folder containing `TradingIndicator.exe` on Windows. Keep the entire
folder/bundle together. Run the equivalent `.venv-build\Scripts\python.exe`
commands on Windows. Build tools require network access; the chart library and its
license are vendored, so the installed chart doesn't depend on the CDN. Market
collection still requires internet access.

Alternatively, GitHub Actions → **Build standalone app** → Run workflow creates
separate Linux, Windows and macOS archives. Select a Python version matching your
memory. Jobs build and smoke-test the frozen executable before uploading. The
archives preserve executable permissions/symlinks. The workflow includes macos-14 ARM64 and macos-15-intel builds; choose the artifact
matching your Mac's processor. No Apple
Developer signing/notarization or Windows signing certificate is configured.
macOS may require the normal explicit Open confirmation for an unsigned app.

## Start and stop

Double-click the Mac app, or run the executable on the target system. On first run,
a setup dialog creates an admin password (minimum 12 characters). Then the control
window opens your browser chart. Log in as `admin`. Close the control window or
click **Stop server** to stop all three workers. Closing only the chart does not
stop calculations. The launcher refuses a second copy using the same memory folder
and refuses to start if port 8000 is occupied. A worker failure stops the other
workers and reports its log location; there is no silent half-running success.

For headless/server use, initialize accounts interactively once:

```bash
TradingIndicator --data-dir /ABSOLUTE/PATH/TradingIndicatorData --setup
TradingIndicator --data-dir /ABSOLUTE/PATH/TradingIndicatorData --no-browser
```

On macOS, the executable inside the bundle is
`TradingIndicator.app/Contents/MacOS/TradingIndicator`. `--self-test` checks profile
paths, bundled assets, Tcl availability, formula identity and a feature/checkpoint
round trip without collecting market data or creating production databases.

The app binds localhost only. This update does not expose the backend remotely,
install login/system services, prevent sleep, or install any phone application.
Autostart/logout persistence needs a separate service installation configured to
invoke this executable with the same `--data-dir`; don't run the old services and
this app against the same memory. Sleep limitations remain as in SERVER_MODE.md.

## Memory is separate from the executable

Default location: `~/TradingIndicatorData`. Use `--data-dir` (or the
`TRADINGBOT_DATA_DIR` environment variable) for another local drive/location.
The profile contains:

- `storage/`: candles, features, decisions, analytical history, liquidity database.
- `config/`: universe, runtime policy, UI settings, optional recovery preferences.
- `state/`: resumable runner/universe state.
- `accounts/`: account hashes, drawings, alert history and optional private push setup.
- `logs/`, `locks/`: operational files.

Existing development commands retain their historical paths when the environment
variable is absent. The standalone launcher sets it before importing any stores.
Never point the production launcher at a development profile. Copy the entire
profile only after stopping its launcher/workers; retain SQLite WAL sidecars if
present. Don't synchronize live databases over cloud/shared folders. Local locking
on Windows conservatively serializes reader/deletion guards; Windows performance
still needs native testing. ACLs, filesystem permissions and private credentials
must be reviewed on the destination OS; Unix mode bits aren't Windows ACLs.

## Initial transfer from the current development installation

Stop ALL original runner, recorder and backend services on the source Mac first.
Verify they are not being restarted by launchd. Use a **fresh** destination folder:

```bash
TradingIndicator --data-dir /ABSOLUTE/PATH/ProductionMemory \
  --import-legacy "/Users/jhanzeebakbar/Scalp Indicator V1" \
  --source-stopped --self-test
```

The importer copies the six known active market/analytical SQLite databases using
SQLite backup (including committed WAL contents), registry/policy/UI configuration,
recovery preference and runner state. It refuses an initialized destination profile.
It does not copy source code or redundant pre-replay backups. Add
`--accounts-from "$HOME/.tradingbot"` to import private account hashes, alert history
(including custom sounds) and drawings from the stopped backend. Remembered login
sessions and push keys are deliberately not imported; sign in again. Add
`--include-raw-archive` to include the historical raw liquidity archive, which may
be large. Neither private memory nor credentials are bundled in the executable. Mobile credentials
may contain machine-specific paths and need separate setup. A failed import should
be retained for inspection; retry into a fresh destination, never overwrite it.

This is an initial offline import, **not** a live cross-database snapshot or a
prepared feature-update merge. Existing replay jobs are retained, not magically
completed. Before normal startup the launcher checks active saved formula versions;
incompatible memory is rejected rather than starting a new production replay.
Matching in-progress repair jobs may resume. Different Python versions may change
source-based signatures; use the exact matching build or a separately verified
prepared migration. `--self-test` reports the build signature but doesn't authorize
incompatible production memory.

## Releases and future prepared updates

Application files and memory are separate release artifacts. Replacing the app
must not replace the memory folder. This first package does **not** implement the
future export/import of verified new-feature results/checkpoints or schema-removal
updates. Until that mechanism exists, deploy matching code/memory releases only;
the compatibility guard prevents a casual formula-changing update from silently
forcing historical recalculation. Back up the stopped profile before any release.
No unattended updater, rollback/database migration system, profitability claim or
cross-platform trading-execution validation is included in this initial package.

## Per-machine Tailscale/reverse-proxy access

Do not hardcode one laptop's hostname into the server source. Configure the explicit
HTTPS origin without enabling mobile push:

```bash
TradingIndicator --data-dir /PATH/TO/ProductionMemory \
  --public-origin https://YOUR-MACHINE.YOUR-NETWORK.ts.net
```

This saves `accounts/public_access.json` and exits without starting services. For
the development checkout use `python3 configure_access.py --origin https://...`,
which uses the existing private account directory. Restart the backend/app after
configuration. A newly built app is required for this option. This does not install
Tailscale, expose a port, enable mobile delivery, or alter authentication. The host
and origin must match the independently configured HTTPS proxy; push setups, if
added later, must use the same origin. Change this setting when moving the profile
to a machine with a different address.
