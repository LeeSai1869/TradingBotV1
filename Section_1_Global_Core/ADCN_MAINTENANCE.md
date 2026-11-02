# ADCN maintenance

Administrators use **Settings → Features → ADCN Memory**. Deployment never clears
existing data and no cleanup runs automatically.

Preview either or both operations:

- Retire archived decision/interpretation fields: count their non-NULL values,
  clear values globally and persist a marker suppressing future storage.
- Delete obsolete BUY/SELL history, optionally scoped by symbol/timeframe.
  Current rule signals, WAIT/SUPPRESSED rows, anchored-evidence rows and rule
  checkpoint rows are excluded.

Identity, current signal and availability keys are always protected. Explicit
column-key dependencies in the live Section 8 processor/presentation/sequence/rules
and Core analysis/evidence consumers also protect fields. This is the supported
live dependency boundary, not analysis of arbitrary external scripts. New consumer
modules must be added to this boundary before deployment. Archived compatibility
readers can still return NULL for retired fields.

Selection changes invalidate the preview. Apply recomputes counts/eligibility
under writer/deletion guards, checks the preview token and requires the exact text
RETIRE ADCN DATA. A changed preview or protected selection is rejected. Mutation
is a single ADCN transaction. Permanent candles/features, evidence, checkpoints
and alert history are preserved.

Retirement keeps schema columns for compatibility. The generic writer ignores
retired values. Current DI decisions already do not calculate archived scores;
this saves storage, rather than claiming extra calculation speed. SQLite pages
become reusable; the file may not shrink immediately. No blocking VACUUM runs.

**Restore future storage** removes the marker. It cannot recover cleared values,
recalculate old history or enable an archived engine. New live features still use
the normal feature contract/migration path.
