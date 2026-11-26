"""Build standalone, network-free comparison artifacts from exported evidence."""
import argparse
import gzip
import json
from pathlib import Path
from trial import run,serial

TEMPLATE=Path(__file__).with_name('viewer.html')


def build(stored,destination):
    result=run(stored)
    bars=[{k:r[k] for k in ('open_time','open','high','low','close')} for r in stored['candles']]
    payload=dict(bars=bars,result=result)
    html=TEMPLATE.read_text().replace('__PAYLOAD__',json.dumps(payload,default=serial,separators=(',',':')).replace('</','<\\/'))
    destination.write_text(html)
    return result


def overview(stored,result,path):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle
    from matplotlib.ticker import FuncFormatter
    from datetime import datetime
    from zoneinfo import ZoneInfo
    rows=stored['candles'][-650:];lookup={r['open_time']:i for i,r in enumerate(rows)}
    fig,axes=plt.subplots(2,1,figsize=(18,10),sharex=True,facecolor='#10151e')
    for ax,key,title in zip(axes,('current_stored','confirmed_pair_two_closes'),('Current stored pivots','Proposed: last two confirmed pivots + two reverse closes')):
        ax.set_facecolor('#10151e');ax.tick_params(colors='#cbd5e1');ax.grid(color='#303844',alpha=.5)
        for i,row in enumerate(rows):
            color='#26a69a' if row['close']>=row['open'] else '#ef5350'
            ax.vlines(i,row['low'],row['high'],color=color,linewidth=.7)
            ax.add_patch(Rectangle((i-.32,min(row['open'],row['close'])),.64,max(abs(row['close']-row['open']),.00001),facecolor=color,linewidth=0))
        for e in result['variants'][key]['events']:
            if e['origin_time'] not in lookup:continue
            high=e['type']=='PIVOT_HIGH';i=lookup[e['origin_time']]
            ax.scatter(i,e['price'],marker='v' if high else '^',s=22,color='#ffb74d' if high else '#38bdf8',zorder=5)
        ax.set_title(title,color='#e2e8f0',loc='left');ax.set_ylabel('ENA / USDT',color='#cbd5e1')
        for spine in ax.spines.values():spine.set_color('#384252')
    axes[-1].xaxis.set_major_formatter(FuncFormatter(lambda x,_:datetime.fromtimestamp(rows[min(max(round(x),0),len(rows)-1)]['open_time']/1000,ZoneInfo('Asia/Karachi')).strftime('%d %b %H:%M')))
    axes[-1].set_xlabel('Pakistan time · markers at pivot origins, known only at later confirmation closes',color='#cbd5e1')
    fig.suptitle('Offline ENAUSDT 15m comparison — no app changes',color='#e2e8f0',fontsize=15)
    fig.tight_layout();fig.savefig(path,dpi=140,facecolor=fig.get_facecolor());plt.close(fig)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('stored',type=Path);p.add_argument('--output',type=Path,required=True);p.add_argument('--png',type=Path)
    a=p.parse_args();stored=json.loads(gzip.decompress(a.stored.read_bytes()));result=build(stored,a.output)
    if a.png:overview(stored,result,a.png)
    print(json.dumps(result['summary'],indent=2))


if __name__=='__main__':main()
