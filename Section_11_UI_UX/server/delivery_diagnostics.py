"""Read-only notification pipeline status; never exposes credentials/device tokens."""
import json
import sqlite3
from . import auth,android_push,mobile_push,public_access


def report():
    result=dict(android=android_push.status(),web_push=mobile_push.status(),origin_consistent=True,
                store='MISSING',accounts=[],devices={})
    try:public_access.configured_origin()
    except (ValueError,OSError):result['origin_consistent']=False
    path=auth.USERS_FILE.with_name('alerts.sqlite3')
    if not path.is_file():return result
    conn=sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True,timeout=.5)
    try:
        conn.execute('BEGIN')
        tables={r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        result['store']='READABLE'
        if 'events' in tables:
            row=conn.execute('SELECT COUNT(*),MAX(created) FROM events').fetchone()
            result['stored_events']=row[0];result['last_event_created_ms']=row[1]
        if 'signal_preferences' in tables:
            for owner,encoded in conn.execute('SELECT owner,spec FROM signal_preferences ORDER BY owner'):
                spec=json.loads(encoded)
                result['accounts'].append(dict(account=owner,monitoring=spec.get('enabled',True),desktop=spec.get('notify',True),
                    mobile=spec.get('mobile',False),buy=spec.get('buy_notify',True),sell=spec.get('sell_notify',True),
                    muted_mobile_coins=sum(flags.get('mobile') is False for flags in spec.get('coins',{}).values()),
                    muted_mobile_timeframes=sum(flags.get('mobile') is False for flags in spec.get('timeframes',{}).values())))
        for name,table in (('android','android_devices'),('web_push','push_devices')):
            if table not in tables:continue
            columns={r[1] for r in conn.execute('PRAGMA table_info('+table+')')}
            enabled='SUM(CASE WHEN enabled=1 THEN 1 ELSE 0 END)' if 'enabled' in columns else 'COUNT(*)'
            row=conn.execute('SELECT COUNT(*),'+enabled+',SUM(CASE WHEN failures>0 THEN 1 ELSE 0 END) FROM '+table).fetchone()
            result['devices'][name]=dict(registered=row[0],enabled=row[1] or 0,retrying=row[2] or 0)
        if 'rules' in tables:
            result['rule_status_counts']={status:count for status,count in conn.execute('SELECT status,COUNT(*) FROM rules GROUP BY status')}
        return result
    finally:conn.close()
