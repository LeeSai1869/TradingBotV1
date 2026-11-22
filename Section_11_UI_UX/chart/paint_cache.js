// One viewport-sized transparent bitmap per primitive layer. Nothing is persisted.
// Crosshair repaints reuse pixels; scale, pan, resize, data and styles invalidate.
export function viewportKey(chart,series,reference=1){
    const scale=chart.timeScale(),range=scale.getVisibleLogicalRange();
    return [range?.from,range?.to,scale.options().barSpacing,
        series.priceToCoordinate(reference),series.priceToCoordinate(reference*1.01)];
}
export class PaintCache {
    constructor(){this.canvas=null;this.key=null;this.stats={builds:0,hits:0,direct:0};}
    invalidate(){this.key=null;}
    clear(){this.key=null;if(this.canvas){this.canvas.width=0;this.canvas.height=0;}this.canvas=null;}
    draw(scope,key,paint){
        const {context,mediaSize}=scope,transform=context.getTransform?.();
        const fallback=()=>{this.stats.direct++;paint(scope);};
        // Preserve uncommon transforms and oversized canvases without caching.
        if(!transform||transform.b||transform.c||transform.e||transform.f||!(transform.a>0&&transform.d>0)||
            typeof document==='undefined'||globalThis.window?.ChartPaintCacheDisabled)return fallback();
        const width=Math.ceil(mediaSize.width*transform.a),height=Math.ceil(mediaSize.height*transform.d);
        if(!width||!height||width*height*4>16*1024*1024){this.clear();return fallback();}
        const signature=JSON.stringify([width,height,transform.a,transform.d,key]);
        if(signature!==this.key){
            let target;
            try{
                this.canvas??=document.createElement('canvas');
                if(this.canvas.width!==width||this.canvas.height!==height){this.canvas.width=width;this.canvas.height=height;}
                target=this.canvas.getContext('2d');
            }catch{this.clear();return fallback();}
            if(!target){this.clear();return fallback();}
            try{
                target.setTransform(1,0,0,1,0,0);target.clearRect(0,0,width,height);
                target.setTransform(transform.a,0,0,transform.d,0,0);
                paint({...scope,context:target});
                this.key=signature;this.stats.builds++;
            }catch(error){this.clear();throw error;}
        }else this.stats.hits++;
        try{context.drawImage(this.canvas,0,0,width,height,0,0,width/transform.a,height/transform.d);}
        catch{this.clear();return fallback();}
    }
}
