# Android notification inbox

Native Android 8+ app, with no charts or trading controls. It connects to the
existing laptop backend: sign in, read boxed signal messages, browse older
history, and independently toggle notifications and sound. Messages include
symbol, timeframe, price, confidence and nearest upper/lower opportunity edges.
Received messages stay in a private local SQLite inbox. Older server history
loads silently. Signing out hides that account's local inbox; it does not delete
server history. Clearing app storage/uninstalling removes its local copy.

## Build and install

Open this directory in Android Studio, install Android SDK 36 and use JDK 17+
(the project is tested with Java 21). Alternatively:

```bash
cd mobile/android
./gradlew assembleDebug
```

Install `app/build/outputs/apk/debug/app-debug.apk` on your phone. Debug builds
are for private testing, not Google Play. No Firebase credentials are required
to compile. Sign in to read history even before push is configured.

## Laptop address for your small group

Follow the private Tailscale HTTPS instructions in [MOBILE_SETUP.md](../../MOBILE_SETUP.md).
Use Tailscale Serve, not public Funnel; install Tailscale on each phone. Enter
that HTTPS address in the app and use a separate existing laptop account for
each user (`python3 add_user.py USERNAME`). Both internet access and access to
the private laptop are needed to synchronize history. The laptop must be awake,
online and running the backend/calculations to generate and send new events.
Google Play distribution does not replace this connection.

## Create Firebase once (no existing project needed)

1. Open https://console.firebase.google.com/ and create a project. Analytics is
   optional. Register an **Android app** with package `com.tradingindicator.alerts`.
   If you choose another package, build with `-PapplicationId=YOUR.PACKAGE` and
   use the same package in every setup command. Choose the final package before
   publishing: a Play listing's package cannot subsequently be changed.
2. Download that app's `google-services.json`. This implementation reads its
   public identifiers on the laptop; do not add it to the Android source tree.
3. In project settings → Cloud Messaging, ensure Firebase Cloud Messaging API
   (HTTP v1) is enabled. In project settings → Service accounts, generate a new
   private key. Keep this JSON **only on the laptop**. Never send it to phone
   users, bundle it into an APK, or commit it. Limit access and revoke/replace
   the key if exposed. The sender needs permission to send FCM messages.
4. From the repository root, using the same Python as the UI backend:

   ```bash
   python3 -m pip install -r requirements-android-push.txt
   python3 configure_android.py \
     --origin https://YOUR-LAPTOP.YOUR-NETWORK.ts.net \
     --google-services /PATH/TO/google-services.json \
     --service-account /PATH/TO/firebase-private-key.json
   python3 restart_ui.py
   ```

   This copies the secret into `~/.tradingbot/firebase-service-account.json`
   and writes `~/.tradingbot/android_push.json`, both mode 600. It creates no
   cloud resources. If Web Push is also configured, use the **same HTTPS origin**.
5. Install/open the Android app, connect and sign in. Allow Android notification
   permission when prompted (Android 13+). The authenticated app fetches public
   Firebase identifiers and registers its device token. The private key stays
   on the laptop. Google Play services/internet are required for FCM delivery.
6. Enable mobile delivery for the intended coins/timeframes in laptop Settings.
   Generate a new alert/test event and check both the OS notification and inbox.
   Historical loading never replays old alarms. Offline/disabled events remain
   in server history; push retries expire rather than playing old alerts later.

After adding Firebase to an already-connected installation, sign out and connect
again. Switching Firebase projects requires clearing app storage, then signing
in again. Android can suppress delivery when force-stopped, under restrictive
battery settings or Do Not Disturb. Sound uses the phone's notification tone;
the app selects audible/silent channels, while OS settings take precedence.
Desktop custom sound uploads are separate and are not copied to phones.

## Google Play later

The source includes release bundle support:

```bash
export ANDROID_KEYSTORE_FILE=/ABSOLUTE/PATH/release.jks
export ANDROID_KEYSTORE_PASSWORD='YOUR_PASSWORD'
export ANDROID_KEY_ALIAS='YOUR_ALIAS'
export ANDROID_KEY_PASSWORD='YOUR_KEY_PASSWORD'
./gradlew bundleRelease
```

Keep signing keys/passwords outside Git and protect backups. Without these
variables the release bundle is **unsigned** and cannot be submitted. Output:
`app/build/outputs/bundle/release/app-release.aab`. Increment versionCode for
subsequent uploads. Use a unique package and your own app identity.

Publishing requires your Google Play developer account, signed bundle, store
listing, privacy policy/Data Safety declarations, applicable testing and review.
This repository does not publish or guarantee approval. Disclose login/device
tokens, signal history and Firebase processing accurately. Start with a private
APK or Play internal test for your 4–5 users. There is no native iOS build here;
iPhone users can use the PWA described in MOBILE_SETUP.md.

## Boundaries and verification

The app consumes authenticated alert history and FCM configuration APIs. It does
not calculate signals, change decision logic or access exchange credentials.
The independent optional FCM worker reads the existing alert store. Missing
Firebase setup leaves desktop alerts and history usable. End-to-end FCM receipt
requires your real project, phone and running laptop and must be checked there.
