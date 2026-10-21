"""Account-owned drawing memory, separate from market data and browser storage."""
import json
import math
import re
import sqlite3
from contextlib import closing
from urllib.parse import parse_qs, urlparse
from . import auth, admin_routes
from Section_1_Global_Core.data_policy import INTERVALS

TOOLS={'line':2,'rectangle':2,'horizontal':1,'retracement':2,'extension':3}

def connection():
    conn=sqlite3.connect(auth.USERS_FILE.with_name('drawings.sqlite3'),timeout=5)
    conn.execute('CREATE TABLE IF NOT EXISTS drawings (username TEXT, symbol TEXT, revision INTEGER NOT NULL, data TEXT NOT NULL, PRIMARY KEY(username,symbol))')
    return conn

def symbol(value):
    if not isinstance(value,str) or not re.fullmatch(r'[A-Z0-9]{2,30}',value):raise ValueError('Invalid symbol')
    return value

def validate(items):
    if not isinstance(items,list) or len(items)>500:raise ValueError('Maximum 500 drawings per coin')
    result=[]
    for d in items:
        if not isinstance(d,dict) or d.get('type') not in TOOLS:raise ValueError('Invalid drawing tool')
        anchors=d.get('anchors')
        if not isinstance(anchors,list) or len(anchors)!=TOOLS[d['type']]:raise ValueError('Invalid anchors')
        for a in anchors:
            if not isinstance(a,dict) or any(isinstance(a.get(k),bool) or not isinstance(a.get(k),(float,int)) or not math.isfinite(a[k]) for k in ('time','offset','price')) or abs(a['offset'])>=10000:raise ValueError('Invalid anchor coordinates')
        style=d.get('style',{})
        if not isinstance(style,dict) or not re.fullmatch(r'#[a-fA-F0-9]{6}',style.get('color','#58b9ff')) or style.get('width',2) not in (1,2,3,4) or style.get('pattern','solid') not in ('solid','dashed','dotted'):raise ValueError('Invalid drawing style')
        opacity=style.get('fillOpacity',.1)
        if isinstance(opacity,bool) or not isinstance(opacity,(int,float)) or not 0<=opacity<=1:raise ValueError('Invalid fill opacity')
        frames=d.get('timeframes',[])
        if not isinstance(frames,list) or len(frames)>len(INTERVALS) or any(f not in INTERVALS for f in frames) or len(set(frames))!=len(frames):raise ValueError('Invalid timeframes')
        result.append({'type':d['type'],'anchors':[{k:a[k] for k in ('time','offset','price')} for a in anchors],
            'style':{'color':style.get('color','#58b9ff'),'width':style.get('width',2),'pattern':style.get('pattern','solid'),'fillOpacity':opacity},
            'locked':d.get('locked') is True,'timeframes':frames})
    return result

def handle_get(path,query,server):
    if path!='/api/drawings':return None,None
    user=admin_routes.user(server)
    if user['role']=='guest':return 401,{'error':'Sign in required'}
    try:s=symbol(parse_qs(query).get('symbol',[''])[0])
    except ValueError as e:return 400,{'error':str(e)}
    with closing(connection()) as conn, conn:
        row=conn.execute('SELECT revision,data FROM drawings WHERE username=? AND symbol=?',(user['username'],s)).fetchone()
    return 200,{'revision':row[0] if row else 0,'drawings':json.loads(row[1]) if row else []}

def handle_post(path,body,server):
    if path!='/api/drawings':return None,None
    user=admin_routes.user(server)
    if user['role']=='guest':return 401,{'error':'Sign in required'}
    origin=server.headers.get('Origin')
    if origin and urlparse(origin).netloc!=server.headers.get('Host'):return 403,{'error':'Cross-origin changes forbidden'}
    try:
        if len(body)>500000:raise ValueError('Drawing memory too large')
        data=json.loads(body)
        if not isinstance(data,dict):raise ValueError('JSON object required')
        s=symbol(data.get('symbol'));items=validate(data.get('drawings'));revision=data.get('revision')
        if type(revision) is not int or not 0<=revision<2**53:raise ValueError('Invalid revision')
        with closing(connection()) as conn, conn:
            conn.execute('BEGIN IMMEDIATE')
            row=conn.execute('SELECT revision FROM drawings WHERE username=? AND symbol=?',(user['username'],s)).fetchone()
            if (row[0] if row else 0)!=revision:return 409,{'error':'Drawings changed on another device. Reload drawings before editing.'}
            conn.execute('INSERT OR REPLACE INTO drawings VALUES (?,?,?,?)',(user['username'],s,revision+1,json.dumps(items,allow_nan=False)))
        return 200,{'revision':revision+1}
    except (ValueError,TypeError,KeyError) as e:return 400,{'error':str(e)}
