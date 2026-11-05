import {getSeries} from '../candles/index.js';
export const name='btc_strategy';
const STORAGE='tradingbot.btc-strategy.v1';
function savePreferences(){try{localStorage.setItem(STORAGE,JSON.stringify({enabled,days:Number(horizon.value)}));}catch{}}
let primitive,label,toggle,horizon,lastKey,lastData,enabled=false,scope='',lastFetch=0,serial=0,pending=false;
class StrategyVisual {
    attached({chart,series,requestUpdate}){Object.assign(this,{chart,series,requestUpdate});}
    detached(){this.chart=this.series=this.requestUpdate=null;}
    paneViews(){return [this];}
    renderer(){return this;}
    zOrder(){return 'top';}
    draw(target){
        if(!this.series||!enabled)return;
        target.useMediaCoordinateSpace(({context:ctx,mediaSize:size})=>{
            ctx.save();ctx.font='bold 11px sans-serif';
            const point=(t,p)=>[this.chart.timeScale().timeToCoordinate(t/1000),this.series.priceToCoordinate(p)];
            for(const observation of this.packet?.observations||[]){
                const [x,y]=point(observation.time,observation.price);if(x===null||y===null||x<0||x>size.width)continue;
                const confirmed=observation.type?.endsWith('CONFIRMED');
                ctx.fillStyle=confirmed?'#54d5e8':'#bba0f5';
                ctx.fillText(`${confirmed?'✓':'◇'} ${observation.type||'DI TURN'}`,x+5,y+18);
            }
            for(const trade of this.packet?.trades||[]){
                for(const [t,p,text,color] of [[trade.entry_time,trade.entry,'BTC BUY','#54d5e8'],[trade.exit_time,trade.exit,`BTC EXIT${Number.isFinite(trade.net_pct)?' '+trade.net_pct.toFixed(2)+'%':''}`,'#ffb454']]){
                    if(!Number.isFinite(t)||!Number.isFinite(p))continue;
                    const [x,y]=point(t,p);if(x===null||y===null||x<0||x>size.width)continue;
                    ctx.fillStyle=color;ctx.beginPath();ctx.arc(x,y,4,0,Math.PI*2);ctx.fill();ctx.fillText(text,x+6,y-8);
                }
            }
            for(const key of ['entry','hard_stop','stop']){
                ctx.strokeStyle={entry:'#54d5e8',hard_stop:'#e35c73',stop:'#ffb454'}[key];ctx.setLineDash(key==='entry'?[2,4]:[]);
                ctx.beginPath();let previous=null;
                for(const level of this.packet?.levels||[]){
                    if(key==='stop'&&level.stop===level.hard_stop){previous=null;continue;}
                    const [x,y]=point(level.time,level[key]);
                    if(x===null||y===null){previous=null;continue;}
                    if(previous&&level.entry_time===previous.entry_time)ctx.lineTo(x,y);else ctx.moveTo(x,y);
                    previous=level;
                }ctx.stroke();
            }
            ctx.restore();
        });
    }
}
export function mount(){
    primitive=new StrategyVisual();getSeries().attachPrimitive(primitive);
    let preferences={};try{preferences=JSON.parse(localStorage.getItem(STORAGE)||'{}')||{};}catch{}
    enabled=preferences.enabled===true;
    const box=document.createElement('div');box.id='btc-strategy-controls';
    Object.assign(box.style,{display:'inline-flex',alignItems:'center',gap:'6px',flexWrap:'wrap'});
    const toolbar=document.getElementById('toolbar');
    if(toolbar)toolbar.append(box);
    else{Object.assign(box.style,{position:'absolute',left:'8px',top:'45px',zIndex:29,color:'#bdeaf2'});document.getElementById('chart').append(box);}
    const control=document.createElement('label');toggle=document.createElement('input');toggle.type='checkbox';toggle.checked=enabled;toggle.setAttribute('aria-label','Show BTC strategy flags');control.append(toggle,document.createTextNode(' BTC strategy flags · experimental spot'));
    horizon=document.createElement('select');horizon.setAttribute('aria-label','BTC strategy history');
    for(const days of [7,30,90,365]){const option=document.createElement('option');option.value=days;option.textContent=days+' days';option.selected=days===( [7,30,90,365].includes(preferences.days)?preferences.days:90);horizon.append(option);}
    horizon.onchange=()=>{savePreferences();lastFetch=0;lastKey=null;serial++;pending=false;primitive.packet=null;primitive.requestUpdate?.();if(enabled&&lastData)update(null,lastData);};
    const eventButton=document.createElement('button');eventButton.textContent='BTC events';eventButton.onclick=showEvents;
    box.append(control,horizon,eventButton);
    label=document.createElement('div');label.setAttribute('role','status');label.id='btc-strategy-status';
    Object.assign(label.style,{position:'absolute',left:'8px',top:'45px',zIndex:29,fontSize:'11px',color:'#bdeaf2',maxWidth:'85%',pointerEvents:'none'});
    document.getElementById('chart').append(label);
    toggle.onchange=()=>{enabled=toggle.checked;savePreferences();lastKey=null;lastFetch=0;serial++;pending=false;primitive.packet=null;primitive.requestUpdate?.();if(!enabled)label.textContent='BTC strategy off — enable BTC strategy flags in the toolbar.';else if(lastData)update(null,lastData);};
}
export async function update(chart,data){
    lastData=data;
    const symbol=data.symbol,timeframe=data.timeframe;
    const supported=symbol==='BTCUSDT'&&['5m','15m','30m','1h'].includes(timeframe);
    const next=`${symbol}:${timeframe}:${data.atLiveEdge===false?'history':'latest'}`;
    if(scope!==next){scope=next;lastKey=null;serial++;pending=false;lastFetch=0;primitive.packet=null;primitive.requestUpdate?.();}
    toggle.disabled=!supported;horizon.disabled=!supported;
    if(!enabled){label.textContent=supported?'BTC strategy off — enable BTC strategy flags in the toolbar.':'BTC strategy supports BTCUSDT · 5m / 15m / 30m / 1h';return;}
    if(!supported){label.textContent='Choose BTCUSDT · 5m / 15m / 30m / 1h';return;}
    const end=data.bars?.filter(b=>!b.provisional).at(-1);
    const requestKey=`${scope}:${end?.time}:${horizon.value}`;
    if(pending||lastKey===requestKey||Date.now()-lastFetch<15000)return;
    const token=++serial;pending=true;lastFetch=Date.now();label.textContent='Loading stored strategy…';
    const query=new URLSearchParams({symbol,interval:timeframe,days:horizon.value});
    if(data.atLiveEdge===false&&end)query.set('before',String(end.client?.close_time+1||end.time*1000+1));
    try{
        const response=await fetch(`/api/strategy/btc?${query}`,{cache:'no-store',signal:AbortSignal.timeout(10000)}),packet=await response.json();
        if(token!==serial)return;
        if(!response.ok)throw new Error(packet.error||'Strategy unavailable');
        if(packet.status==='READY')lastKey=requestKey;
        primitive.packet=packet;primitive.requestUpdate?.();
        const open=packet.trades?.find(t=>t.status==='OPEN');
        label.textContent=packet.status==='READY'?`Simulated · ${horizon.value} days · starts flat at history boundary · ${packet.version||'event sequence'} · ${packet.candles} candles · ${packet.total_trades??packet.trades.length} entries · from ${packet.window_start!=null?new Date(packet.window_start).toISOString().slice(0,10):'start'} · through ${packet.window_end?new Date(packet.window_end).toISOString().slice(0,16)+'Z':'window end'} · ${open?'holding BTC':'flat'} · cyan DI turn & entry / red hard stop / amber trail · 0.5% activates trail · costs included${packet.gaps?' · gaps censored':''}`:packet.reason;
        boxTitle(packet);
    }catch(error){if(token===serial){primitive.packet=null;primitive.requestUpdate?.();label.textContent=error.message;}}
    finally{if(token===serial)pending=false;}
}
function boxTitle(packet){label.title=`${packet.interpretation||''}\nWindow starts flat; earlier positions excluded. Confirmed closed candles only. 0.5% hard stop is a price threshold, not a guaranteed loss cap; gaps and costs can exceed it. Trend/regime filters and confidence calibration are pending.`;}

function showEvents(){
    document.getElementById('btc-events-dialog')?.remove();
    const dialog=document.createElement('dialog');dialog.id='btc-events-dialog';dialog.setAttribute('aria-label','BTC strategy events');
    Object.assign(dialog.style,{width:'min(1100px,95vw)',maxHeight:'85vh',overflow:'auto',background:'#181d25',color:'#ddd',border:'1px solid #52647d',padding:'16px'});
    const title=document.createElement('h2');title.textContent='BTC strategy event sequence';
    const close=document.createElement('button');close.textContent='Close events';close.onclick=()=>dialog.close();
    const note=document.createElement('p');note.textContent='Latest 300 events from the chart response. Times are UTC. A DI turn is known at the third candle close; confirmed DI turns are eligible at that close and fill at the next open. Price and candidates provide confluence only; there is no price-break gate.';
    dialog.append(title,close,note);
    const events=(primitive.packet?.events||[]).slice(-300);
    if(!events.length){const empty=document.createElement('p');empty.textContent=primitive.packet?.reason||'Enable BTC strategy flags and load data to inspect events.';dialog.append(empty);}
    const table=document.createElement('table');table.style.width='100%';table.style.fontSize='12px';
    const head=document.createElement('tr');for(const text of ['Known UTC','Event','DI+','DI−','Spread','Turn origin UTC','Before → Turn → After','Detail']){const cell=document.createElement('th');cell.textContent=text;head.append(cell);}table.append(head);
    const date=value=>Number.isFinite(value)?new Date(value).toISOString().replace('T',' ').slice(0,19):'—';
    const number=value=>Number.isFinite(value)?value.toFixed(2):'—';
    for(const event of events){
        const row=document.createElement('tr'),context=event.context||event.at_detection||{};
        for(const text of [date(event.known_time),event.type.replaceAll('_',' '),number(context.di_plus),number(context.di_minus),number(context.spread),date(event.origin_time??event.turn_origin_time),(event.values||[]).map(number).join(' → '),event.reason||context.dominant||'']){
            const cell=document.createElement('td');cell.textContent=text;cell.style.padding='5px';row.append(cell);
        }table.append(row);
    }
    dialog.append(table);document.body.append(dialog);dialog.showModal();
}
