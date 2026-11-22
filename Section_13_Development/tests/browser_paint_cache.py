"""Real Canvas2D pixel and dense-layer cache regression at Retina resolution."""
import asyncio
import json
from pathlib import Path
from playwright.async_api import async_playwright


async def run():
    source=(Path(__file__).resolve().parents[2]/'Section_11_UI_UX/chart/paint_cache.js').read_text().replace('export ','')
    async with async_playwright() as p:
        browser=await p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
        page=await browser.new_page(viewport={'width':1728,'height':900},device_scale_factor=2)
        result=await page.evaluate('''source=>{
            const Cache=new Function(source+';return PaintCache;')();
            const width=1728,height=505,ratio=2;
            const canvas=()=>{const c=document.createElement('canvas');c.width=width*ratio;c.height=height*ratio;return c;};
            const cached=canvas(),direct=canvas(),cache=new Cache();let builds=0;
            const prepare=c=>{const x=c.getContext('2d');x.setTransform(1,0,0,1,0,0);x.fillStyle='#101820';x.fillRect(0,0,c.width,c.height);x.setTransform(ratio,0,0,ratio,0,0);return x;};
            const paint=({context:x})=>{builds++;x.save();
                for(let i=0;i<12000;i++){
                    x.fillStyle=i%2?'#22bb66':'#ee4455';x.globalAlpha=.05+(i%10)/20;
                    x.fillRect((i*37)%width,(i*13)%height,1+(i%41)/5,1+(i%9)/3);
                }
                x.globalAlpha=.7;x.strokeStyle='#abcdef';x.lineWidth=1.5;x.beginPath();x.moveTo(10.25,20.5);x.lineTo(1000.75,490.25);x.stroke();x.restore();};
            const scope={context:prepare(cached),mediaSize:{width,height}};
            cache.draw(scope,1,paint);paint({context:prepare(direct)});
            const a=cached.getContext('2d').getImageData(0,0,cached.width,cached.height).data;
            const b=direct.getContext('2d').getImageData(0,0,direct.width,direct.height).data;
            let maximum=0,differences=0;for(let i=0;i<a.length;i++){const d=Math.abs(a[i]-b[i]);maximum=Math.max(maximum,d);if(d)differences++;}
            const before=builds,start=performance.now();
            for(let i=0;i<100;i++){scope.context=prepare(cached);cache.draw(scope,1,paint);}
            const cache_ms=performance.now()-start;
            return {maximum_channel_error:maximum,differing_channels:differences,channels:a.length,
                crosshair_repaints:100,layer_rebuilds:builds-before,stats:cache.stats,cache_ms};
        }''',source)
        assert result['maximum_channel_error']<=3,result
        assert result['layer_rebuilds']==0,result
        assert result['stats']['hits']==100,result
        print('PASS: Retina pixels match direct drawing within Canvas2D alpha rounding; 100 dense-layer repaints require zero geometry rebuilds')
        print(json.dumps(result))
        await browser.close()


if __name__=='__main__':asyncio.run(run())
