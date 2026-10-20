# Global Core — Section 1

**Status: LOCKED**

Section 1 is a closed, self-contained module. It owns the ingestion,
storage, and audit of Binance klines, plus the symbol registry and the
main loop. Downstream sections consume it through a single public
gateway (`global_packet`). No other module touches Global Core's
internals.

---

## 1. What Global Core owns

| Artifact | Path | Purpose |
|---|---|---|
| Kline store | section_1_4_1_memory_storage/Storage/klines.db | Raw Binance klines |
| Metadata | section_1_4_1_memory_storage/Storage/metadata.db | Audit trail, compromised pairs |
| Symbol registry | symbols.json | Approved / staged / disapproved / pending / top50 |
| Audit manifests | section_1_4_1_memory_storage/Audit/audit_log/ | Every audit run |
| Known gaps | section_1_4_1_memory_storage/Audit/known_gaps.json | Documented Binance source gaps |
| Processors list | processors.json | Downstream processors called per new bar |
| Orchestrator state | section_1_9_state.json | Last-seen bar per (symbol, interval) |

## 2. What Global Core does NOT own

- Features (Section 4)
- Regime classification (Section 5)
- Scoring engines (Section 6)
- Confluence (Section 7)
- Decisions / signals (Section 8)
- ADCN memory (Sections 4 & 8, per column)
- UI flags (Section 11)
- VN / vision analysis (external, strategy-dependent)
- AI agent / bot / execution (external)

Global Core runs the loop but does not compute any of these.
It calls processors that do -- and knows nothing about them.

---

## 3. Public surface (what other sections MAY import)

From outside Section_1_Global_Core/, you may import:

    Section_1_Global_Core.global_packet
    Section_1_Global_Core.import_features_packet
    Section_1_Global_Core.import_regime_packet
    Section_1_Global_Core.import_opportunity_score
    Section_1_Global_Core.import_confidence_score
    Section_1_Global_Core.import_scalp_score_packet
    Section_1_Global_Core.import_scalp_confluence_score_packet
    Section_1_Global_Core.import_scalp_decision_score_packet
    Section_1_Global_Core.section_1_1_constants
    Section_1_Global_Core.section_1_2_market_definitions
    Section_1_Global_Core.section_1_3_market_state
    Section_1_Global_Core.section_1_4_memory
    Section_1_Global_Core.section_1_5_timeframes
    Section_1_Global_Core.section_1_6_outputs
    Section_1_Global_Core.section_1_7_global_state
    Section_1_Global_Core.section_1_8_symbols

Nothing else. In particular:

    Section_1_Global_Core.section_1_4_1_memory_storage.*   <- PRIVATE
    Section_1_Global_Core.section_1_9_orchestrator.*       <- PRIVATE
    Section_1_Global_Core.section_1_10_*                   <- PRIVATE
    Section_1_Global_Core.section_1_11_*                   <- PRIVATE
    Section_1_Global_Core.tools.*                          <- PRIVATE

Enforced by:

    python3 -m Section_1_Global_Core.tools.check_imports

---

## 4. The loop (orchestrator)

Entry point:

    python3 -m Section_1_Global_Core.section_1_9_orchestrator

Every cycle (~30 s):

1. update_klines.update_all() -- fetch new closed bars for every active
   symbol x 15 intervals, write to klines.db
2. audit_runner.run_fast() -- A1 (schema) + A2 (continuity) + A5 (freshness)
3. For every (symbol, interval), read bars since last-seen state. For each
   new closed bar, build a BarEvent and dispatch to every processor listed
   in processors.json.
4. Save state, sleep, repeat.

First run seeds baselines only -- no events fired. Processors start
receiving events from the next bar forward.

---

## 5. Adding a processor

Edit processors.json:

    {
      "schema_version": 1,
      "processors": [
        {"module": "Section_4_Features.feature_builder", "function": "process_bar"}
      ]
    }

Each processor exposes a function accepting a BarEvent:

    def process_bar(ev):
        # ev.symbol, ev.timeframe, ev.open_time, ev.close_time
        # ev.open, ev.high, ev.low, ev.close, ev.volume
        ...

Global Core loads processors by string. It never imports them directly.
Adding or removing a processor does not modify Global Core.

If a processor raises, Global Core logs and continues with the next bar.
The loop never crashes from a processor error.

---

## 6. Symbol management

Lists in symbols.json:

| List | Meaning |
|---|---|
| approved | Coins Global Core is allowed to process |
| staged | Approved in principle, waiting to be promoted |
| disapproved | Permanently rejected |
| pending | Candidates awaiting your decision |
| top50 | Last known top-50 eligible set (from proposer) |

CLI:

    python3 -m Section_1_Global_Core.section_1_11_symbol_verifier status
    python3 -m Section_1_Global_Core.section_1_11_symbol_verifier list-pending
    python3 -m Section_1_Global_Core.section_1_11_symbol_verifier approve SYMBOL
    python3 -m Section_1_Global_Core.section_1_11_symbol_verifier disapprove SYMBOL --reason "..."
    python3 -m Section_1_Global_Core.section_1_11_symbol_verifier promote SYMBOL
    python3 -m Section_1_Global_Core.section_1_11_symbol_verifier stage-list
    python3 -m Section_1_Global_Core.section_1_11_symbol_verifier set-cap N
    python3 -m Section_1_Global_Core.section_1_11_symbol_verifier move SYMBOL approved|disapproved

Proposer:

    python3 -m Section_1_Global_Core.section_1_10_symbol_proposer

---

## 7. Audit

Every cycle (fast): A1 + A2 + A5.
Daily (full): A3 (cross-source sampling) + A4 (cross-interval).
Every run: manifest JSON written to Audit/audit_log/.

Manual run:

    python3 -c "from Section_1_Global_Core.section_1_4_1_memory_storage.Audit import audit_runner; audit_runner.run(include_daily=True)"

Locked invariant: klines.db contains only raw Binance klines. Nothing
else is ever written there. Quarantine is not used.

---

## 8. Version lock rules

Once locked, Global Core's code and data contracts are frozen.

Allowed without version bump:
- Adding processors via processors.json
- Approving / disapproving / promoting symbols
- Adding entries to known_gaps.json

Requires bump + re-audit:
- Editing any file inside Section_1_Global_Core/
- Changing symbols.json schema
- Changing any public-surface packet field
- Changing the BarEvent shape

Forbidden:
- Any import of Sections 2-13 inside Global Core
- Any direct write to klines.db from outside Global Core
- Any change to known_gaps.json without documenting the reason

---

## 9. Freeze record

    Locked: 2026-10-13
    Audit: pass (A1=0, A2=0, A5=0)
    Symbols: approved=[BTCUSDT, SUIUSDT], staged=47
    Intervals: 15 (1m..1M)
    Processors: 0 (scaffold only)

Any subsequent change must update this record.

### Stored-bar read contract 1.1 — 2026-10-19

User-requested chart correction: `db.read_state_page()` exposes the existing
three memories as one record per canonical candle, with count-based pages
and an exclusive `before` cursor. `klines_store.read_page()` uses the existing
primary key; no schema, ingestion, audit rule, BarEvent, processor, or stored
data changes. Existing range readers remain compatible.

Re-audit scope: isolated SQLite contract tests cover exact counts, gaps,
calendar-month keys, missing derived rows, market identity and cursor edges.
Browser flow tests exercise the same gateway. This is not a new market-data
A1/A2/A5 certification: the cloud instance has no downloaded market history.
The previously reported public-surface checker conflicts remain outstanding.

### Runtime data policy 2.0 — 2026-10-20

User-requested timeframe and coin administration adds a shared runtime policy,
manual coin pauses, role-checked Section 11 operations and three-memory deletion.
The registry remains permanent; pending/staged/eligibility remain rule-driven.
Ingestion and processing read the same policy, recheck it before writes, and
coordinate with deletion through a cross-process lock. Proposer/verifier reject
stale registry writes. Freshness checks exclude inactive pairs; structural audits
continue to cover stored history. Reactivation bootstraps missing candle pages;
delete epochs reset runner cursors and invalidate stale catch-up/browser caches.
Processor errors propagate so the runner does not advance past failed bars.

Required deployment: restart all writer processes and the UI server after pulling
before using administration. Local accounts are provisioned separately; there
are no default passwords. See Section 11's controls/settings/README.md.

Validation covers isolated three-store transaction rollback, scoped deletion,
registry preservation, role bypass attempts, stale writes, re-download and actual
feature calculation. No real market history was deleted and no new market-data
A1/A2/A5 certification is claimed. Existing import-policy checker conflicts remain
outside this change. The previous 1.1 chart read APIs remain compatible.
