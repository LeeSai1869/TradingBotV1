# Trigger and Activate in offline replay

Each condition has a role. Existing conditions default to **Activate**.

The Trigger group arms its branch when its conditions match together. The setup
remains armed without a time expiry, even when those conditions later become
false. The Activate group then determines when that branch produces a simulated
BUY or SELL signal. AND/OR/NOT grouping is preserved separately within each role;
review the preview when mixing roles inside groups. At least one Activate
condition is required.

Activation may occur on the same or a later candle close (default), or only on a
later close. Execution remains at the next contiguous candle open. Only the side
currently awaited can arm. A side change or missing/invalid price candle clears
pending setups. The report records arming, activation, resets, and original
trigger inputs separately from activation-time inputs.

For a trailing SELL, choose **Profit threshold only** to avoid adding an indicator
condition. Choose **Profit threshold + indicator conditions** for conditional
eligibility. Search is inside each condition field dropdown.

These controls configure offline analyzer replay; they do not activate a live bot.
Stored-memory analysis requires a compatible feature generation. A selective
repair targeting the current formulas leaves unrelated stored fields usable. Core
repair masks hide affected cells until their repair cursor passes them. Unknown
generations remain blocked, and analytical engine context keeps its stricter
generation checks. All-unknown BUY evaluation is reported as BLOCKED_INPUTS,
with unavailable return/balance cards rather than a zero-return result. No values
are recalculated or written by this reader.

The accompanying current-move-v2 pivot update needs one automatic targeted
historical repair. Its geometry differs from confirmed-pair-v1, so the old partial
pivot checkpoint cannot be reused. Unrelated live indicators and the fair repair
scheduler retain their existing paths. Do not delete databases or manually reset
replay progress.

## Test periods

Full Life is the default and leaves the replay unbounded, using all available
history per selected coin. Past 6 Months, Past Year, Past 2 Years, and Past 4 Years
use calendar months ending at the selected source’s latest candle, rounded up
to the next UTC minute when necessary. Batch coins share those boundaries.
Shorter histories are not filled with invented data. Custom dates remain editable,
and the selected preset is retained with the browser draft.
