import test from 'node:test';
import assert from 'node:assert/strict';
import {formatValue, featurePriceFormat} from '../Section_11_UI_UX/web_root/value_format.js';

test('features always display two decimals without mutating values',()=>{
    const value=34.40199;
    for(const field of ['features.adx','features.ema50','features.vwap','features.atr','client.volume','adcn.final_score'])
        assert.equal(formatValue(value,field),'34.40');
    assert.equal(value,34.40199);
    assert.equal(formatValue(2,'features.rsi'),'2.00');
    assert.equal(formatValue(-.126,'features.di_direction'),'-0.13');
    assert.deepEqual(featurePriceFormat,{type:'price',precision:2,minMove:.01});
});
test('raw prices retain precision; unavailable and nonnumeric values remain readable',()=>{
    for(const field of ['client.open','client.high','client.low','client.close','features.current_price','features.c1'])
        assert.equal(formatValue(.123456789123,field),'0.123456789123');
    for(const value of [null,undefined,NaN,Infinity])assert.equal(formatValue(value),'—');
    assert.equal(formatValue(false),'false');
    assert.equal(formatValue('BUY'),'BUY');
});
