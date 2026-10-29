// Compact evidence labels; score percentages are not win probabilities.
export function confidenceLabel(bar,side,config){
    const name=side.toUpperCase();if(!config[`confidence_${side}`]?.visible)return name;
    const evidence=bar.confidence,state=evidence?.[`${side}_status`]??evidence?.status,score=evidence?.[`${side}_score`];
    return `${name}\n${state==='ready'&&Number.isFinite(score)?score.toFixed(0)+'%':'—'}`;
}
