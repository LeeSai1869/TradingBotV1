import test from 'node:test';
import assert from 'node:assert/strict';
import {closedSignals,SignalCursor,normalizeMomentum} from '../Section_11_UI_UX/overlays/markers/preferences.js';
import {normalizeStyles} from '../Section_11_UI_UX/controls/settings/feature_styles.js';
const signal=(time,side='BUY')=>({open_time:time-60000,client:{close_time:time},momentum:{signal_type:side}});

test('Momentum styles default on and retain independent marker shape/color/size/label',()=>{
    const styles=normalizeStyles({momentum_sell:{visible:false,shape:'circle',width:4,color:'#123456',label:false}});
    assert.equal(styles.momentum_buy.visible,true);assert.equal(styles.momentum_buy.shape,'arrowUp');
    assert.deepEqual(styles.momentum_sell,{visible:false,shape:'circle',width:4,color:'#123456',label:false,style:0});
    assert.equal(normalizeStyles({momentum_buy:{shape:'bad'}}).momentum_buy.shape,'arrowUp');
});
test('forming bars and old strategy decisions cannot produce Momentum markers',()=>{
    const bars=[signal(1000),{...signal(2000,'SELL'),provisional:true},{adcn:{signal_type:'BUY',trigger:'OLD'}}];
    assert.equal(closedSignals(bars).length,1);
    assert.equal(closedSignals(bars,{},false).length,0);
    assert.equal(closedSignals(bars,{momentum_buy:{visible:false}}).length,0);
});
test('sound cursor suppresses history, duplicates, pre-open history and symbol/timeframe switches',()=>{
    const cursor=new SignalCursor(),data={symbol:'ETHUSDT',timeframe:'5m'};
    assert.deepEqual(cursor.observe(data,closedSignals([signal(900)]),1000),[]);
    assert.deepEqual(cursor.observe(data,closedSignals([signal(1100)]),1200),['buy']);
    assert.deepEqual(cursor.observe(data,closedSignals([signal(1100)]),1300),[]);
    assert.deepEqual(cursor.observe(data,closedSignals([signal(950,'SELL')]),200000),[]);
    assert.deepEqual(cursor.observe({...data,timeframe:'1h'},closedSignals([signal(1100)]),1300),[]);
    assert.deepEqual(cursor.observe({...data,symbol:'BTCUSDT'},closedSignals([signal(1100)]),1300),[]);
});
test('sound preferences validate options and volume',()=>{
    assert.deepEqual(normalizeMomentum(),{buy:'none',sell:'none',volume:.35});
    assert.deepEqual(normalizeMomentum({buy:'bell',sell:'invalid',volume:9}),{buy:'bell',sell:'none',volume:1});
});


test('suppressed candidates and obsolete v2 rows cannot create markers or sounds',()=>{
    const bars=[{...signal(1000),momentum:{signal_type:null,decision_state:'SUPPRESSED'},adcn:{signal_type:'BUY',trigger:'DI_TURNING_POINT_V3'}},
        {adcn:{signal_type:'BUY',trigger:'DI_TURNING_POINT_V2'}}];
    assert.deepEqual(closedSignals(bars),[]);
    assert.deepEqual(closedSignals([{momentum:null,adcn:{signal_type:'BUY',trigger:'DI_TURNING_POINT_V3'}}]),[]);
});
