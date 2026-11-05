import contextlib
import gzip
import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch
import study_pivot_moves as cli
import test_pivot_research as fixtures


class PivotReport(unittest.TestCase):
    def setUp(self):fixtures.PivotCohort.setUp(self)

    def test_real_report_embeds_complete_feature_windows_and_is_reproducible(self):
        path=self.root/'study.json.gz'
        args=['study_pivot_moves.py','--timeframe','1m','--until','1970-01-01T01:00:00Z','--context-cases','1','--output',str(path)]
        with patch('sys.argv',args),contextlib.redirect_stdout(io.StringIO()):self.assertEqual(cli.main(),0)
        first=path.read_bytes();packet=json.loads(gzip.decompress(first))
        self.assertEqual(packet['summary']['pivots'],3)
        self.assertEqual(len(packet['contexts']),1) # all synthetic origin swings hit; no complete failure is fabricated
        self.assertTrue(all(context['bars'] for context in packet['contexts'].values()))
        self.assertIn('ema200',next(iter(packet['contexts'].values()))['bars'][0]['features'])
        with patch('sys.argv',args),contextlib.redirect_stdout(io.StringIO()):cli.main()
        self.assertEqual(first,path.read_bytes())

    def test_publish_is_scoped_to_the_generated_report_only(self):
        path=Path(cli.__file__).resolve().parent/'research_reports'/'example.json.gz'
        with patch.object(cli.subprocess,'check_output',side_effect=['main\n','research_reports/example.json.gz\n']),patch.object(cli.subprocess,'run') as run:
            cli.push_report(path)
        self.assertEqual(run.call_args_list[0].args[0],['git','add','-f','--','research_reports/example.json.gz'])
        self.assertIn('--only',run.call_args_list[1].args[0])
        self.assertEqual(run.call_args_list[-1].args[0],['git','push','origin','main'])
        with self.assertRaises(ValueError):cli.push_report(self.root/'outside.json.gz')
        with patch.object(cli.subprocess,'check_output',return_value='work\n'),patch.object(cli.subprocess,'run') as run:
            with self.assertRaises(ValueError):cli.push_report(path)
            run.assert_not_called()

    def test_sample_is_evenly_spaced_including_period_ends(self):
        self.assertEqual(cli.spaced(list(range(11)),3),[0,5,10])
        self.assertEqual(cli.spaced([1,2],0),[])
