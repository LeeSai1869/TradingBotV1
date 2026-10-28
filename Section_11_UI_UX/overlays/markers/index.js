// Momentum uses the canonical closed-bar projection of the single Section 8 rule.
import {getSeries} from '../candles/index.js';
import {closedSignals,SignalCursor,normalizeMomentum,signalReference,signalPlacement} from './preferences.js';
import {confidenceLabel} from '../opportunity/index.js';
import {playSignalSound} from '../../controls/alerts/index.js';
export const name='markers';
let primitive=null;
const cursor=new SignalCursor();
export function mount(){}
export function update(chart,data,options={}) {
    const series=getSeries();if(!series)return;
    const config=globalThis.window?.Composer?.config||{}, styles=config.featureStyles||{};
    const signals=closedSignals(data.bars||[],styles,options.visible!==false);
    const markers=signals.map(({bar,side})=>{
        const style=styles[`momentum_${side}`]||{},buy=side==='buy',reference=signalReference(bar);
        return {time:bar.time,...signalPlacement(bar,side),color:style.color||(buy?'#26a69a':'#ef5350'),
            shape:style.shape||(buy?'arrowUp':'arrowDown'),text:style.label===false?'':confidenceLabel(bar,side,styles)+(reference!==null?` @ ${reference.toPrecision(7)}`:''),size:style.width||2};
    }).sort((a,b)=>a.time-b.time);
    if(typeof LightweightCharts.createSeriesMarkers==='function') {
        if(!primitive)primitive=LightweightCharts.createSeriesMarkers(series,markers);
        else primitive.setMarkers(markers);
    }
    const sounds=normalizeMomentum(config.momentumSounds);
    const fresh=cursor.observe(data,closedSignals(data.bars||[]));
    if(!['reload','history','settings'].includes(options.op)&&options.visible!==false)
        for(const side of fresh)if(styles[`momentum_${side}`]?.visible!==false)playSignalSound(sounds[side],sounds.volume);
}
