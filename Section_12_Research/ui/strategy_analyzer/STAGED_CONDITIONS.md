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
Stored-memory analysis still requires a valid feature generation. Pending feature
repairs can make that source unavailable until its repair finishes; the editor
cannot manufacture missing or invalidated features.

The accompanying current-move-v2 pivot update needs one automatic targeted
historical repair. Its geometry differs from confirmed-pair-v1, so the old partial
pivot checkpoint cannot be reused. Unrelated live indicators and the fair repair
scheduler retain their existing paths. Do not delete databases or manually reset
replay progress.
