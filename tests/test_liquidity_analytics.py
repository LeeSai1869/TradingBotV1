"""Causal rolling observations and recovery semantics, without exchange I/O."""
import unittest
from Section_1_Global_Core.liquidity.analytics import Analytics
from Section_1_Global_Core.liquidity.summary import Minutes


def packet(now, *, continuous=True, mid=100., buy=90., sell=10., oi=100.):
    return dict(symbol='BTCUSDT',available_ms=now,exchange_ms=now,book_received_ms=now,
        window_start_ms=now-5000,book_window_start_ms=now-5000,
        trade_coverage='continuous' if continuous else 'partial',aggressive_buy_usdt=buy,
        aggressive_sell_usdt=sell,metrics=dict(mid=mid,spread_bps=1.,imbalance_10bps=.3),
        context=dict(open_interest=oi,open_interest_exchange_ms=now,mark_price=101.,index_price=100.),
        coverage=dict(bid_bps=15.,ask_bps=17.),radius_bps=100,
        bands=[dict(side='bid',notional_usdt=100.,sampled_presence_ms=40000),
               dict(side='ask',notional_usdt=200.,sampled_presence_ms=0)])


class AnalyticsTests(unittest.TestCase):
    def test_warmup_then_complete_flow_and_absorption(self):
        a=Analytics()
        first=a.add(packet(5000))['analytics']
        self.assertFalse(first['60s']['complete']);self.assertIsNone(first['60s']['delta_usdt'])
        for now in range(10000,60001,5000):last=a.add(packet(now))
        flow=last['analytics']['60s']
        self.assertTrue(flow['complete']);self.assertEqual(flow['delta_usdt'],960.)
        self.assertTrue(flow['buy_absorption_evidence']);self.assertFalse(flow['sell_absorption_evidence'])
        self.assertAlmostEqual(last['analytics']['mark_index_basis_bps'],100.)
        self.assertEqual(last['analytics']['bid_persistent_30s_share'],1.)
        self.assertEqual(last['analytics']['ask_persistent_30s_share'],0.)

    def test_real_scheduler_jitter_does_not_prevent_warmup(self):
        a=Analytics();last=0
        for index in range(1,14):
            now=index*5001;p=packet(now);p['window_start_ms']=last
            a.add(p);last=now
        self.assertTrue(p['analytics']['60s']['complete'])
        self.assertEqual(p['analytics']['60s']['observed_window_ms'],60012)
        self.assertEqual(p['analytics']['60s']['aggressive_buy_usdt'],1080.)

    def test_gap_partial_and_clock_reversal_reset_cvd(self):
        a=Analytics();a.add(packet(5000));a.add(packet(10000))
        partial=a.add(packet(15000,continuous=False))['analytics']
        self.assertIsNone(partial['cvd_since_continuity_usdt'])
        after=a.add(packet(20000))['analytics'];self.assertEqual(after['cvd_since_continuity_usdt'],80.)
        gap=a.add(packet(40000))['analytics'];self.assertFalse(gap['60s']['complete'])
        self.assertEqual(gap['cvd_since_continuity_usdt'],80.)
        reverse=a.add(packet(35000))['analytics'];self.assertEqual(reverse['cvd_since_continuity_usdt'],80.)

    def test_position_change_requires_real_baseline_and_context(self):
        a=Analytics()
        for now in range(5000,310001,5000):p=a.add(packet(now,oi=110. if now>=305000 else 100.))
        self.assertAlmostEqual(p['analytics']['open_interest_change_5m_pct'],10.)
        p=packet(315000);p['context']={};a.add(p)
        self.assertIsNone(p['analytics']['open_interest_change_5m_pct'])
        self.assertIsNone(p['analytics']['mark_index_basis_bps'])
        self.assertFalse(p['health']['open_interest_fresh'])
        self.assertFalse(p['health']['mark_context_fresh'])

    def test_price_response_rejects_absorption_when_price_moves(self):
        a=Analytics()
        for now in range(5000,60001,5000):p=a.add(packet(now,mid=100+now/60000))
        self.assertFalse(p['analytics']['60s']['buy_absorption_evidence'])
        self.assertGreater(p['analytics']['realized_volatility_60s_bps'],0.)

    def test_memory_bounded_and_closed_summary_retains_analytics(self):
        a=Analytics();minutes=Minutes('BTCUSDT');closed=None
        for now in range(5000,10000001,5000):
            p=a.add(packet(now));closed=minutes.add(p) or closed
        self.assertLessEqual(len(a.rows),180);self.assertLessEqual(len(a.oi),180)
        self.assertEqual(closed['analytics_last']['version'],1)
        self.assertIn('book_age_ms',closed['health_last'])

if __name__=='__main__':unittest.main()

class MarketContextTests(unittest.TestCase):
    def test_asof_alignment_missing_benchmark_and_recovery(self):
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        from Section_1_Global_Core.liquidity import store
        with tempfile.TemporaryDirectory() as root, patch.object(store,'DB_PATH',Path(root)/'liquidity.db'):
            conn=store.open_writer()
            try:
                for now in range(5000,310001,5000):
                    for symbol,factor in [('BTCUSDT',1),('ETHUSDT',2)]:
                        p=packet(now,mid=100+factor*(now/5000)**2/1000);p['symbol']=symbol
                        store.write_sample(conn,p,now)
                conn.commit()
                result=store.market_context_at('ETHUSDT',310000)['benchmarks']
                self.assertTrue(result['BTCUSDT']['complete'])
                self.assertGreater(result['BTCUSDT']['correlation_5m'],.99)
                self.assertGreater(result['BTCUSDT']['relative_return_5m_bps'],0)
                self.assertFalse(store.market_context_at('SOLUSDT',310000)['benchmarks']['BTCUSDT']['complete'])
                self.assertFalse(store.market_context_at('ETHUSDT',10000)['benchmarks']['BTCUSDT']['complete'])
                store.set_status(conn,'BTCUSDT','resynchronizing','gap',309000);conn.commit()
                self.assertFalse(store.market_context_at('ETHUSDT',310000)['benchmarks']['BTCUSDT']['complete'])
            finally:conn.close()
