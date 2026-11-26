# ENAUSDT 15m — Mac pivot evidence audit

App source: `4e8d0b836f69d64df1489767869d25ceb2ad5096`.
Evidence commit: `b7f4c00a931fe8bd8bf1ed2245a1cb35193f2c2c`.
No app calculations, runner settings or databases were changed by this audit.

## Verified findings

- All 6,000 stored rows have valid `structure_events`; the legacy label fallback
  is not used for this evidence. The previously identified fallback placement
  difference therefore does **not** explain these screenshots.
- There are 884 high and 884 low confirmations. Every exported confirmation has
  the correct available origin-candle extreme and satisfies the 25% close rule.
- All 2,503 overlapping closed browser candles match the database event payloads.
- Running the exact exported renderer produces 370 SH and 370 SL labels: all
  740 pivot events whose origins are within the chart's loaded window. No such
  confirmed event is lost or invented by that rendering path.
- Candidate display style keys were excluded by the browser export's regex
  (`candidate_high_tag`/`candidate_low_tag` do not contain `pivot`). Their absence
  from the export is not evidence that those settings were absent in the app.

## Long unlabeled leg

The large high is 0.1155, origin 1795443300000, confirmed at 1795445100000.
The next low is 0.0904, origin 1795617000000, confirmed at 1795627800000.
Between those confirmations are 202 candles with no qualifying 25% rebound close.
The closest earlier rebound closes are 0.1028 against a 0.1029 required close
(candidate low 0.0987). The low confirmation threshold at 0.0904 is 0.096675.
Thus the lack of intermediate confirmed pivots follows the existing anchored
25% rule. Visual local turns do not necessarily meet that rule.

The latest candidate high is 0.1042, anchored at 0.0904. Its confirmation threshold
is 0.10075. The lowest later exported close is 0.1015, so it remains a candidate.

## Separate numeric boundary defect

Four older candles meet the exact decimal threshold but fail the floating-point
comparison by roughly 1e-17. The audit lists their timestamps and thresholds.
For example, 0.1035 is compared with a computed 0.10350000000000001 for a low
confirmation. None is in the 202-candle gap. This is a separate equality-edge
issue; fixing it is not a remedy for the screenshot's long leg or swing density.
Any numerical correction must have dedicated boundary tests and a reviewed
recursive-state repair plan. Do not silently replay history from this report.

## Rule decision still required

Requiring two consecutive reverse closes **in addition to** 25% can reduce dense
small pivots but cannot create pivots inside a leg that never retraces 25%.
Allowing those closes **instead of** 25% is a different confirmation rule.
No arbitrary ATR floor, candle-size filter or alternative rule was introduced.

## Reproduce

```bash
python3 Section_13_Development/diagnostics/audit_pivot_debug.py \
 Section_12_Research/reports/pivot_debug/ENAUSDT-15m-20261126/stored-pivots.json.gz \
 --chart Section_12_Research/reports/pivot_debug/ENAUSDT-15m-20261126/chart-pivots.json
python3 -m unittest Section_13_Development.tests.test_pivot_evidence_audit
```
