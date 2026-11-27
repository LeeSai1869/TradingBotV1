# Current data before historical work

The market runner services active pairs in this order:

1. Download newly closed candles, rotating across active pairs. Skip endpoints
   already caught up to the last closed interval. Monthly intervals use UTC
   calendar boundaries. Request timeouts use the remaining download budget;
   each subsequent request rechecks the deadline.
2. Advance recent, contiguous feature tails, including the bulk owner's tail.
   A pending selective repair executes only unchanged calculation units in this
   lane. Changed fields remain NULL until their historical replay reaches them.
   Provisional chart calculations use the same unchanged units on a read-only
   checkpoint clone.
3. Service eligible analytical updates and strategy decisions. Decisions require
   their own committed inputs; unrelated pivot repairs do not block DI inputs.
   Repairs that affect required inputs, or have an outdated signature, still block.
4. Rotate feature repairs across every active coin/timeframe, in bounded
   batches, independently of the analytical bulk owner. Persist the last visited
   pair in runner state so restart does not return the queue to its beginning.
   Failed pairs also yield their next turn. Historical downloads and analytical
   history keep their bounded bulk turns. Feature recovery borrows those
   background turns while active.

Current feature rows, the main checkpoint and the moving repair target commit
atomically. A repair merges only after reaching the current main checkpoint.
Missing raw candles remain gaps; neither scheduler path jumps over them.

An operator's feature-runtime priority is saved until cleared. It selects a
background repair pair for a bonus turn on alternating background calls. The
normal queue retains its cursor and continues on the other calls, so a saved
preference cannot starve other pairs. It does not precede current downloads or
current feature updates. Clear just that preference, preserving the configured budgets:

```python
from Section_1_Global_Core import feature_runtime
config = feature_runtime.read()
config['priority'] = None
feature_runtime.write(config)
```

This changes no strategy formula, pivot rule, active timeframe, chart control,
exchange order behavior or database schema. Recursive changed features can still
show pending until their replay completes; unrelated live indicators can advance.
Network/service outages can still delay incoming candles. Network timeouts are
socket-operation bounds, not a hard wall-clock guarantee for every request phase.
