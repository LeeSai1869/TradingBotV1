export function zoneReadiness(progress,frames,styles,timeframe){
    const currentFVG=['bull_fvg_zones','bear_fvg_zones',`bull_fvg_${timeframe}_zones`,`bear_fvg_${timeframe}_zones`].some(k=>styles[k]?.visible);
    const sr=['support_zones','resistance_zones','inst_support_zones','inst_resistance_zones'].some(k=>styles[k]?.visible);
    const waiting=(progress?.zone_repairs||[]).filter(group=>group==='FVG'?currentFVG:sr);
    const notices=waiting.length?[`Zone coverage pending feature repair: ${waiting.join(', ')}`]:[];
    if(sr&&!waiting.includes('Support / Resistance')&&['waiting for features','historical feature replay'].includes(progress?.status))notices.push('Support / Resistance: waiting for feature calculation');
    for(const [tf,frame] of Object.entries(frames||{})){
        if(!frame?.status||frame.status==='ready')continue;
        const enabled=tf==='current'?currentFVG:['bull','bear'].some(side=>styles[`${side}_fvg_${tf}_zones`]?.visible);
        if(enabled&&!(tf==='current'&&waiting.includes('FVG')))notices.push(`${tf==='current'?timeframe:tf} FVG: ${frame.status}`);
    }
    return notices.join(' | ');
}
