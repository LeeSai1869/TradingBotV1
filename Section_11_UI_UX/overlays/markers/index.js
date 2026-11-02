// Momentum uses the canonical closed-bar projection of the single Section 8 rule.
import {getSeries} from '../candles/index.js';
import {closedSignals} from './preferences.js';
import {SignalFlags} from './flags.js';
export const name='markers';
let primitive=null;
export function mount(){primitive=new SignalFlags();getSeries().attachPrimitive(primitive);}
export function update(chart,data,options={}) {
    const series=getSeries();if(!series)return;
    const config=globalThis.window?.Composer?.config||{}, styles=config.featureStyles||{};
    const signals=closedSignals(data.bars||[],styles,options.visible!==false);
    primitive.signals=signals;primitive.styles=styles;primitive.requestUpdate?.();
}
