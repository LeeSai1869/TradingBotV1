// One account event cursor, independent of charts and recoverable after suspension.
export function createAlertFeed({request,onHistory,onEvent,onState=()=>{},schedule=setTimeout,cancel=clearTimeout,interval=2000}) {
    let cursor=null,active=false,busy=false,timer=null,pending=false;
    function clear(){if(timer!==null)cancel(timer);timer=null;}
    async function poll(){
        if(!active)return;
        if(busy){pending=true;return;}
        clear();busy=true;pending=false;
        try{
            const packet=await request('/api/alerts/events'+(cursor===null?'':`?after=${cursor}`));
            if(!Number.isSafeInteger(packet.cursor)||packet.cursor<0||!Array.isArray(packet.events))throw Error('Invalid notification feed response');
            if(cursor!==null&&packet.cursor<cursor)throw Error('Notification feed cursor moved backwards');
            if(cursor===null)onHistory(packet.history||[]);
            for(const event of packet.events)onEvent(event);
            cursor=packet.cursor;onState(null);
        }catch(error){onState(error);}
        finally{
            busy=false;
            if(active){const delay=pending?0:interval;pending=false;timer=schedule(poll,delay);}
        }
    }
    return {
        start(){active=true;void poll();},
        pause(){active=false;pending=false;clear();},
        wake(){if(active)void poll();},
    };
}

export function watchAlertFeed(feed,win=window,doc=document){
    const restore=()=>feed.start();
    const visible=()=>{if(doc.visibilityState==='visible')feed.start();};
    const pause=()=>feed.pause();
    win.addEventListener('pageshow',restore);
    win.addEventListener('focus',restore);
    win.addEventListener('online',restore);
    win.addEventListener('pagehide',pause);
    doc.addEventListener('visibilitychange',visible);
    feed.start();
    return ()=>{
        feed.pause();win.removeEventListener('pageshow',restore);win.removeEventListener('focus',restore);
        win.removeEventListener('online',restore);win.removeEventListener('pagehide',pause);doc.removeEventListener('visibilitychange',visible);
    };
}
