import {formatValue,featurePriceFormat} from '../../web_root/value_format.js';
// Completed stored indicators use exactly the same canonical bars as candles.
import {FEATURE_STYLES} from '../../controls/settings/feature_styles.js';
export const name='indicators';
const groups=new Map();let chart, controls, observer, latestBar, hoverTime=null, barsByTime=new Map();
function values(){
    const bar=barsByTime.get(hoverTime)||latestBar;
    for(const state of groups.values())if(state.valueLabel){
        state.valueLabel.replaceChildren();
        for(const [key,label] of FEATURE_STYLES[state.feature].outputs)if(styles()[key]?.visible){
            const text=document.createElement("span");text.textContent=`${label} ${formatValue(bar?value(bar,key):null)}`;text.style.color=styles()[key].color;state.valueLabel.append(text);
        }
    }
}
const LOWER=['RSI','ADX','DI','ATR','Volume'];
function styles(){return window.Composer.config.featureStyles||{};}
function value(bar,key){const n=key==='volume'?bar.client?.volume:bar.features?.[key];return Number.isFinite(n)?n:null;}
function button(label,text,parent,action){const b=document.createElement('button');b.type='button';b.textContent=text;b.setAttribute('aria-label',label);b.onclick=action;parent.append(b);return b;}
function positionHeaders(){
    if(!chart)return;
    const outer=document.getElementById('chart').getBoundingClientRect();
    for(const state of groups.values())if(state.header){const row=state.pane.getHTMLElement();if(row)state.header.style.top=(row.getBoundingClientRect().top-outer.top+5)+'px';}
}
function create(feature){
    const state={feature,lines:new Map(),pane:['VWAP','WMA','Volume Profile'].includes(feature)?null:chart.addPane(true),header:null,collapsed:false,levels:[]};
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
        button(`Close ${feature}`,'×',header,()=>window.dispatchEvent(new CustomEvent('feature-visibility-change',{detail:{feature,visible:false}})));
    }
    for(const [key,label,,presentation='line'] of FEATURE_STYLES[feature].outputs){
        if(['zone','profile'].includes(presentation))continue;
        const line=chart.addSeries(presentation==='histogram'?LightweightCharts.HistogramSeries:LightweightCharts.LineSeries,
            {visible:false,title:'',priceLineVisible:false,lastValueVisible:true,crosshairMarkerVisible:true,
             priceFormat:featurePriceFormat},state.pane?.paneIndex()??0);
        state.lines.set(key,line);
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
        return info?{...info,priceRange:{minValue:Math.min(0,info.priceRange.minValue),maxValue:Math.max(30,info.priceRange.maxValue)}}:null;
    }});
}
export function mount(instance){
    chart=instance;chart.subscribeCrosshairMove(event=>{hoverTime=typeof event.time==='number'?event.time:null;values();});controls=document.createElement('div');controls.id='indicator-pane-controls';document.getElementById('chart').append(controls);
    observer=new ResizeObserver(()=>requestAnimationFrame(positionHeaders));observer.observe(document.getElementById('chart'));
}
export function update(instance,data){
    barsByTime=new Map((data.bars||[]).map(bar=>[bar.time,bar]));latestBar=data.bars?.at(-1);
    for(const feature of [...LOWER,'VWAP','WMA','Volume Profile']){
        const enabled=FEATURE_STYLES[feature].outputs.some(([key,,,presentation])=>!['zone','profile'].includes(presentation)&&styles()[key]?.visible);
        let state=groups.get(feature);
        if(!enabled){if(state)remove(state);continue;}
        if(!state)state=create(feature);
        for(const [key,line] of state.lines){
            const style=styles()[key];line.applyOptions({visible:!!style?.visible && !state.collapsed,color:style?.color,
                priceFormat:featurePriceFormat,
                lineWidth:style?.width||2,lineStyle:style?.style||0,lastValueVisible:!!style?.visible && !state.collapsed});
            if(!style?.visible)continue;
            line.setData((data.bars||[]).map(bar=>{
                const n=value(bar,key);if(n===null)return {time:bar.time};
                const point={time:bar.time,value:n};
                if(key==='volume')point.color=bar.client.close>=bar.client.open?style.color:'#ef5350';
                return point;
            }));
        }
        levels(state);
    }
    values();requestAnimationFrame(positionHeaders);
}
export function updateLive(instance,bar){
    if(!bar)return;
    latestBar=bar;barsByTime.set(bar.time,bar);values();
    for(const state of groups.values())for(const [key,line] of state.lines){
        if(!styles()[key]?.visible)continue;
        const n=value(bar,key);const point=n===null?{time:bar.time}:{time:bar.time,value:n};
        if(key==='volume' && n!==null)point.color=bar.client.close>=bar.client.open?styles()[key].color:'#ef5350';
        line.update(point);
    }
}
export function getSeries(key){for(const state of groups.values())if(state.lines.has(key))return state.lines.get(key);return null;}
