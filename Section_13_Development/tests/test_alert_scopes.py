"""ALL rules keep pair-specific state; full-day history stays private and paginated."""
import json
import unittest
from unittest.mock import patch
import test_data_admin as fixtures
from Section_11_UI_UX.server import alerts,alert_routes
from Section_1_Global_Core.memory_storage.Storage import db


class AlertScopes(unittest.TestCase):
    setUp=fixtures.DataAdminTests.setUp
    server=fixtures.DataAdminTests.server

    def rule(self,**changes):
        return dict(name='All markets',symbol='ALL',interval='ALL',field='client.high',operator='above',
                    value=1,target_field=None,repeat='per_bar',sound='none',notify=True,enabled=True,mode='closed')|changes

    def arm(self,**changes):
        with patch.object(alerts.time,'time',return_value=120):return alerts.save('admin',self.rule(**changes))

    def bars(self,t=180000):
        for symbol in ('BTCUSDT','SUIUSDT'):
            for interval,duration in (('1m',60000),('3m',180000)):
                db.write_klines([dict(self.rows[0],symbol=symbol,interval=interval,open_time=t,close_time=t+duration-1)])

    def test_all_combinations_deliver_per_pair_once_and_remain_one_editable_rule(self):
        with patch.object(alerts.data_policy,'active_intervals',return_value=['1m','3m']):
            key=self.arm();self.bars()
            with patch.object(alerts.time,'time',return_value=400):alerts.evaluate_once();alerts.evaluate_once()
        rules=alerts.list_rules('admin');self.assertEqual(len(rules),1)
        self.assertEqual((rules[0]['id'],rules[0]['symbol'],rules[0]['interval']),(key,'ALL','ALL'))
        events=alerts.events('admin',0)['events']
        self.assertEqual({(event['symbol'],event['interval']) for event in events},
                         {('BTCUSDT','1m'),('BTCUSDT','3m'),('SUIUSDT','1m'),('SUIUSDT','3m')})
        self.assertEqual(len(events),4);self.assertTrue(all(event['notify'] for event in events))
        self.assertEqual(alerts.events('user',0)['events'],[])

    def test_either_selector_can_be_all_independently(self):
        with patch.object(alerts.data_policy,'active_intervals',return_value=['1m','3m']):
            self.arm(symbol='ALL',interval='1m',name='Coins')
            self.arm(symbol='BTCUSDT',interval='ALL',name='Timeframes')
            self.bars()
            with patch.object(alerts.time,'time',return_value=400):alerts.evaluate_once()
        events=alerts.events('admin',0)['events']
        self.assertEqual({(event['name'],event['symbol'],event['interval']) for event in events},
                         {('Coins','BTCUSDT','1m'),('Coins','SUIUSDT','1m'),('Timeframes','BTCUSDT','1m'),('Timeframes','BTCUSDT','3m')})

    def test_newly_active_pairs_skip_existing_history(self):
        with patch.object(alerts.data_policy,'active_symbols',return_value=['BTCUSDT']):self.arm(interval='1m')
        self.bars()
        with patch.object(alerts.time,'time',return_value=240):alerts.sync_scoped_rules()
        with patch.object(alerts.time,'time',return_value=400):alerts.evaluate_once()
        self.assertFalse(any(event['symbol']=='SUIUSDT' for event in alerts.events('admin',0)['events']))
        db.write_klines([dict(self.rows[0],symbol='SUIUSDT',open_time=240000,close_time=299999)])
        with patch.object(alerts.time,'time',return_value=400):alerts.evaluate_once()
        self.assertEqual(len([event for event in alerts.events('admin',0)['events'] if event['symbol']=='SUIUSDT']),1)

    def test_once_is_independent_per_pair_and_delete_removes_private_workers(self):
        with patch.object(alerts.data_policy,'active_intervals',return_value=['1m','3m']):
            key=self.arm(repeat='once');self.bars()
            with patch.object(alerts.time,'time',return_value=400):alerts.evaluate_once()
            self.bars(360000)
            with patch.object(alerts.time,'time',return_value=700):alerts.evaluate_once();alerts.evaluate_once()
        self.assertEqual(len(alerts.events('admin',0)['events']),4)
        alerts.delete('user',key);self.assertEqual(len(alerts.list_rules('admin')),1)
        alerts.delete('admin',key)
        conn=alerts.open_db()
        try:self.assertEqual(conn.execute('SELECT COUNT(*) FROM rules').fetchone()[0],0)
        finally:conn.close()
        self.assertEqual(len(alerts.events('admin',0)['events']),4)

    def test_edit_rejects_stale_workers_and_internal_ids_cannot_be_managed(self):
        key=self.arm(interval='1m')
        conn=alerts.open_db()
        try:child=conn.execute("SELECT * FROM rules WHERE id LIKE 'scope:%' ORDER BY id LIMIT 1").fetchone()
        finally:conn.close()
        for owner in ('admin','user'):
            with self.assertRaises(ValueError):alerts.save(owner,self.rule(id=child['id']))
            with self.assertRaises(ValueError):alerts.delete(owner,child['id'])
        self.bars()
        with patch.object(alerts.time,'time',return_value=120):alerts.save('admin',self.rule(id=key,interval='1m',value=1000))
        with patch.object(alerts.time,'time',return_value=400):alerts.evaluate_rule(child);alerts.evaluate_once()
        self.assertEqual(alerts.events('admin',0)['events'],[])
        self.assertEqual(alerts.list_rules('admin')[0]['value'],1000)

    def test_private_workers_do_not_count_against_the_fifty_rule_limit(self):
        for index in range(3):self.arm(name=str(index))
        self.arm(name='Fourth')
        self.assertEqual(len(alerts.list_rules('admin')),4)

    def test_full_day_history_filters_paginates_and_keeps_mobile_history_unchanged(self):
        now=2_000_000_000_000;since=now-86_400_000
        conn=alerts.open_db()
        try:
            with conn:
                for index in range(129):
                    owner='user' if index==128 else 'admin'
                    created=since-1 if index==0 else now+1 if index==127 else since+index
                    packet=dict(name='History',symbol='BTCUSDT',interval='1m',created=created,bar_time=index,notify=True)
                    conn.execute('INSERT INTO events(owner,rule_id,epoch,bar_time,created,packet) VALUES (?,?,?,?,?,?)',
                                 (owner,'history','0',index,created,json.dumps(packet)))
            first=alerts.events('admin',None,history_since=since,history_until=now,history_limit=100)
            second=alerts.events('admin',None,history_since=since,history_until=now,history_limit=100,history_before=first['next_before'])
            self.assertTrue(first['has_more']);self.assertFalse(second['has_more'])
            self.assertEqual(len(first['history'])+len(second['history']),126)
            self.assertEqual(len({event['seq'] for event in first['history']+second['history']}),126)
            self.assertEqual(len(alerts.events('admin',None)['history']),20)
            code,packet=alert_routes.handle_get('/api/alerts/history',f'since={since}&until={now}&limit=100',self.server('admin'))
            self.assertEqual(code,200);self.assertEqual(len(packet['history']),100)
            self.assertEqual(alert_routes.handle_get('/api/alerts/history','since=bad',self.server('admin'))[0],400)
            self.assertEqual(alert_routes.handle_get('/api/alerts/history','since=20&until=10',self.server('admin'))[0],400)
            self.assertEqual(alert_routes.handle_get('/api/alerts/history','',self.server())[0],401)
        finally:conn.close()

    def test_custom_history_excludes_automatic_decisions_without_filtering_delivery(self):
        conn=alerts.open_db()
        try:
            with conn:
                for index in range(250):
                    automatic=index%2==0
                    packet=dict(name='Automatic BUY' if automatic else 'My BUY alert',symbol='BTCUSDT',interval='1m',
                                field='decision.buy',created=1000+index,bar_time=index,notify=True)
                    rule_id='auto:signal' if automatic else 'scope:custom'
                    conn.execute('INSERT INTO events(owner,rule_id,epoch,bar_time,created,packet) VALUES (?,?,?,?,?,?)',
                                 ('admin',rule_id,'0',index,packet['created'],json.dumps(packet)))
            code,first=alert_routes.handle_get('/api/alerts/history','source=custom&limit=100',self.server('admin'))
            self.assertEqual(code,200);self.assertEqual(len(first['history']),100);self.assertTrue(first['has_more'])
            code,second=alert_routes.handle_get('/api/alerts/history',f"source=custom&limit=100&before={first['next_before']}",self.server('admin'))
            self.assertEqual(code,200);self.assertEqual(len(second['history']),25);self.assertFalse(second['has_more'])
            self.assertTrue(all(event['source']=='custom' and event['name']=='My BUY alert' for event in first['history']+second['history']))
            # Mobile history and the live desktop feed retain automatic signal events.
            code,mobile=alert_routes.handle_get('/api/alerts/history','limit=100',self.server('admin'))
            self.assertEqual(code,200);self.assertTrue(any(event['source']=='signal' for event in mobile['history']))
            delivered=alerts.events('admin',0)['events']
            self.assertTrue(any(event['source']=='signal' and event['notify'] for event in delivered))
            self.assertEqual(alert_routes.handle_get('/api/alerts/history','source=invalid',self.server('admin'))[0],400)
        finally:conn.close()


if __name__=='__main__':unittest.main()
