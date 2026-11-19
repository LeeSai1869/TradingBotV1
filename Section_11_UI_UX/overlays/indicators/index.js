import {formatTurnover, isUSDT, turnover, turnoverPriceFormat, TURNOVER_AVERAGE_BARS} from '../../web_root/quote_volume.js';
import {formatValue,featurePriceFormat} from '../../web_root/value_format.js';
// Completed stored indicators use exactly the same canonical bars as candles.
import {FEATURE_STYLES} from '../../controls/settings/feature_styles.js';
import {PANE_FEATURES} from '../../controls/settings/feature_legend.js';
export const name='indicators';
const groups=new Map();let chart, controls, observer, latestBar, hoverTime=null, barsByTime=new Map();
let turnoverAverages = new Map(), turnoverTail = [], quoteVolume = false;
function averageTurnover(points) {
    if (points.length < TURNOVER_AVERAGE_BARS || points.some(point => !point)) return null;
    return {value: points.reduce((sum, point) => sum + point.value, 0) / TURNOVER_AVERAGE_BARS,
        estimated: points.some(point => point.estimated)};
}
function updateTurnover(bars) {
    quoteVolume = isUSDT(bars.at(-1));
    turnoverAverages = new Map();
    turnoverTail = [];
    if (!quoteVolume || !['volume', 'volume_ma'].some(key => styles()[key]?.visible)) return;
    for (const bar of bars) {
        turnoverTail.push(turnover(bar));
        if (turnoverTail.length > TURNOVER_AVERAGE_BARS) turnoverTail.shift();
        turnoverAverages.set(bar.time, averageTurnover(turnoverTail));
    }
}
function values(){
    const bar=barsByTime.get(hoverTime)||latestBar;
    for(const state of groups.values())if(state.valueLabel){
        const labels = [];
        for(const [key,label] of FEATURE_STYLES[state.feature].outputs)if(styles()[key]?.visible||window.Composer.config.hiddenFeatures?.[state.feature]?.includes(key)){
            let text = `${label} ${formatValue(bar ? value(bar,key) : null)}`;
            if (quoteVolume && key === 'volume') text = `Turnover ${formatTurnover(turnover(bar))}`;
            if (quoteVolume && key === 'volume_ma') text = `Turnover SMA (${TURNOVER_AVERAGE_BARS}) ${formatTurnover(turnoverAverages.get(bar?.time))}`;
            labels.push([text, styles()[key].color]);
        }
        const signature = JSON.stringify(labels);
        if (signature === state.labelSignature) continue;
        state.labelSignature = signature;
        state.valueLabel.replaceChildren(...labels.map(([label,color]) => {
            const text = document.createElement("span");
            text.textContent = label;
            text.style.color = color;
            return text;
        }));
    }
}
const LOWER=PANE_FEATURES;
function styles(){return window.Composer.config.featureStyles||{};}
function value(bar,key){
    if (quoteVolume && key === 'volume') return turnover(bar)?.value ?? null;
    if (quoteVolume && key === 'volume_ma') return turnoverAverages.get(bar.time)?.value ?? null;
    const n=key==='volume'?bar.client?.volume:bar.features?.[key];
    return Number.isFinite(n)?n:null;
}
function button(label,text,parent,action){const b=document.createElement('button');b.type='button';b.textContent=text;b.setAttribute('aria-label',label);b.onclick=action;parent.append(b);return b;}
function positionHeaders(){
    if(!chart)return;
    const main=chart.panes()[0]?.getHTMLElement();if(main)main.dataset.mainPane='';
    const outer=document.getElementById('chart').getBoundingClientRect();
    for(const state of groups.values())if(state.header){const row=state.pane.getHTMLElement();if(row){row.dataset.featurePane=state.feature;state.header.style.top=(row.getBoundingClientRect().top-outer.top+5)+'px';}}
}
function addOutput(state, presentation) {
    return chart.addSeries(presentation === 'histogram' ? LightweightCharts.HistogramSeries : LightweightCharts.LineSeries,
        {visible: false, title: '', priceLineVisible: false, lastValueVisible: true,
         crosshairMarkerVisible: true, priceFormat: featurePriceFormat}, state.pane?.paneIndex() ?? 0);
}
function indicatorPoint(bar, key, style) {
    const n = value(bar, key);
    if (n === null) return {time: bar.time};
    const point = {time: bar.time, value: n};
    if (key === 'volume' && style.presentation !== 'line') {
        point.color = bar.client.close >= bar.client.open ? style.color : (style.downColor ?? '#ef5350');
    }
    return point;
}
function create(feature){
    const state={feature,lines:new Map(),pane:['VWAP','WMA','Volume Profile','Market Structure'].includes(feature)?null:chart.addPane(true),header:null,collapsed:false,levels:[]};
    if(state.pane){
        state.pane.setStretchFactor(.5);
        const header=document.createElement('div');header.className='indicator-pane-header';header.dataset.feature=feature;
        header.setAttribute('role','group');header.setAttribute('aria-label',`${feature} pane controls`);controls.append(header);state.header=header;
        const collapse=button(`Collapse ${feature}`,'▾',header,()=>{
            state.collapsed=!state.collapsed;
            collapse.textContent=state.collapsed?'▸':'▾';collapse.setAttribute('aria-label',`${state.collapsed?'Expand':'Collapse'} ${feature}`);
            collapse.setAttribute('aria-expanded',String(!state.collapsed));
            for(const [key,line] of state.lines)line.applyOptions({visible:!state.collapsed && styles()[key]?.visible===true});
            state.pane.setHeight(state.collapsed?34:150);requestAnimationFrame(positionHeaders);
        });collapse.setAttribute('aria-expanded','true');
        const title=document.createElement('strong');title.textContent=feature;header.append(title);
        state.valueLabel=document.createElement("span");state.valueLabel.className="indicator-values";state.valueLabel.setAttribute("aria-label",`${feature} values`);header.append(state.valueLabel);
        button(`${feature} settings`,'⚙',header,()=>window.dispatchEvent(new CustomEvent('open-feature-settings',{detail:feature})));
        state.toggle=button(`Hide ${feature} on chart`,'◎',header,()=>window.dispatchEvent(new CustomEvent('feature-legend-action',{detail:{feature,action:state.hidden?'show':'hide'}})));
        state.toggle.dataset.featureToggle='';
        button(`Close ${feature}`,'×',header,()=>window.dispatchEvent(new CustomEvent('feature-legend-action',{detail:{feature,action:'remove'}})));
    }
    for(const [key,,,presentation='line'] of FEATURE_STYLES[feature].outputs){
        if(['zone','profile'].includes(presentation))continue;
        const type = key === 'volume' ? (styles()[key]?.presentation ?? presentation) : presentation;
        state.lines.set(key, addOutput(state, type));
        if (key === 'volume') state.volumePresentation = type;
    }
    groups.set(feature,state);
    if(state.pane){const node=state.pane.getHTMLElement();if(node)observer.observe(node);}
    return state;
}
function remove(state){
    state.header?.remove();if(state.pane){const node=state.pane.getHTMLElement();if(node)observer.unobserve(node);chart.removePane(state.pane.paneIndex());}
    else for(const line of state.lines.values())chart.removeSeries(line);
    groups.delete(state.feature);
}
function levels(state){
    if(!['RSI','ADX'].includes(state.feature))return;
    const line=state.lines.get(state.feature==='ADX'?'adx':'rsi');for(const level of state.levels)line.removePriceLine(level);
    const config=window.Composer.config.rsiLevels||{lower:30,upper:70};
    state.levels=(state.feature==='ADX'?[25]:[config.lower,config.upper]).map(price=>line.createPriceLine({price,color:'#748298',lineWidth:1,lineStyle:2,axisLabelVisible:true,title:''}));
    if(state.feature==='RSI')line.applyOptions({autoscaleInfoProvider:()=>({priceRange:{minValue:0,maxValue:100}})});
    else line.applyOptions({autoscaleInfoProvider:original=>{
        const info=original();
        if (!info?.priceRange) return info;
        return {...info, priceRange:{
            minValue: Math.min(0, info.priceRange.minValue),
            maxValue: Math.max(30, info.priceRange.maxValue)
        }};
    }});
}
export function mount(instance){
    chart=instance;chart.subscribeCrosshairMove(event=>{hoverTime=typeof event.time==='number'?event.time:null;values();});controls=document.createElement('div');controls.id='indicator-pane-controls';document.getElementById('chart').append(controls);
    observer=new ResizeObserver(()=>requestAnimationFrame(positionHeaders));observer.observe(document.getElementById('chart'));
}
export function update(instance,data,options={}){
    barsByTime=new Map((data.bars||[]).map(bar=>[bar.time,bar]));latestBar=data.bars?.at(-1);
    updateTurnover(data.bars || []);
    for(const feature of [...LOWER,'VWAP','WMA','Volume Profile','Market Structure']){
        const enabled=FEATURE_STYLES[feature].outputs.some(([key,,,presentation])=>!['zone','profile'].includes(presentation)&&styles()[key]?.visible);
        let state=groups.get(feature);
        const hidden=LOWER.includes(feature)&&!!window.Composer.config.hiddenFeatures?.[feature]?.length;
        if(!enabled&&!hidden){if(state)remove(state);continue;}
        if(!state)state=create(feature);
        state.hidden=hidden;
        if(state.header){
            state.header.dataset.hidden=String(hidden);
            const label=`${hidden?'Show':'Hide'} ${feature} on chart`;
            state.toggle.textContent=hidden?'◉':'◎';state.toggle.setAttribute('aria-label',label);state.toggle.title=label;
            state.toggle.setAttribute('aria-pressed',String(!hidden));
        }
        for(const [key,output] of state.lines){
            const style = styles()[key];
            let line = output;
            const presentation = style?.presentation ?? 'histogram';
            if (key === 'volume' && state.volumePresentation !== presentation) {
                line = addOutput(state, presentation);
                chart.removeSeries(output);
                state.lines.set(key, line);
                state.volumePresentation = presentation;
            }
            line.applyOptions({visible:!!style?.visible && !state.collapsed,color:style?.color,
                priceFormat:quoteVolume && state.feature === 'Volume' ? turnoverPriceFormat : featurePriceFormat,
                lineWidth:style?.width||2,lineStyle:style?.style||0,lastValueVisible:!!style?.visible && !state.collapsed});
            if(!style?.visible){if(line.data().length)line.setData([]);continue;}
            if(options.resetViewport)line.priceScale().applyOptions({autoScale:true});
            line.setData((data.bars||[]).map(bar => indicatorPoint(bar, key, style)));
        }
        levels(state);
    }
    values();requestAnimationFrame(positionHeaders);
}
export function updateLive(instance,bar){
    if(!bar)return;
    if (quoteVolume && turnoverTail.length) {
        if (latestBar?.time === bar.time) turnoverTail[turnoverTail.length - 1] = turnover(bar);
        else {
            turnoverTail.push(turnover(bar));
            if (turnoverTail.length > TURNOVER_AVERAGE_BARS) turnoverTail.shift();
        }
        turnoverAverages.set(bar.time, averageTurnover(turnoverTail));
    }
    latestBar=bar;barsByTime.set(bar.time,bar);values();
    for(const state of groups.values())for(const [key,line] of state.lines){
        const style = styles()[key];
        if (style?.visible) line.update(indicatorPoint(bar, key, style));
    }
}
export function getSeries(key){for(const state of groups.values())if(state.lines.has(key))return state.lines.get(key);return null;}

export function clear(){barsByTime=new Map();latestBar=null;updateTurnover([]);for(const state of groups.values())for(const line of state.lines.values())line.setData([]);values();}
