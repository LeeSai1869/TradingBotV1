// Pure chart projection; no engine/store imports, network calls or DOM access.
import {segments} from './project.js';
self.onmessage=({data})=>{
    const {id,bars,config,frames,target}=data;
    const started=performance.now(),items=segments(bars,config,frames,target);
    self.postMessage({id,items,ms:Math.round(performance.now()-started)});
};
