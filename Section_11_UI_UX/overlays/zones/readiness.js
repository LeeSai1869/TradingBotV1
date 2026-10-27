export function zoneReadiness(progress,frames,styles,timeframe,institutional={}){
    const currentFVG=['bull_fvg_zones','bear_fvg_zones',`bull_fvg_${timeframe}_zones`,`bear_fvg_${timeframe}_zones`].some(k=>styles[k]?.visible);
    const sr=['support_zones','resistance_zones','inst_support_zones','inst_resistance_zones'].some(k=>styles[k]?.visible);
    const ob=Object.entries(styles).some(([key,value])=>/_(ob|breaker)_zones$/.test(key)&&value?.visible);
    const waiting=(progress?.zone_repairs||[]).filter(group=>group==='FVG'?currentFVG:group==='Order Blocks'?ob:sr);
    const notices=waiting.length?[`Zone coverage pending feature repair: ${waiting.join(', ')}`]:[];
    if(sr&&!waiting.includes('Support / Resistance')&&['waiting for features','historical feature replay'].includes(progress?.status))notices.push('Support / Resistance: waiting for feature calculation');
    if(ob&&!waiting.includes('Order Blocks')&&['waiting for features','historical feature replay'].includes(progress?.status))notices.push('Order Blocks: waiting for feature calculation');
    for(const [tf,frame] of Object.entries(frames||{})){
        if(!frame?.status||frame.status==='ready')continue;
        const enabled=tf==='current'?currentFVG:['bull','bear'].some(side=>styles[`${side}_fvg_${tf}_zones`]?.visible);
        if(enabled&&!(tf==='current'&&waiting.includes('FVG')))notices.push(`${tf==='current'?timeframe:tf} FVG: ${frame.status}`);
    }
    if(['support','resistance'].some(side=>styles[`inst_${side}_zones`]?.visible&&styles[`inst_${side}_zones`]?.higher!==false)){
        const pending=Object.entries(institutional||{}).filter(([,frame])=>!frame||frame.status!=='ready'||frame.current===false).map(([tf])=>tf);
        if(pending.length)notices.push(`Institutional source coverage pending: ${pending.join(', ')}`);
    }
    return notices.join(' | ');
}
