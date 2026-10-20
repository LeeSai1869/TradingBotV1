// The free corner resizes inward/outward while keeping the chosen anchor fixed.
export function mountResize(hud,preferences) {
    const handle=document.createElement('button');handle.className='hud-resize';
    handle.setAttribute('aria-label','Resize HUD');handle.title='Drag to resize HUD; arrow keys adjust size';hud.append(handle);
    let drag;
    function update(width,height) {
        const parent=hud.parentElement;
        width=Math.max(Math.min(180,parent.clientWidth-105),Math.min(width,parent.clientWidth-105));
        height=Math.max(Math.min(100,parent.clientHeight-85),Math.min(height,parent.clientHeight-85));
        hud.style.width=width+'px';hud.style.height=height+'px';
        return {width,height};
    }
    function save(){const box=hud.getBoundingClientRect();window.dispatchEvent(new CustomEvent('hud-size-change',{detail:{width:Math.round(box.width),height:Math.round(box.height)}}));}
    handle.onpointerdown=event=>{
        if(event.button!==0)return;event.preventDefault();event.stopPropagation();
        const box=hud.getBoundingClientRect(), position=preferences().position;
        drag={x:event.clientX,y:event.clientY,width:box.width,height:box.height,
            dx:position.endsWith('right')?-1:1,dy:position.startsWith('bottom')?-1:1};
        handle.setPointerCapture(event.pointerId);
    };
    handle.onpointermove=event=>{if(drag)update(drag.width+(event.clientX-drag.x)*drag.dx,drag.height+(event.clientY-drag.y)*drag.dy);};
    handle.onpointerup=event=>{if(!drag)return;drag=null;save();if(handle.hasPointerCapture(event.pointerId))handle.releasePointerCapture(event.pointerId);};
    handle.onpointercancel=()=>{if(drag){drag=null;save();}};
    handle.onkeydown=event=>{
        if(!['ArrowLeft','ArrowRight','ArrowUp','ArrowDown'].includes(event.key))return;
        event.preventDefault();const box=hud.getBoundingClientRect();
        update(box.width+(event.key==='ArrowRight'?10:event.key==='ArrowLeft'?-10:0),box.height+(event.key==='ArrowDown'?10:event.key==='ArrowUp'?-10:0));save();
    };
}
