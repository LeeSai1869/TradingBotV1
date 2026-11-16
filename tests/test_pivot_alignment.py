import unittest
from research_reports.BTC_1h_bear_target_breakouts_v3 import pivot_alignment as audit

H=audit.HOUR
def pivot(origin=10*H,known=12*H,id='low'):
    return dict(id=id,origin_time=origin,known_time=known,price=100)

class PivotPlacementTests(unittest.TestCase):
    def test_origin_next_and_confirmation_are_distinct(self):
        event=pivot();by_origin={10*H:[event]}
        self.assertEqual(audit.placement(10*H+5*60000,by_origin)['category'],'pivot_candle')
        next_bar=audit.placement(11*H+5*60000,by_origin)
        self.assertEqual(next_bar['category'],'next_candle');self.assertFalse(next_bar['already_known'])
        self.assertEqual(audit.placement(12*H,by_origin)['category'],'elsewhere')

    def test_confirmation_bucket_never_implies_knowledge_before_exact_known_time(self):
        event=pivot(known=12*H+30*60000);by_known={12*H:[event]}
        self.assertEqual(audit.placement(12*H,by_known,basis='known_time')['category'],'elsewhere')
        self.assertEqual(audit.placement(event['known_time'],by_known,basis='known_time')['category'],'pivot_candle')
        self.assertEqual(audit.placement(13*H,by_known,basis='known_time')['category'],'next_candle')

    def test_exit_bar_not_its_upper_bound_determines_the_hour(self):
        event=pivot(id='high');by_origin={10*H:[event]}
        self.assertEqual(audit.placement(11*H-60000,by_origin)['category'],'pivot_candle')
        self.assertEqual(audit.placement(11*H,by_origin)['category'],'next_candle')

    def test_overlapping_origin_windows_are_counted_once(self):
        previous=pivot(origin=9*H,id='previous');current=pivot()
        match=audit.placement(10*H+1,{9*H:[previous],10*H:[current]})
        self.assertEqual(match['category'],'pivot_candle')
        result=audit.summarize_side([{'buy':match}],'buy')
        self.assertEqual(result['combined'],1);self.assertEqual(result['pivot_candle']+result['next_candle'],1)

    def test_qualified_swing_path_rejects_short_or_invalid_candles(self):
        row=dict(open_time=0,close_time=H-1,open=100,high=102,low=99,close=101)
        self.assertTrue(audit.full_candle(row))
        self.assertFalse(audit.full_candle({**row,'close_time':H-2}))
        self.assertFalse(audit.full_candle({**row,'low':103}))
        self.assertFalse(audit.full_candle(None))

if __name__=='__main__':unittest.main()
