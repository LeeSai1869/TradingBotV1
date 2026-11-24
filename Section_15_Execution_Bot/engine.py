"""Restart-safe paper Spot ledger: single position, idempotent fills, capped compounding."""
from contextlib import closing
import hashlib
from dataclasses import replace
import uuid
import json
from pathlib import Path
import sqlite3
from .config import Config, money as D

SCHEMA='''
CREATE TABLE IF NOT EXISTS accounts(name TEXT PRIMARY KEY,config TEXT NOT NULL,state TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS fills(id INTEGER PRIMARY KEY,account TEXT NOT NULL,event_key TEXT NOT NULL,side TEXT NOT NULL,
 reason TEXT NOT NULL,at_ms INTEGER NOT NULL,price TEXT NOT NULL,quantity TEXT NOT NULL,fee TEXT NOT NULL,pnl TEXT,
 UNIQUE(account,event_key));
CREATE INDEX IF NOT EXISTS fills_account_id ON fills(account,id DESC);
CREATE TABLE IF NOT EXISTS configuration_changes(id INTEGER PRIMARY KEY,account TEXT NOT NULL,at_ms INTEGER NOT NULL,before_config TEXT NOT NULL,after_config TEXT NOT NULL);
'''


def dump(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)


class Conflict(ValueError):pass


def config_token(config):return hashlib.sha256(dump(config).encode()).hexdigest()


def position_token(conn,name,state):
    last=conn.execute("SELECT MAX(id) FROM fills WHERE account=? AND side='BUY'",(name,)).fetchone()[0]
    return hashlib.sha256(dump([last,state['quantity'],state['cost'],state['entry']]).encode()).hexdigest()



class Ledger:
    def __init__(self,path):self.path=Path(path)

    def connect(self):
        self.path.parent.mkdir(parents=True,exist_ok=True)
        conn=sqlite3.connect(self.path,timeout=2);conn.executescript(SCHEMA)
        return conn

    def create(self,config,now):
        with closing(self.connect()) as c,c:
            c.execute('INSERT INTO accounts VALUES (?,?,?)',(config.name,dump(config.data()),dump(dict(
                cash=str(D(config.initial_capital)),quantity='0',cost='0',entry='0',epoch=None,
                cursor=-1,armed_at=now,enabled=False,halted=False,status='Created; paused',realized_pnl='0'))))

    def report(self,name=None):
        with closing(self.connect()) as c:
            rows=c.execute('SELECT name,config,state FROM accounts'+(' WHERE name=?' if name else '') ,(name,) if name else ()).fetchall()
            return [dict(name=r[0],config=json.loads(r[1]),state=json.loads(r[2])) for r in rows]

    def history(self,name,limit=100):
        if type(limit) is not int or not 1<=limit<=1000:raise ValueError('History limit must be 1..1000')
        with closing(self.connect()) as c:
            cursor=c.execute('SELECT * FROM fills WHERE account=? ORDER BY id DESC LIMIT ?',(name,limit))
            names=[d[0] for d in cursor.description]
            return [dict(zip(names,row)) for row in cursor.fetchall()]

    def failure(self,name,message,now):
        with closing(self.connect()) as c,c:
            c.execute('BEGIN IMMEDIATE')
            row=c.execute('SELECT state FROM accounts WHERE name=?',(name,)).fetchone()
            if row:
                state=json.loads(row[0]);state.update(status='No fill: '+message[:300],last_error_ms=now)
                c.execute('UPDATE accounts SET state=? WHERE name=?',(dump(state),name))

    def enabled(self,name,value,now,*,expected_config=None):
        with closing(self.connect()) as c,c:
            c.execute('BEGIN IMMEDIATE')
            row=c.execute('SELECT config,state FROM accounts WHERE name=?',(name,)).fetchone()
            if row is None:raise ValueError('Unknown paper account')
            if expected_config is not None and config_token(json.loads(row[0]))!=expected_config:raise Conflict('Configuration changed; refresh the dashboard')
            state=json.loads(row[1])
            if value and state['halted']:raise ValueError('Allocation is halted; create a new reviewed allocation')
            if state['enabled']==value:return
            state['enabled']=value
            if value:
                state.update(armed_at=now,status='Enabled; awaiting fresh signal')
                # A stopped position remains owned and risk exits stay enabled.
                # After a stop/take-profit, require a fresh BUY before reentry.
            else:state['status']='Entries paused; existing position still monitored'
            c.execute('UPDATE accounts SET state=? WHERE name=?',(dump(state),name))

    def step(self,name,quote,feed,now):
        with closing(self.connect()) as c,c:
            c.execute('BEGIN IMMEDIATE')
            row=c.execute('SELECT config,state FROM accounts WHERE name=?',(name,)).fetchone()
            if row is None:raise ValueError('Unknown paper account')
            cfg=Config(**json.loads(row[0]));s=json.loads(row[1]);quote.validate(cfg.symbol,now)
            fee=D(cfg.fee_bps)/10000;slip=D(cfg.slippage_bps)/10000
            fills=[]
            def execute(side,reason,key):
                price=D(quote.ask)*(1+slip) if side=='BUY' else D(quote.bid)*(1-slip)
                cash=D(s['cash']);quantity=D(s['quantity']);cost=D(s['cost'])
                if side=='BUY':
                    budget=min(cash,D(cfg.capital_cap));quantity=budget/(price*(1+fee))
                    charge=quantity*price*fee;cost=budget;cash-=budget;pnl=None
                    s.update(quantity=str(quantity),cost=str(cost),entry=str(price))
                else:
                    gross=quantity*price;charge=gross*fee;pnl=gross-charge-cost;cash+=gross-charge
                    s.update(quantity='0',cost='0',entry='0',realized_pnl=str(D(s['realized_pnl'])+pnl))
                c.execute('INSERT INTO fills(account,event_key,side,reason,at_ms,price,quantity,fee,pnl) VALUES (?,?,?,?,?,?,?,?,?)',
                    (name,key,side,reason,now,str(price),str(quantity),str(charge),str(pnl) if pnl is not None else None))
                s['cash']=str(cash);fills.append(dict(side=side,reason=reason,price=str(price),quantity=str(quantity)))
            # Position protection remains active when the strategy is paused,
            # deleted, switched, or its source is temporarily unavailable.
            protected=False
            if D(s['quantity'])>0:
                change=(D(quote.bid)*(1-slip)/D(s['entry'])-1)*100
                reason='STOP_LOSS' if change<=-D(cfg.stop_loss_pct) else 'TAKE_PROFIT' if change>=D(cfg.take_profit_pct) else None
                if reason:
                    execute('SELL',reason,'risk:'+str(now));protected=True
            if feed is None:s['status']='Strategy unavailable; entries blocked, risk exits active'
            else:
                if s['epoch'] is None:s['epoch']=feed['epoch']
                elif s['epoch']!=feed['epoch']:
                    s.update(halted=True,status='Data generation changed; create a new account after review')
                for event in sorted(feed['events'],key=lambda e:e['open_time']):
                    if event['open_time']<=s['cursor']:continue
                    if event['side'] not in ('BUY','SELL') or event['close_time']>now:raise ValueError('Invalid/unclosed strategy event')
                    s['cursor']=event['open_time']
                    # Never replay historical trades when starting/restarting.
                    fresh=event['close_time']>=s['armed_at'] and 0<=now-event['close_time']<=cfg.max_signal_age_seconds*1000
                    if not fresh or s['halted']:continue
                    key=feed['epoch']+':'+str(event['open_time'])
                    if event['side']=='SELL' and D(s['quantity'])>0:
                        execute('SELL','STRATEGY_SELL',key)
                    elif event['side']=='BUY' and s['enabled'] and not protected and D(s['quantity'])==0 and D(s['cash'])>0:
                        execute('BUY','STRATEGY_BUY',key)
                if not s['halted']:s['status']='Watching' if s['enabled'] else 'Entries paused; risk exits active'
            s.update(last_quote_ms=quote.observed_ms,last_bid=quote.bid,last_ask=quote.ask)
            c.execute('UPDATE accounts SET state=? WHERE name=?',(dump(s),name))
            return fills


    def view(self,name=None):
        """Consistent read-only dashboard snapshot; never creates a missing ledger."""
        if not self.path.is_file():return dict(accounts=[],fills=[],fills_account=name)
        with closing(sqlite3.connect(self.path.resolve().as_uri()+'?mode=ro',uri=True,timeout=1)) as c:
            c.execute('BEGIN')
            accounts=[]
            for label,config,state in c.execute('SELECT name,config,state FROM accounts ORDER BY name'):
                cfg=json.loads(config);saved=json.loads(state)
                accounts.append(dict(name=label,config=cfg,state=saved,config_token=config_token(cfg),position_token=position_token(c,label,saved)))
            fills=[]
            if name:
                cursor=c.execute('SELECT * FROM fills WHERE account=? ORDER BY id DESC LIMIT 100',(name,))
                columns=[d[0] for d in cursor.description];fills=[dict(zip(columns,row)) for row in cursor.fetchall()]
            return dict(accounts=accounts,fills=fills,fills_account=name)

    def configure(self,name,changes,now,*,expected_config):
        allowed={'capital_cap','stop_loss_pct','take_profit_pct','fee_bps','slippage_bps','max_signal_age_seconds'}
        if not isinstance(changes,dict) or not changes or set(changes)-allowed:
            raise ValueError('Edit only entry cap, exits, modeled costs and signal age; use a new allocation for other changes')
        with closing(self.connect()) as c,c:
            c.execute('BEGIN IMMEDIATE')
            row=c.execute('SELECT config,state FROM accounts WHERE name=?',(name,)).fetchone()
            if row is None:raise ValueError('Unknown paper account')
            before=json.loads(row[0]);state=json.loads(row[1])
            if config_token(before)!=expected_config:raise Conflict('Configuration changed; reopen settings to review it')
            if state['enabled'] or D(state['quantity'])!=0:raise Conflict('Pause entries and close the position before editing settings')
            cfg=replace(Config(**before),**changes)
            after=cfg.data()
            c.execute('UPDATE accounts SET config=? WHERE name=?',(dump(after),name))
            c.execute('INSERT INTO configuration_changes(account,at_ms,before_config,after_config) VALUES (?,?,?,?)',
                (name,now,dump(before),dump(after)))

    def close_position(self,name,quote,now,*,expected_position):
        """Explicit manual PAPER exit plus pause; reject an old position preview."""
        with closing(self.connect()) as c,c:
            c.execute('BEGIN IMMEDIATE')
            row=c.execute('SELECT config,state FROM accounts WHERE name=?',(name,)).fetchone()
            if row is None:raise ValueError('Unknown paper account')
            cfg=Config(**json.loads(row[0]));state=json.loads(row[1]);quote.validate(cfg.symbol,now)
            if position_token(c,name,state)!=expected_position or D(state['quantity'])<=0:
                raise Conflict('Position changed; refresh before closing it')
            price=D(quote.bid)*(1-D(cfg.slippage_bps)/10000);quantity=D(state['quantity'])
            gross=price*quantity;fee=gross*D(cfg.fee_bps)/10000;pnl=gross-fee-D(state['cost'])
            c.execute('INSERT INTO fills(account,event_key,side,reason,at_ms,price,quantity,fee,pnl) VALUES (?,?,?,?,?,?,?,?,?)',
                (name,'manual:'+uuid.uuid4().hex,'SELL','MANUAL_CLOSE',now,str(price),str(quantity),str(fee),str(pnl)))
            state.update(cash=str(D(state['cash'])+gross-fee),quantity='0',cost='0',entry='0',enabled=False,
                realized_pnl=str(D(state['realized_pnl'])+pnl),last_quote_ms=quote.observed_ms,last_bid=quote.bid,last_ask=quote.ask,
                status='Paper position closed; entries paused')
            c.execute('UPDATE accounts SET state=? WHERE name=?',(dump(state),name))
