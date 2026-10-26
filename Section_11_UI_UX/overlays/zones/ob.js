// The sparse ledger is authoritative. Latest-block scalar outputs are never
// used as evidence that an older block disappeared.
import {srSegments} from './sr.js';
export function obSegments(bars,config,snapshot=null){
    return srSegments(bars,config,snapshot?{through:snapshot.through,zones:snapshot.ob_zones||{}}:null,{
        field:'ob_zone_events',
        keys:z=>[`${z.strict?'strict':'normal'}_${z.side}_${z.kind}_zones`],
        score:z=>z.strength,
    });
}
