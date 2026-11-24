"""Private paper-ledger controls and real loopback HTTP boundaries."""
from contextlib import ExitStack
from dataclasses import replace
from decimal import Decimal as D
from http.client import HTTPConnection
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from Section_15_Execution_Bot.config import Config
from Section_15_Execution_Bot.engine import Ledger,Conflict
from Section_15_Execution_Bot.quotes import Quote
from Section_15_Execution_Bot.dashboard import Dashboard,Server


def cfg(name='ena'):
    return Config(name,'ENAUSDT','5m','current','100','200','2','4','0','0',strategy_source='current',strategy_fingerprint='fixture')


class DashboardLedger(unittest.TestCase):
    def setUp(self):
        self.root=Path(self.enterContext(tempfile.TemporaryDirectory()));self.ledger=Ledger(self.root/'bot.db')
        self.ledger.create(cfg(),0)
    def account(self):return self.ledger.view('ena')['accounts'][0]
    def buy(self):
        self.ledger.enabled('ena',True,0)
        self.ledger.step('ena',Quote('ENAUSDT','1','1',1000),dict(epoch='test',events=[dict(open_time=0,close_time=999,side='BUY')]),1000)
    def test_edit_preserves_cash_history_and_cursor_and_rejects_stale_settings(self):
        account=self.account();before=account['state'].copy()
        self.ledger.configure('ena',{'capital_cap':'50','stop_loss_pct':'3'},2000,expected_config=account['config_token'])
        current=self.account();self.assertEqual(current['state'],before)
        self.assertEqual(current['config']['capital_cap'],'50')
        with self.assertRaises(Conflict):self.ledger.configure('ena',{'take_profit_pct':'5'},2001,expected_config=account['config_token'])
        with self.ledger.connect() as c:self.assertEqual(c.execute('SELECT COUNT(*) FROM configuration_changes').fetchone()[0],1)
    def test_edit_rejects_enabled_accounts_positions_and_identity_changes(self):
        self.buy();account=self.account()
        with self.assertRaises(Conflict):self.ledger.configure('ena',{'stop_loss_pct':'3'},2000,expected_config=account['config_token'])
        self.ledger.enabled('ena',False,2000)
        with self.assertRaises(Conflict):self.ledger.configure('ena',{'stop_loss_pct':'3'},2000,expected_config=account['config_token'])
        with self.assertRaises(ValueError):self.ledger.configure('ena',{'symbol':'BTCUSDT'},2000,expected_config=account['config_token'])
    def test_enable_is_idempotent_and_cannot_reset_signal_activation_on_duplicate_click(self):
        self.ledger.enabled('ena',True,1000);self.ledger.enabled('ena',True,2000)
        self.assertEqual(self.account()['state']['armed_at'],1000)
    def test_close_is_scoped_fresh_and_atomic_with_pause(self):
        self.buy();account=self.account();self.ledger.create(cfg('other'),0)
        self.ledger.close_position('ena',Quote('ENAUSDT','1.1','1.1',2000),2000,expected_position=account['position_token'])
        state=self.account()['state'];self.assertFalse(state['enabled']);self.assertEqual(D(state['quantity']),0)
        self.assertEqual(D(state['cash']),110);self.assertEqual(self.ledger.history('ena')[0]['reason'],'MANUAL_CLOSE')
        self.assertEqual(self.ledger.view('other')['accounts'][1]['state']['cash'],'100')
        with self.assertRaises(Conflict):self.ledger.close_position('ena',Quote('ENAUSDT','1.1','1.1',2000),2000,expected_position=account['position_token'])
        self.assertEqual(len(self.ledger.history('ena')),2)
    def test_old_position_token_cannot_close_a_later_position(self):
        self.buy();old=self.account()['position_token']
        self.ledger.step('ena',Quote('ENAUSDT','1','1',2000),dict(epoch='test',events=[dict(open_time=1000,close_time=1999,side='SELL')]),2000)
        self.ledger.step('ena',Quote('ENAUSDT','1','1',3000),dict(epoch='test',events=[dict(open_time=2000,close_time=2999,side='BUY')]),3000)
        with self.assertRaises(Conflict):self.ledger.close_position('ena',Quote('ENAUSDT','1','1',3001),3001,expected_position=old)
        self.assertGreater(D(self.account()['state']['quantity']),0)
    def test_stale_or_wrong_quote_cannot_close_and_ro_view_does_not_create_or_mutate(self):
        self.buy();before=self.ledger.path.read_bytes();account=self.account()
        for quote in (Quote('ENAUSDT','1','1',0),Quote('BTCUSDT','1','1',12000)):
            with self.assertRaises(ValueError):self.ledger.close_position('ena',quote,12000,expected_position=account['position_token'])
        self.assertEqual(before,self.ledger.path.read_bytes())
        missing=self.root/'missing.db';self.assertEqual(Ledger(missing).view()['accounts'],[]);self.assertFalse(missing.exists())
    def test_edited_entry_cap_leaves_the_rest_of_the_wallet_as_reserve(self):
        row=self.account()
        self.ledger.configure('ena',{'capital_cap':'25'},100,expected_config=row['config_token'])
        self.buy()
        state=self.account()['state']
        self.assertEqual(D(state['cost']),25);self.assertEqual(D(state['cash']),75)
        self.assertEqual(state['last_bid'],'1')

    def test_equity_uses_the_reported_quote_without_making_network_requests(self):
        self.buy()
        with patch('Section_15_Execution_Bot.quotes.fetch',side_effect=AssertionError('GET must not fetch exchange data')):
            data=Dashboard(self.ledger.path).state('ena')
        self.assertEqual(D(data['accounts'][0]['estimated_equity']),100)
        self.assertEqual(data['fills_account'],'ena')


class DashboardHTTP(unittest.TestCase):
    def setUp(self):
        self.root=Path(self.enterContext(tempfile.TemporaryDirectory()));self.path=self.root/'bot.db'
        self.server=Server(self.path,0);self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.addCleanup(self.stop)
    def stop(self):self.server.shutdown();self.server.server_close();self.thread.join(2)
    def request(self,path='/',data=None,**headers):
        conn=HTTPConnection('127.0.0.1',self.server.server_port,timeout=5)
        if data is not None:
            headers={'Content-Type':'application/json','X-Dashboard-Token':self.server.csrf,**headers};body=json.dumps(data)
        else:body=None
        conn.request('POST' if data is not None else 'GET',path,body=body,headers=headers)
        response=conn.getresponse();status=response.status;payload=response.read();conn.close();return status,payload
    def test_local_page_and_reads_do_not_create_missing_ledger(self):
        status,body=self.request();self.assertEqual(status,200);self.assertIn(self.server.csrf.encode(),body)
        status,body=self.request('/api/state');self.assertEqual(status,200);self.assertEqual(json.loads(body)['accounts'],[])
        self.assertFalse(self.path.exists())
    def test_origin_host_token_and_traversal_rejected(self):
        for headers in ({'Origin':'https://evil.example'},{'Host':'evil.example'},{'X-Dashboard-Token':'wrong'}):
            self.assertEqual(self.request('/api/action',{'action':'create'},**headers)[0],403)
        self.assertEqual(self.request('/../../config.py')[0],404)
        self.assertEqual(self.request('/api/state',Host='evil.example')[0],403)
    def test_create_pause_edit_and_validation_have_no_exchange_or_chart_writes(self):
        config=cfg().data();allowed={'name','symbol','interval','initial_capital','capital_cap','stop_loss_pct','take_profit_pct','fee_bps','slippage_bps','max_signal_age_seconds'}
        config={k:v for k,v in config.items() if k in allowed}
        with patch('Section_15_Execution_Bot.source.snapshot',return_value={'events':[],'epoch':'test'}):
            self.assertEqual(self.request('/api/action',{'action':'create','config':config})[0],200)
            row=json.loads(self.request('/api/state?name=ena')[1])['accounts'][0]
            self.assertFalse(row['state']['enabled'])
            self.assertEqual(self.request('/api/action',{'action':'enable','name':'ena','expected_config':row['config_token']})[0],200)
            self.assertEqual(self.request('/api/action',{'action':'pause','name':'ena','expected_config':row['config_token']})[0],200)
            self.assertEqual(self.request('/api/action',{'action':'configure','name':'ena','expected_config':row['config_token'],'changes':{'stop_loss_pct':'3'}})[0],200)
            self.assertEqual(self.request('/api/action',{'action':'configure','name':'ena','expected_config':row['config_token'],'changes':{'stop_loss_pct':'4'}})[0],409)
        self.assertEqual(self.request('/api/action',{'action':'create','config':{**config,'mode':'live'}})[0],400)

    def test_pause_is_not_blocked_by_a_stale_config_and_stale_close_does_not_fetch(self):
        ledger=self.server.dashboard.ledger;ledger.create(cfg(),0);ledger.enabled('ena',True,0)
        self.assertEqual(self.request('/api/action',{'action':'pause','name':'ena','expected_config':'old-tab'})[0],200)
        self.assertFalse(ledger.view()['accounts'][0]['state']['enabled'])
        with patch('Section_15_Execution_Bot.quotes.fetch',side_effect=AssertionError('No quote required for a stale position')):
            self.assertEqual(self.request('/api/action',{'action':'close','name':'ena','expected_position':'old-position'})[0],409)


class DashboardUpgrade(unittest.TestCase):
    def test_old_ledger_reads_without_ddl_and_upgrades_without_resetting_money_or_history(self):
        with tempfile.TemporaryDirectory() as directory:
            import sqlite3
            from Section_15_Execution_Bot.engine import dump
            path=Path(directory)/'legacy.db'
            state=dict(cash='107',quantity='0',cost='0',entry='0',epoch='legacy',cursor=123,
                armed_at=100,enabled=False,halted=False,status='Watching',realized_pnl='7')
            with sqlite3.connect(path) as c:
                c.execute('CREATE TABLE accounts(name TEXT PRIMARY KEY,config TEXT NOT NULL,state TEXT NOT NULL)')
                c.execute('CREATE TABLE fills(id INTEGER PRIMARY KEY,account TEXT NOT NULL,event_key TEXT NOT NULL,side TEXT NOT NULL,reason TEXT NOT NULL,at_ms INTEGER NOT NULL,price TEXT NOT NULL,quantity TEXT NOT NULL,fee TEXT NOT NULL,pnl TEXT,UNIQUE(account,event_key))')
                c.execute('INSERT INTO accounts VALUES (?,?,?)',('ena',dump(cfg().data()),dump(state)))
                c.execute("INSERT INTO fills VALUES (1,'ena','old','SELL','STRATEGY_SELL',99,'1','1','0','7')")
            before=path.read_bytes();ledger=Ledger(path);snapshot=ledger.view('ena')
            self.assertEqual(before,path.read_bytes());self.assertEqual(snapshot['accounts'][0]['state'],state)
            ledger.configure('ena',{'stop_loss_pct':'3'},200,expected_config=snapshot['accounts'][0]['config_token'])
            self.assertEqual(ledger.view('ena')['accounts'][0]['state'],state)
            self.assertEqual(len(ledger.history('ena')),1)
            self.assertEqual(ledger.history('ena')[0]['event_key'],'old')
