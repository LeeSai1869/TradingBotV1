// Cache only the visual projection; feature calculations and stored rows stay canonical.
const fields=['sr_zone_events','ob_zone_events','current_structure','structure_origin_bar',
    'structure_start_bar','structure_range_low','structure_range_high'];
for(const side of ['support','resistance','inst_support','inst_resistance'])
    fields.push(side+'_zone_low',side+'_zone_high','nearest_'+side+'_zone_id','nearest_'+side+'_score');
for(const side of ['bull','bear'])fields.push(`qualified_${side}_fvg`,`${side}_fvg_low`,`${side}_fvg_high`,
    ...['low','high','created_bar','age'].map(key=>`nearest_${side}_fvg_${key}`),`nearest${side}_fvg_reaction_score`);
export function projectionRows(rows){return rows.map(row=>({time:row.time,provisional:row.provisional,
    client:{open_time:row.client?.open_time,close_time:row.client?.close_time,low:row.client?.low,high:row.client?.high,close:row.client?.close},
    features:Object.fromEntries(fields.map(field=>[field,row.features?.[field]]))}));}
function key(row){const c=row.client||{},f=row.features||{};return [row.time,c.open_time,c.close_time,c.low,c.high,c.close,...fields.map(field=>f[field])];}
function equal(a,b){return a.length===b.length&&a.every((value,i)=>Object.is(value,b[i]));}
export class ProjectionCache {
    constructor(project){this.project=project;this.reset();this.builds=0;this.hits=0;}
    reset(){this.keys=null;this.frameRefs=null;this.items=[];this.ends=[];}
    get(data,styles){
        const rows=(data.bars||[]).filter(bar=>!bar.provisional);
        const keys=rows.map(key),settings=JSON.stringify(styles);
        const refs=[data.srSnapshot,...Object.entries(data.fvgFrames||{}).flat(),...Object.entries(data.srFrames||{}).flat()];
        const scope=`${data.symbol}:${data.timeframe}`,edge=data.bars?.at(-1)?.time;
        const valid=this.keys&&this.scope===scope&&this.edge===edge&&this.settings===settings&&equal(this.frameRefs,refs)&&
            keys.length===this.keys.length&&keys.every((row,i)=>equal(row,this.keys[i]));
        if(valid)this.hits++;
        else{
            this.items=this.project(data.bars||[],styles,{...data.fvgFrames,sr:data.srSnapshot,institutional:data.srFrames},data.timeframe);
            this.ends=this.items.map(item=>item.end);
            this.keys=keys;this.settings=settings;this.scope=scope;this.edge=edge;this.frameRefs=refs;this.builds++;
        }
        // Live extension mutates display endpoints, never the closed projection.
        this.items.forEach((item,i)=>item.end=this.ends[i]);
        return this.items;
    }
}
