import test from 'node:test';
import assert from 'node:assert/strict';
import {fibLevels,normalizeDrawings} from '../Section_11_UI_UX/controls/drawings/geometry.js';
test('retracement runs from the second anchor back toward the first in either direction',()=>{
    const up=fibLevels('retracement',[{price:100},{price:200}]);
    assert.equal(up.find(l=>l.ratio===0).price,200);
    assert.equal(up.find(l=>l.ratio===.618).price,138.2);
    assert.equal(up.find(l=>l.ratio===1).price,100);
    const down=fibLevels('retracement',[{price:200},{price:100}]);
    assert.equal(down.find(l=>l.ratio===.5).price,150);
});
test('extension projects the first leg from the third anchor',()=>{
    const levels=fibLevels('extension',[{price:100},{price:200},{price:150}]);
    assert.equal(levels.find(l=>l.ratio===1).price,250);
    assert.equal(levels.find(l=>l.ratio===1.618).price,311.8);
});
test('saved drawings reject invalid tools, missing anchors and nonfinite coordinates',()=>{
    const a={time:123,offset:.5,price:10};
    assert.deepEqual(normalizeDrawings([{type:'line',anchors:[a,a]},{type:'unknown',anchors:[a]},
        {type:'extension',anchors:[a,a]},{type:'horizontal',anchors:[{...a,price:NaN}]}]),[{type:'line',anchors:[a,a]}]);
    assert.deepEqual(normalizeDrawings(null),[]);
});
