"""Shared funding, atomic competing entries and lossless legacy consolidation."""
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal as D
import json
import io
from contextlib import redirect_stdout
from unittest.mock import patch
from pathlib import Path
import sqlite3
import tempfile
import unittest
from Section_15_Execution_Bot.engine import Ledger,Conflict,dump
from Section_15_Execution_Bot.dashboard import Dashboard
from Section_15_Execution_Bot.quotes import Quote
from .test_paper_bot import config,feed


class SharedWallet(unittest.TestCase):
    def setUp(self):
        self.path=Path(self.enterContext(tempfile.TemporaryDirectory()))/'bot.db'
        self.ledger=Ledger(self.path)
        for name in ('ena','other'):
            self.ledger.create(config(name=name,capital_cap='60'),0)
            self.ledger.enabled(name,True,0)
    def buy(self,name):return self.ledger.step(name,Quote('ENAUSDT','1','1',1000000),feed(),1000000)
    def test_second_slot_cannot_add_funds_and_balances_are_not_stored_in_slots(self):
        self.assertEqual(D(self.ledger.wallet()['cash']),100)
        self.ledger.create(config(name='third',initial_capital='9999'),0)
        self.assertEqual(D(self.ledger.wallet()['cash']),100)
        with sqlite3.connect(self.path) as c:
            for row in c.execute('SELECT state FROM accounts'):self.assertNotIn('cash',json.loads(row[0]))
            self.assertEqual(c.execute('SELECT COUNT(*) FROM bot_wallet').fetchone()[0],1)
    def test_simultaneous_slots_cannot_double_spend(self):
        with ThreadPoolExecutor(2) as pool:list(pool.map(self.buy,['ena','other']))
        rows=self.ledger.report();costs=sorted(D(a['state']['cost']) for a in rows)
        self.assertEqual(costs,[D(40),D(60)])
        self.assertEqual(D(self.ledger.wallet()['cash']),0)
        self.assertEqual(sum(D(a['state']['cost']) for a in rows),100)
    def test_sell_proceeds_and_profit_are_shared_but_positions_and_history_stay_scoped(self):
        self.buy('ena')
        self.ledger.step('ena',Quote('ENAUSDT','1.1','1.1',1001000),feed('SELL',1000000,1000999),1001000)
        self.assertEqual(D(self.ledger.wallet()['cash']),106)
        self.assertEqual(D(self.ledger.wallet()['realized_pnl']),6)
        self.buy('other')
        self.assertEqual(D(self.ledger.wallet()['cash']),46)
        self.assertEqual(D(self.ledger.report('ena')[0]['state']['quantity']),0)
        self.assertEqual(len(self.ledger.history('ena')),2)
        self.assertEqual(len(self.ledger.history('other')),1)
        for name in ('ena','other'):
            result=Dashboard(self.path).state(name)
            self.assertEqual(D(result['wallet']['estimated_equity']),106)
            self.assertEqual(D(result['wallet']['cash']),46)
    def test_empty_pool_skips_buy_without_replaying_it_when_funds_return(self):
        self.buy('ena');self.buy('other')
        self.ledger.create(config(name='third'),0);self.ledger.enabled('third',True,0)
        self.assertEqual(self.buy('third'),[])
        self.assertIn('shared cash',self.ledger.report('third')[0]['state']['status'])
        row=self.ledger.view('ena')['accounts'][0]
        self.ledger.close_position('ena',Quote('ENAUSDT','1','1',1000001),1000001,expected_position=row['position_token'])
        self.assertEqual(self.buy('third'),[])
        self.assertEqual(D(self.ledger.wallet()['cash']),60)
    def test_cli_rejects_another_deposit_but_allows_an_unfunded_slot(self):
        from Section_15_Execution_Bot.__main__ import main
        args=['bot','--db',str(self.path),'create','--name','third','--symbol','ENAUSDT','--interval','5m',
              '--capital-cap','25','--stop-loss-pct','2','--take-profit-pct','4']
        with patch('sys.argv',args+['--capital','100']),redirect_stdout(io.StringIO()):
            with self.assertRaises(SystemExit) as result:main()
            self.assertEqual(result.exception.code,2)
        with patch('sys.argv',args),patch('Section_15_Execution_Bot.source.snapshot',return_value=dict(epoch='test',events=[])),redirect_stdout(io.StringIO()):main()
        self.assertEqual(len(self.ledger.report()),3)
        self.assertEqual(D(self.ledger.wallet()['cash']),100)
    def test_dashboard_rejects_second_initial_deposit(self):
        raw={k:v for k,v in config(name='third').data().items() if k in {'name','symbol','interval','initial_capital','capital_cap','stop_loss_pct','take_profit_pct'}}
        with self.assertRaisesRegex(ValueError,'already has a wallet'):Dashboard(self.path).action(dict(action='create',config=raw))
        self.assertEqual(D(self.ledger.wallet()['cash']),100)


class WalletMigration(unittest.TestCase):
    def legacy(self,count=1):
        path=Path(self.enterContext(tempfile.TemporaryDirectory()))/'old.db'
        with sqlite3.connect(path) as c:
            c.execute('CREATE TABLE accounts(name TEXT PRIMARY KEY,config TEXT NOT NULL,state TEXT NOT NULL)')
            c.execute('CREATE TABLE fills(id INTEGER PRIMARY KEY,account TEXT,event_key TEXT,side TEXT,reason TEXT,at_ms INTEGER,price TEXT,quantity TEXT,fee TEXT,pnl TEXT)')
            for i in range(count):
                cfg=config(name='slot'+str(i));state=dict(cash='67',quantity='4',cost='40',entry='10',realized_pnl='7',epoch='old',cursor=123,armed_at=0,enabled=True,halted=False,status='Watching')
                c.execute('INSERT INTO accounts VALUES (?,?,?)',(cfg.name,dump(cfg.data()),dump(state)))
                c.execute("INSERT INTO fills(account,event_key,side,reason,at_ms,price,quantity,fee) VALUES (?, 'old-buy', 'BUY','STRATEGY_BUY',1,'10','4','0')",(cfg.name,))
        return Ledger(path)
    def test_single_legacy_wallet_migrates_once_with_open_position_and_state_unchanged(self):
        ledger=self.legacy();before=ledger.view()['accounts'][0]['state'];ledger.prepare()
        self.assertEqual(ledger.view()['accounts'][0]['state'],before)
        self.assertEqual(D(ledger.wallet()['cash']),67)
        self.assertEqual(D(ledger.wallet()['realized_pnl']),7)
        ledger.prepare();self.assertEqual(D(ledger.wallet()['cash']),67)
        self.assertEqual(ledger.history('slot0')[0]['event_key'],'old-buy')
        with sqlite3.connect(ledger.path) as c:
            original=json.loads(c.execute('SELECT legacy_accounts FROM wallet_migrations').fetchone()[0])
            self.assertEqual(original[0]['state'],before)
    def test_multiple_legacy_wallets_require_explicit_combining_preserving_positions(self):
        ledger=self.legacy(2)
        with self.assertRaisesRegex(Conflict,'Multiple legacy'):ledger.prepare()
        self.assertIsNone(ledger.wallet())
        self.assertEqual(len(ledger.view()['accounts']),2)
        wallet=ledger.migrate(combine=True)
        self.assertEqual(D(wallet['cash']),134)
        self.assertEqual(D(wallet['initial_capital']),200)
        self.assertEqual(D(wallet['realized_pnl']),14)
        self.assertEqual([a['state']['quantity'] for a in ledger.report()],['4','4'])
        ledger.migrate(combine=True);self.assertEqual(D(ledger.wallet()['cash']),134)
    def test_legacy_writer_after_migration_is_rejected(self):
        ledger=self.legacy();ledger.prepare()
        with sqlite3.connect(ledger.path) as c:
            state=json.loads(c.execute('SELECT state FROM accounts').fetchone()[0]);state['cash']='999'
            c.execute('UPDATE accounts SET state=?',(dump(state),))
        with self.assertRaisesRegex(Conflict,'Legacy worker'):ledger.report()
        self.assertEqual(D(ledger.wallet()['cash']),67)
