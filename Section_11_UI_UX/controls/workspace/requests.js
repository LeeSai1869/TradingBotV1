// Optional HUD requests must settle even if the UI backend is unreachable.
export async function hudRequest(url, {signal, timeoutMs=8000}={}) {
    const controller=new AbortController();
    let timedOut=false;
    const abort=()=>controller.abort();
    if(signal?.aborted)abort();else signal?.addEventListener('abort',abort,{once:true});
    const timer=setTimeout(()=>{timedOut=true;controller.abort();},timeoutMs);
    try {
        const response=await fetch(url,{cache:'no-store',signal:controller.signal});
        const packet=await response.json();
        if(!response.ok)throw new Error(packet.error || `HUD request failed (HTTP ${response.status}).`);
        return packet;
    } catch(error) {
        if(timedOut)throw new Error('HUD server did not respond. Retry or restart the UI server.');
        if(error.name==='AbortError')throw error;
        if(error instanceof TypeError)throw new Error('Cannot reach the UI server. Run python3 restart_ui.py, then retry.');
        throw error;
    } finally {
        clearTimeout(timer);signal?.removeEventListener('abort',abort);
    }
}
