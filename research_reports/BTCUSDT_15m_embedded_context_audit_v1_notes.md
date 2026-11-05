# First context audit: selected examples only

Source: BTCUSDT 15m all-history 2% pivot study v1, source_id
`e234ff6c94de739beb7c529be9937a516c637d7cad0006a80b96aa54b708e5dc`.

This report audits the **40 deliberately selected embedded contexts**, not the
full 103,127 pivots and not actual BUY/SELL flags. Recognition-candle inputs are
used for scores; outcomes start at the following candle open. The original
source report remains unchanged. Open the companion `.html` in a browser.

- 23 BUY-side examples: 22 ready Confidence scores, one insufficient-evidence
  warmup. Selected modes: 14 continuation and 9 reversal. Available scores range
  from 53.03 to 86.79 out of 100.
- 17 SELL-side examples: all ready, 13 continuation and 4 reversal; scores range
  from 37.53 to 73.18.
- In 13 BUY-side continuation examples, removing the structure inputs removes
  20 score points. Reversal-mode scores do not depend on that family. This is
  sensitivity to the questioned structure input, not proof that all those
  classifications were wrong, a corrected score, or a calibrated probability.
- After recognition, the BUY-side examples contain 4 observed 2% hits, 15 complete
  non-hits and 4 with no post-confirmation window. SELL-side contains 3 hits,
  9 non-hits and 5 with no post-confirmation window. These selected-sample rates
  cannot establish predictive performance or generalize to live trades.
- Independent local/4h/daily Regime and Trend histories are **not embedded** in
  the source report. Their coverage remains explicitly unavailable. Legacy
  regime labels are kept separate, and legacy trend maturity is not direction.
- Opportunity reconstructions use scalar features, not the chart's complete
  historical zone inventory. Native/model bands, touch coverage, gap crossings,
  and excursions after the touch candle remain individually inspectable.
  No-touch within a short swing does not establish a faulty band prediction.

The staged structure patch reproduces and corrects the count>2 classification
path in regression tests. It is not installed in the live feature producer:
that requires isolated historical repair and a separate deployment/migration.
No feature replay, decision filter, UI layout or runner rule changed here.

For full-cohort and actual saved-decision audits, use `PIVOT_CONTEXT_AUDIT.md`.
