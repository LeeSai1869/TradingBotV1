// Metadata notifications must not replace queued candle/history/settings work.
export function coalesceRender(pending, op, reset = false) {
    const keep = !reset && pending && (
        pending.op === 'settings' || (op === 'live' && pending.op !== 'liquidity') || op === 'liquidity'
    );
    return {
        op: keep ? pending.op : op,
        reset: reset || !!pending?.reset,
        latest: reset ? false : pending?.latest,
        span: reset ? undefined : pending?.span,
    };
}
