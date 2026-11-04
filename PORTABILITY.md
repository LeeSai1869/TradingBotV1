# Moving this application

The source checkout can run from a different folder; it is not a standalone bundled
binary. Launchers resolve their own project root, including paths containing spaces,
and use `TRADINGBOT_PYTHON` when set, otherwise `python3` from PATH. The two older
runner/chart shell launchers no longer contain one user's absolute Mac paths.

To move machines, stop all project services before copying databases, preserve the
required local data/configuration, install Python/dependencies on the destination,
and recreate its virtual environment. Start the checkout with that environment and
reinstall its login/system service registrations for the new absolute paths. Do not
start two writers against the same copied/live storage. Existing services are not
modified by Git pulls alone. Platform-specific macOS service installers remain macOS
specific; no Windows/Linux service installer or packaged executable is claimed.

Private account/push setup under `~/.tradingbot` and OS permissions are machine-level
state, not bundled application code. Transfer secrets privately only to the trusted
backend machine when needed; phone applications receive public configuration/device
registration, never the service-account private key. See `SERVER_MODE.md` for logout
and idle-sleep operation, and `mobile/android/README.md` for Android push setup.

## Standalone distribution

The standalone build and separate cross-platform memory profile are described in
[STANDALONE_APP.md](STANDALONE_APP.md). Source-mode defaults above remain unchanged.
