# Volume Profile nodes and analytical backlog

Volume Profile lines and histogram nodes have different stored inputs. POC/VAH/VAL
come from feature rows; HVN/LVN histograms also require the matching feature
checkpoint's stored volume bins. Current lines alone do not prove those bins are
available. The current profile updates on committed closed candles, not intrabar.

Run from the same checkout/profile used by the chart backend:

```sh
python3 check_volume_profile.py BTCUSDT --intervals 5m 15m 30m 1h 4h
```

This reads databases without recalculating features, downloading data or changing
policy. It prints the database path, latest closed candle, feature checkpoint,
histogram readiness/reason, POC/value-area levels and nonzero HVN/LVN counts. A
ready profile with nonzero nodes points to settings, rendering or a different
backend/profile when the chart still lacks nodes. Check that High-volume nodes
and Low-volume nodes are enabled in Volume Profile settings; enabling POC/VAH/VAL
alone does not enable nodes. Zero-volume bins have zero histogram width.

The chart's VP status tooltip now carries the concrete checkpoint wait reason.
The backend reads one consistent checkpoint transaction and includes feature
generation in its profile-cache identity. Previously a same-candle recalculation
could leave stale histogram bins cached when its POC/VAH/VAL were unchanged. No
Volume Profile formula or live trading logic was changed.

For Section 5, `python3 intelligence_status.py --summary` also reports the actual
runner processing universe. Command-line symbol/timeframe filters limit the
diagnostic report only; they do not limit processing.

In the supplied November 12 logs, 400 active symbol/timeframe pairs share the
analytical budgets: 4 live scope visits per cycle and a separate history budget
of 200 rows / 0.5 seconds, including dependency work. Ten engines make 4,000
scopes. Feature packets and current candles can therefore be current while a
particular analytical scope waits a long time for its next visit. `[history:*]`
messages show that historical calculations are running; `BACKFILLING` does not
mean caught up. Occasional multi-second database commits and writer waits add
pressure, but are not proof of a stopped runner.

Changing the processing universe or analytical scheduling priorities is separate
from selecting coins in the chart or filtering a status report. Do not reset
databases, replay checkpoints, or formulas to address scheduling pressure.
