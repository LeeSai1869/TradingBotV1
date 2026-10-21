// CONTROL: symbol dropdown + per-symbol price format.
import { setPriceFormat } from "../../overlays/candles/index.js";
export const name = "symbol";
const el = () => document.getElementById("symbol");
let populateId = 0;
let search,list,active=0,matches=[];
const names={BTCUSDT:'Bitcoin',ETHUSDT:'Ethereum',SUIUSDT:'Sui',BNBUSDT:'BNB',SOLUSDT:'Solana',XRPUSDT:'XRP',ADAUSDT:'Cardano',DOGEUSDT:'Dogecoin'};
function close(){if(list)list.hidden=true;search?.setAttribute('aria-expanded','false');search?.removeAttribute('aria-activedescendant');}
function sync(){if(search)search.value=el().value;}
function choose(value){el().value=value;sync();close();el().dispatchEvent(new Event('change'));}
function results(){
    const query=search.value.trim().toUpperCase().replace(/\s+/g,'');
    matches=[...el().options].filter(o=>!query || (o.value+(names[o.value]||'')).toUpperCase().includes(query)).slice(0,50);active=0;
    list.replaceChildren();list.hidden=false;search.setAttribute('aria-expanded','true');
    const bounds=search.getBoundingClientRect();Object.assign(list.style,{left:bounds.left+'px',top:bounds.bottom+3+'px',width:Math.max(220,bounds.width)+'px'});
    for(const [i,option] of matches.entries()){
        const item=document.createElement('div');item.id=`symbol-match-${i}`;item.setAttribute('role','option');item.textContent=option.value+(names[option.value]?` · ${names[option.value]}`:'');
        item.onpointerdown=event=>{event.preventDefault();choose(option.value);};list.append(item);
    }
    if(!matches.length){const empty=document.createElement('div');empty.textContent='No matching symbols';list.append(empty);}
    highlight();
}
function highlight(){[...list.children].forEach((node,i)=>node.setAttribute('aria-selected',String(i===active&&!!matches.length)));if(matches.length)search.setAttribute('aria-activedescendant',`symbol-match-${active}`);}

async function populate(preserve = false) {
    const id = ++populateId;
    try {
        const r = await fetch("/api/symbols", { cache: "no-store" });
        if (!r.ok) throw new Error(`Symbols: HTTP ${r.status}`);
        const data = await r.json();
        if (id !== populateId) return;
        const syms = Array.isArray(data.symbols) ? data.symbols : [];
        const sel = el();
        const current = preserve ? sel.value : null;
        sel.innerHTML = "";
        for (const s of (syms.length ? syms : ["BTCUSDT"])) {
            const opt = document.createElement("option");
            opt.value = s; opt.textContent = s;
            sel.appendChild(opt);
        }
        if (current && ![...sel.options].some(option => option.value === current)) {
            const option = document.createElement("option");
            option.value = current; option.textContent = `${current} (inactive)`;
            sel.append(option);
        }
        if (current) sel.value = current;
        else if (syms.includes("BTCUSDT")) sel.value = "BTCUSDT";
        sync();
    } catch (e) {
        console.error("[symbol] populate failed:", e);
        if (id === populateId && !preserve) el().innerHTML = '<option value="BTCUSDT">BTCUSDT</option>';
    }
}

export function applyPriceFormat(symbol, bars, configuredPrecision) {
    if (el().value !== symbol) return;
    let precision = Number.isInteger(configuredPrecision)
        ? Math.max(0, Math.min(8, configuredPrecision)) : null;
    if (precision === null) {
        precision = 0;
        for (const bar of bars.slice(-1000)) {
            for (const key of ["open", "high", "low", "close"]) {
                const value = bar.client[key];
                if (!Number.isFinite(value)) continue;
                const [base, exponent = "0"] = String(value).toLowerCase().split("e");
                const decimals = (base.split(".")[1] || "").length - Number(exponent);
                precision = Math.max(precision, Math.min(8, decimals));
            }
        }
    }
    setPriceFormat({ type: "price", precision, minMove: Math.pow(10, -precision) });
}

export function value() { return el().value; }

export async function mount() {
    await populate();
    el().hidden=true;
    search=document.createElement('input');search.id='symbol-search';search.type='search';search.autocomplete='off';search.placeholder='Search symbol';search.setAttribute('aria-label','Search symbol');search.setAttribute('role','combobox');search.setAttribute('aria-autocomplete','list');search.setAttribute('aria-controls','symbol-search-results');search.setAttribute('aria-expanded','false');el().after(search);
    list=document.createElement('div');list.id='symbol-search-results';list.setAttribute('role','listbox');list.setAttribute('aria-label','Matching symbols');list.hidden=true;document.body.append(list);sync();
    search.oninput=results;search.onfocus=()=>{search.select();results();};
    search.onblur=()=>{close();sync();};
    search.onkeydown=event=>{
        if(event.key==='Escape'){close();sync();return;}
        if(['ArrowDown','ArrowUp'].includes(event.key)){event.preventDefault();if(list.hidden)results();else if(matches.length){active=(active+(event.key==='ArrowDown'?1:-1)+matches.length)%matches.length;highlight();}return;}
        if(event.key==='Enter'){event.preventDefault();if(matches[active])choose(matches[active].value);}
    };
    el().addEventListener('change',sync);window.addEventListener('resize',close);document.getElementById('toolbar').addEventListener('scroll',close);
}
export async function refresh() { await populate(true); }
