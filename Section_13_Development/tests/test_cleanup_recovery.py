"""Real Git merges preserve state, relocated binary reports and edited tests."""
from contextlib import contextmanager
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from Section_14_Operations.finish_repository_cleanup import finish, report_stash, REPORT, RUNTIME


class CleanupRecovery(unittest.TestCase):
    def setUp(self):
        temporary=self.enterContext(tempfile.TemporaryDirectory())
        self.root=Path(temporary)/'App with spaces';self.root.mkdir()
        self.git('init','-q','-b','main');self.git('config','user.email','test@example.invalid');self.git('config','user.name','Test')
        self.write('tests/example.py',b'import old_fixture\nvalue = 1\n')
        self.write(REPORT,b'\x00original report')
        self.write(RUNTIME[0],b'{"cursor":1}')
        self.write('Section_11_UI_UX/view.js',b'original UI')
        self.git('add','.');self.git('commit','-qm','base')
        self.git('switch','-qc','cleanup')
        moves=[]
        for old,new in [('tests/example.py','Section_13_Development/tests/example.py'),(REPORT,'Section_12_Research/reports/BTC_1h_sequences/strategy_analyzer/strategy_analysis.json.gz')]:
            target=self.root/new;target.parent.mkdir(parents=True,exist_ok=True);(self.root/old).rename(target)
            moves.append(dict(old=old,new=new))
        self.write('Section_13_Development/tests/example.py',b'import new_fixture\nvalue = 1\n')
        self.write('Section_13_Development/repository_layout/moves.json',json.dumps(dict(moves=moves)).encode())
        self.git('add','-A');self.git('commit','-qm','organize')
        self.git('switch','-q','main')
        self.write('tests/example.py',b'import old_fixture\nvalue = 1\n# saved test edit\n')
        self.write(REPORT,b'\x00local report edit')
        self.git('stash','push','-qm','report-before-cleanup')
        self.stash=report_stash(self.root)
        self.write(RUNTIME[0],b'{"cursor":987}')
        self.services=[]

    def git(self,*args):
        return subprocess.check_output(['git',*args],cwd=self.root,stderr=subprocess.STDOUT).decode()

    def write(self,name,value):
        path=self.root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(value)

    @contextmanager
    def stopped(self):
        self.services.append('stopped')
        try:yield
        finally:self.services.append('restarted')

    def test_recovers_edits_at_new_paths_without_reverting_current_state(self):
        finish(self.root,'cleanup',self.stash,stop_services=self.stopped)
        self.assertEqual((self.root/RUNTIME[0]).read_bytes(),b'{"cursor":987}')
        self.assertEqual((self.root/'Section_11_UI_UX/view.js').read_bytes(),b'original UI')
        self.assertEqual((self.root/'Section_13_Development/tests/example.py').read_bytes(),b'import new_fixture\nvalue = 1\n# saved test edit\n')
        self.assertEqual((self.root/'Section_12_Research/reports/BTC_1h_sequences/strategy_analyzer/strategy_analysis.json.gz').read_bytes(),b'\x00local report edit')
        self.assertIn(self.stash,self.git('stash','list','--format=%H'))
        self.assertEqual(self.services,['stopped','restarted'])

    def test_aborts_a_merge_that_would_change_ui_and_still_restores_state(self):
        self.git('stash','push','-qm','temporary runtime')
        self.git('switch','-q','cleanup')
        self.write('Section_11_UI_UX/view.js',b'changed UI');self.git('add','.');self.git('commit','-qm','UI change')
        self.git('switch','-q','main');self.git('stash','pop','-q')
        before=self.git('rev-parse','HEAD')
        with self.assertRaisesRegex(RuntimeError,'UI/UX'):
            finish(self.root,'cleanup',self.stash,stop_services=self.stopped)
        self.assertEqual(self.git('rev-parse','HEAD'),before)
        self.assertEqual((self.root/RUNTIME[0]).read_bytes(),b'{"cursor":987}')
        self.assertEqual((self.root/'Section_11_UI_UX/view.js').read_bytes(),b'original UI')
        self.assertEqual(self.services,['stopped','restarted'])

    def test_partial_report_stash_also_retains_previously_staged_test_edits(self):
        self.git('stash','apply',self.stash)
        self.git('add','tests/example.py')
        self.git('stash','push','-qm','report-before-cleanup','--',REPORT)
        stash=report_stash(self.root)
        # Reproduce the clean index/worktree left after the failed merge rollback.
        self.git('restore','--source=HEAD','--staged','--worktree','--','tests/example.py')
        finish(self.root,'cleanup',stash,stop_services=self.stopped)
        self.assertIn(b'# saved test edit',(self.root/'Section_13_Development/tests/example.py').read_bytes())
