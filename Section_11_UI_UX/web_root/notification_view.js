// Shared by the desktop chart and the installable mobile companion.
export const TOAST_LIFETIME_MS=20000;
const price=value=>Number.isFinite(value)?value.toLocaleString(undefined,{maximumSignificantDigits:10}):'Unavailable';
export function chartLink(event){return '/?'+new URLSearchParams({symbol:event.symbol,interval:event.interval,at:String(event.bar_time)});}
export function notificationView(event){
    const data=event.details||{};
    return {title:`${event.symbol} ${event.interval} ${data.side||event.name}`,
        time:new Date(data.signal_ms||event.created).toLocaleString(),url:chartLink(event),
        lines:[`Price ${price(data.price)} · Confidence ${price(data.confidence)}/100`,
            `Sell OZ · upper ${price(data.upper?.high)}`,`Buy OZ · lower ${price(data.lower?.low)}`]};
}
export function notificationCard(event,{open,ephemeral=false}={}){
    const view=notificationView(event),card=document.createElement('article');card.className='alert-toast';card.setAttribute('role','status');
    const close=document.createElement('button');close.textContent='×';close.className='alert-dismiss';close.setAttribute('aria-label','Dismiss notification');card.append(close);
    const link=document.createElement('a');link.href=view.url;link.className='alert-open';card.append(link);
    const time=document.createElement('time');time.textContent=view.time;link.append(time);
    const title=document.createElement('strong');title.textContent=view.title;link.append(title);
    for(const line of view.lines){const text=document.createElement('span');text.textContent=line;link.append(text);}
    if(open)link.onclick=event=>{event.preventDefault();open();};
    const timer=ephemeral?setTimeout(()=>card.remove(),TOAST_LIFETIME_MS):null;
    close.onclick=()=>{clearTimeout(timer);card.remove();};
    return card;
}
