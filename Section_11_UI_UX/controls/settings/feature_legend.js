import {FEATURE_STYLES} from './feature_styles.js';

export function hiddenFeatures(value,outputs){
    const result={};
    for(const [name,feature] of Object.entries(FEATURE_STYLES)){
        const keys=new Set(feature.outputs.map(([key])=>key));
        const hidden=Array.isArray(value?.[name])?value[name].filter(key=>keys.has(key)):[];
        if(hidden.length&&!feature.outputs.some(([key])=>outputs[key]?.visible))result[name]=hidden;
    }
    return result;
}

export function legendEntries(preferences){
    return Object.entries(FEATURE_STYLES).filter(([name,feature])=>feature.connected&&(
        preferences.hiddenFeatures?.[name]?.length || feature.outputs.some(([key])=>preferences.outputs[key]?.visible)
        && (name!=='EMA'||preferences.ema!==false) && (name!=='Momentum Indicator'||preferences.markers!==false)
    )).map(([name])=>({name,hidden:!!preferences.hiddenFeatures?.[name]?.length}));
}

export function changeFeature(preferences,name,action){
    const feature=FEATURE_STYLES[name];
    if(!feature||!['hide','show','remove'].includes(action))return preferences;
    const next=structuredClone(preferences);
    next.hiddenFeatures??={};
    if(action==='hide'){
        const visible=feature.outputs.filter(([key])=>next.outputs[key]?.visible).map(([key])=>key);
        if(visible.length)next.hiddenFeatures[name]=visible;
    }
    for(const [key] of feature.outputs)next.outputs[key].visible=action==='show'&&next.hiddenFeatures[name]?.includes(key)===true;
    if(action==='show'){
        if(name==='EMA')next.ema=true;
        if(name==='Momentum Indicator')next.markers=true;
    }
    if(action!=='hide')delete next.hiddenFeatures[name];
    return next;
}

export function renderLegend(preferences,onChange){
    const chart=document.getElementById('chart');if(!chart)return;
    let legend=document.getElementById('feature-legend');
    if(!legend){legend=document.createElement('div');legend.id='feature-legend';legend.setAttribute('role','region');legend.setAttribute('aria-label','Chart features');chart.append(legend);
        new ResizeObserver(()=>chart.style.setProperty('--feature-legend-bottom',`${legend.hidden?76:legend.offsetTop+legend.offsetHeight+6}px`)).observe(legend);
    }
    // Keep controls stable during candle updates and preserve keyboard focus.
    const entries=legendEntries(preferences);
    const identity=JSON.stringify(entries);
    if(legend.dataset.entries===identity)return;
    legend.dataset.entries=identity;legend.replaceChildren();legend.hidden=!entries.length;
    for(const {name,hidden} of entries){
        const row=document.createElement('div');row.className='feature-legend-row';row.dataset.feature=name;row.dataset.hidden=String(hidden);
        const title=document.createElement('button');title.type='button';title.className='feature-legend-name';title.textContent=name;title.title=`${name} settings`;
        title.setAttribute('aria-label',`${name} feature settings`);
        title.onclick=()=>window.dispatchEvent(new CustomEvent('open-feature-settings',{detail:name}));row.append(title);
        for(const [action,text,label] of [[hidden?'show':'hide',hidden?'◉':'◎',`${hidden?'Show':'Hide'} ${name} on chart`],['remove','×',`Remove ${name} from chart`]]){
            const button=document.createElement('button');button.type='button';button.textContent=text;button.title=label;button.setAttribute('aria-label',label);
            if(action!=='remove'){
                button.textContent='';button.setAttribute('aria-pressed',String(!hidden));
                const ns='http://www.w3.org/2000/svg',icon=document.createElementNS(ns,'svg');
                for(const [key,value] of Object.entries({viewBox:'0 0 24 24',width:'15',height:'15',fill:'none',stroke:'currentColor','stroke-width':'1.6','aria-hidden':'true'}))icon.setAttribute(key,value);
                for(const d of ['M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12Z','M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0',...(hidden?['M3 3l18 18']:[])]){
                    const path=document.createElementNS(ns,'path');path.setAttribute('d',d);icon.append(path);
                }
                button.append(icon);
            }
            button.onclick=()=>onChange(name,action);row.append(button);
        }
        legend.append(row);
    }
}
