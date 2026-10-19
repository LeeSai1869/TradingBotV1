import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import { logicalShift } from '../Section_11_UI_UX/web_root/window_state.js';

function cache() {
    const context = vm.createContext({window: {}, console: {log() {}, error() {}},
        document: {getElementById: () => null}, Date, fetch: () => {throw Error('unexpected fetch');}});
    vm.runInContext(fs.readFileSync(new URL('../Section_11_UI_UX/web_root/data_cache.js', import.meta.url), 'utf8'), context);
    const c = context.window.DataCache;
    c._readFlagsCurrent = async () => null;
    return c;
}
const deferred = () => {let resolve; const promise = new Promise(r => resolve = r); return {promise, resolve};};
const packet = (time, extra = {}) => ({klines: [{time}], features: [], flags_history: [], ...extra});

test('late initial response cannot overwrite a newer market', async () => {
    const c = cache();
    const old = deferred();
    c._prefetchInitialOlder = async () => false;
    c._fetchWindow = () => c.symbol === 'OLD' ? old.promise : Promise.resolve(packet(200));
    const first = c.loadInitial('OLD', '1m');
    await c.loadInitial('NEW', '5m');
    old.resolve(packet(100));
    assert.equal(await first, false);
    assert.equal(c.symbol, 'NEW');
    assert.equal(c.klines[0].time, 200);
});

test('an old flags response cannot render data under the new selection', async () => {
    const c = cache(); const old = deferred();
    c._prefetchInitialOlder = async () => false;
    c._fetchWindow = async () => packet(c.symbol === 'OLD' ? 100 : 200);
    c._readFlagsCurrent = (s) => s === 'OLD' ? old.promise : Promise.resolve({symbol: 'NEW'});
    const first = c.loadInitial('OLD', '1m');
    await c.loadInitial('NEW', '1m');
    old.resolve({symbol: 'OLD'});
    await first;
    assert.equal(c.flags_current.symbol, 'NEW');
    assert.equal(c.klines[0].time, 200);
});

test('reversing navigation invalidates an obsolete directional prefetch', async () => {
    const c = cache(); const pending = deferred();
    c.timeframe = '1m'; c.klines = [{time: 60}, {time: 120}];
    c._fetchBlock = () => pending.promise;
    const work = c.prefetchNextOlder(60000);
    const reserve = {klines: [{time: 30}]};
    c.setReadyOlder(reserve);
    pending.resolve({klines: [{time: 10}]});
    assert.equal(await work, false);
    assert.equal(c.readyOlder, reserve);
});

test('partial history and gaps preserve the same visible candle positions', () => {
    const old = [30, 40, 50, 60].map(time => ({time}));
    assert.equal(logicalShift(old, [20, 30, 40, 50].map(time => ({time}))), 1);
    assert.equal(logicalShift(old, [50, 60, 80].map(time => ({time}))), -2);
});

test('month boundaries follow the UTC calendar, including leap years', () => {
    const c = cache(); c.timeframe = '1M';
    assert.equal(c._shiftMs(Date.UTC(2024, 1, 1), 1), Date.UTC(2024, 2, 1));
    assert.equal(c._shiftMs(Date.UTC(2024, 2, 1), -1), Date.UTC(2024, 1, 1));
});

test('live refresh is ignored if the user pans into history while fetching', async () => {
    const c = cache(); const pending = deferred();
    c.timeframe = '1m'; c.klines = [{time: 60}];
    c._fetchWindow = () => pending.promise;
    const refresh = c.refreshLive();
    c.atLiveEdge = false;
    pending.resolve(packet(120));
    assert.equal(await refresh, false);
    assert.equal(c.klines[0].time, 60);
});

test('live rollover refreshes candles, features and markers as one packet', async () => {
    const c = cache(); c.timeframe = '1m'; c.klines = [{time: 60}];
    c._fetchWindow = async () => ({klines: [{time:60}, {time:120}],
        features: [{time:120, ema50:42}], flags_history: [{bar_time:120000, signal_type:'BUY'}]});
    let event;
    c.subscribe((_, op) => event = op);
    assert.equal(await c.refreshLive(), true);
    assert.equal(c.features[0].ema50, 42);
    assert.equal(c.flags_history[0].signal_type, 'BUY');
    assert.equal(c.klines.length, 2);
    assert.equal(event, 'live-refresh');
});

function pollHarness(c) {
    let nextTimer;
    const updates = [];
    const elements = {symbol: {value: 'BTCUSDT'}, interval: {value: '1m'}};
    const context = vm.createContext({DataCache:c, Date, console,
        document: {getElementById: name => elements[name]},
        candles: {updateLive: b => updates.push(b)}, flags: {update() {}},
        setTimeout: fn => {nextTimer=fn; return 1;}, clearTimeout() {},
        fetch: async () => ({ok:true,json:async () => ({time:180})}),
    });
    const source = fs.readFileSync(new URL('../Section_11_UI_UX/web_root/live_poll.js',import.meta.url),'utf8')
        .replace(/^import .*;$/gm,'').replace(/export function/g,'function');
    vm.runInContext(source + '\nglobalThis.controls={start,stop};',context);
    return {context, updates, elements, timer: () => nextTimer};
}
const flush = () => new Promise(resolve => setImmediate(resolve));

test('live rollover actually requests the newly closed canonical packet', async () => {
    const c=cache(); c.symbol='BTCUSDT'; c.timeframe='1m'; c.klines=[{time:60}];
    let refreshed=0;
    c.refreshLive=async () => {refreshed++;};
    const h=pollHarness(c);
    h.context.controls.start();
    await flush();
    h.context.controls.stop();
    assert.equal(refreshed,1);
    assert.equal(h.updates[0].time,180);
});

test('live response for a previous selection cannot update the candles', async () => {
    const c=cache(); c.symbol='BTCUSDT'; c.timeframe='1m';
    const pending=deferred(); const h=pollHarness(c);
    h.context.fetch=() => pending.promise;
    h.context.controls.start();
    c._reloadGeneration++; c.symbol='SUIUSDT'; h.elements.symbol.value='SUIUSDT';
    pending.resolve({ok:true,json:async () => ({time:180})});
    await flush(); h.context.controls.stop();
    assert.equal(h.updates.length,0);
});

test('the next poll is scheduled only after the active request finishes', async () => {
    const c=cache(); c.symbol='BTCUSDT'; c.timeframe='1m';
    const pending=deferred(); const h=pollHarness(c);
    h.context.fetch=() => pending.promise;
    h.context.controls.start();
    assert.equal(h.timer(),undefined);
    pending.resolve({ok:false});
    await flush(); h.context.controls.stop();
    assert.equal(typeof h.timer(),'function');
});
