import test from 'node:test';
import assert from 'node:assert/strict';
import {migrateStyles, normalizeStyles} from '../Section_11_UI_UX/controls/settings/feature_styles.js';

test('legacy shared EMA styling migrates to independent outputs without changing selections', () => {
    const styles = migrateStyles({periods:[7,50], color:'#123456', width:3, style:2});
    assert.equal(styles.ema7.visible,true);
    assert.equal(styles.ema25.visible,false);
    assert.equal(styles.ema50.color,'#123456');
    assert.equal(styles.ema50.width,3);
    assert.equal(styles.ema50.style,2);
    styles.ema7.color='#abcdef';
    assert.equal(styles.ema50.color,'#123456');
});

test('stored per-output styling survives normalization and invalid fields fall back', () => {
    const styles = normalizeStyles({rsi:{color:'#abcdef',width:4,style:1},
        ema25:{visible:true,color:'bad',width:20,style:99}});
    assert.deepEqual(styles.rsi,{visible:false,color:'#abcdef',width:4,style:1});
    assert.equal(styles.ema25.visible,true);
    assert.equal(styles.ema25.width,2);
    assert.equal(styles.ema25.style,0);
    assert.deepEqual(migrateStyles({outputs:styles}),styles);
    assert.equal(normalizeStyles().ema50.visible,true);
});
