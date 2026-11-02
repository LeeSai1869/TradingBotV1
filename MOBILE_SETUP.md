# Laptop-hosted alerts for 4–5 people

The laptop runs the existing calculations, alert evaluator and a separate small
Web Push sender. No VPS, Play Store release or Apple App Store release is needed.
The mobile companion is an installable web app (PWA), served by the same backend.
It shows signal price, directional confidence, nearest sell-zone upper edge and
nearest buy-zone lower edge. Tapping a notification opens its original chart
candle. It does not place trades or connect to an exchange account.

## Private connection — no public website required

A practical starting point is Tailscale on the laptop and each phone:

1. Install Tailscale and connect the intended users/devices to your private
   network using invitations/access rules. Check the current plan/user allowance
   for your 4–5 people; this repository does not create an account or select a plan.
2. Keep the chart backend at `http://127.0.0.1:8000` running. Enable MagicDNS/HTTPS
   for your private network if prompted, then on the laptop use:

   ```bash
   tailscale serve --bg http://127.0.0.1:8000
   ```

   Use **Serve**, not public Funnel. Take the HTTPS address printed by Serve,
   such as `https://your-laptop.your-tailnet.ts.net`. No purchased domain is
   necessary for this private setup. Keep access limited to the intended people.
3. In the project, using the same Python as the UI backend:

   ```bash
   python3 -m pip install -r requirements-mobile.txt
   python3 configure_mobile.py --origin https://YOUR-LAPTOP.YOUR-NETWORK.ts.net --contact mailto:YOUR-EMAIL
   python3 restart_ui.py
   ```

   Replace the placeholders with your real address/contact. This only saves local
   configuration and private VAPID keys under `~/.tradingbot`; it does not open
   ports, install Tailscale or change your network. Existing keys are reused.
4. Create a separate normal account for each person as needed:

   ```bash
   python3 add_user.py person_name
   ```

   It prompts privately for a password and preserves existing accounts. Do not
   re-run the initial two-account provisioning command to add more people, since
   that command replaces the account file. Do not give users the admin password.
5. On each phone, connect to the private network and open
   `https://YOUR-ADDRESS/web_root/mobile.html`. Sign in, install it, then enable
   mobile notifications from inside the installed app.

Android Chrome supports browser installation. On iPhone/iPad, use Safari → Share
→ Add to Home Screen, then open that installed app; Web Push requires iOS/iPadOS
16.4 or later. App/OS permission is required. Each app account supports up to five
push devices. Signing out of the mobile companion unsubscribes that device.

The backend remains loopback-bound. It allows only localhost and the one explicit
configured HTTPS host. A proxy that rewrites Host to localhost is supported for
that exact configured Origin; arbitrary forwarded headers are not trusted. The
mobile APIs retain login, account ownership and same-origin checks. Public
reverse-proxy exposure is not installed or enabled by pulling this update.

## Controls and actual limits

Settings → Notifications has separate Desktop and Mobile switches. Coins and
Timeframes also have independent Desktop/Mobile switches. Mobile controls remain
disabled until server setup is complete. Desktop muting does not mute mobile or
change sounds/calculations. Sounds remains its own Settings menu; uploaded desktop
audio is not a custom phone OS notification ringtone.

The laptop must stay awake, online and running the backend. A sleeping/offline
laptop cannot generate new pushes. Phone OS push delivery can be delayed and is
not a guaranteed trade-execution channel. The private connection is needed to
sign in, enroll or open charts. After enrollment, OS push receipt uses Apple/
Google/browser infrastructure; it need not keep the app screen open.

In-app cards have a dismiss button and a 20-second lifetime. Phone system banner
appearance/lifetime is controlled by the OS; cards can be dismissed/tapped. Old
history is not pushed on first enrollment. The worker retries temporary failures,
removes expired endpoints and expires unsent alerts after five minutes. A stable
notification tag reduces duplicates after retries. Push payloads are encrypted by
Web Push, not sent as plain text to the provider. Private subscription keys remain
in the account alert store and are not exposed by the device-status API.

This implementation is tested with simulated push-provider responses and real
Web Push encryption; actual iPhone/Android receipt still needs your laptop's
HTTPS address, permissions and device enrollment. No external push subscription
or hosting was created during development.

## Later

The same backend and phone app can move to an always-on machine when needed.
Android store packaging is possible later, but store publication is unnecessary
for this small private group and does not replace the notification-generating
backend. No store listing, account fee or review is part of this update.
