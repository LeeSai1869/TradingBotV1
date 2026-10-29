// Momentum uses the canonical closed-bar projection of the single Section 8 rule.
import {getSeries} from '../candles/index.js';
import {closedSignals,SignalCursor,normalizeMomentum} from './preferences.js';
import {SignalFlags} from './flags.js';
import {playSignalSound} from '../../controls/alerts/index.js';
export const name='markers';
let primitive=null;
const cursor=new SignalCursor();
export function mount(){primitive=new SignalFlags();getSeries().attachPrimitive(primitive);}
export function update(chart,data,options={}) {
    const series=getSeries();if(!series)return;
    const config=globalThis.window?.Composer?.config||{}, styles=config.featureStyles||{};
    const signals=closedSignals(data.bars||[],styles,options.visible!==false);
    primitive.signals=signals;primitive.styles=styles;primitive.requestUpdate?.();
    const sounds=normalizeMomentum(config.momentumSounds);
    const fresh=cursor.observe(data,closedSignals(data.bars||[]));
    if(!['reload','history','settings'].includes(options.op)&&options.visible!==false)
        for(const side of fresh)if(styles[`momentum_${side}`]?.visible!==false)playSignalSound(sounds[side],sounds.volume);
}
