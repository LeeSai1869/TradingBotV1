import {fvgSegments} from './fvg.js';
import {structureSegments} from './structure.js';
import {srSegments,institutionalProjection,srRole} from './sr.js';
import {obSegments} from './ob.js';
export function segments(bars,config,frames={},target=''){
    const result=[];
    if(['support','resistance','inst_support','inst_resistance'].some(key=>config[key+'_zones']?.visible))result.push(...srSegments(bars,config,frames.sr));
    if(Object.entries(config).some(([key,value])=>/_(ob|breaker)_zones$/.test(key)&&value?.visible))result.push(...obSegments(bars,config,frames.sr));
    result.push(...structureSegments(bars,config));
    for(const [source,frame] of Object.entries(frames.institutional||{}))result.push(...institutionalProjection(bars,config,frame,source));
    for(const item of result)if(/^(inst_)?(support|resistance)_zones$/.test(item.key))item.role=srRole(item,bars);
    const endTime=bars.at(-1)?.time;
    result.push(...fvgSegments(bars,config,{target,endTime,seeds:frames.current?.active}));
    for(const [source,frame] of Object.entries(frames))if(source!=='current'&&source!=='sr'&&source!=='institutional')result.push(...fvgSegments(frame.bars||[],config,{source,target,endTime,seeds:frame.active}));
    return result;
}
