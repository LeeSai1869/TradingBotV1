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

    def test_merge_conflicts_are_reported_before_any_services_are_stopped(self):
        self.git('stash','push','-qm','temporary runtime')
        self.git('switch','-q','cleanup')
        self.write('conflict.txt',b'cleanup branch');self.git('add','.');self.git('commit','-qm','cleanup extra')
        self.git('switch','-q','main')
        self.write('conflict.txt',b'local branch');self.git('add','.');self.git('commit','-qm','local extra')
        self.git('stash','pop','-q')
        with self.assertRaisesRegex(RuntimeError,'(?s)preview found conflicts.*conflict.txt'):
            finish(self.root,'cleanup',self.stash,stop_services=self.stopped)
        self.assertEqual(self.services,[])
        self.assertEqual((self.root/RUNTIME[0]).read_bytes(),b'{"cursor":987}')
        self.assertEqual((self.root/'conflict.txt').read_bytes(),b'local branch')

    def test_known_styles_conflict_keeps_local_fixture_and_only_rebases_imports(self):
        from Section_14_Operations.finish_repository_cleanup import KNOWN_TEST_CONFLICT
        root=self.root.parent/'Styles repo';root.mkdir()
        def run(*args):return subprocess.check_output(['git',*args],cwd=root,stderr=subprocess.STDOUT).decode()
        def write(name,data):
            p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
        run('init','-q','-b','main');run('config','user.email','test@example.invalid');run('config','user.name','Test')
        old='tests/feature_styles.test.mjs'
        base=b"import x from '../Section_11_UI_UX/example.js';\nconst options = 'base';\n"+b"// unchanged test assertions\n"*30
        write(old,base);write(REPORT,b'\0report');write(RUNTIME[0],b'{"cursor":1}')
        write('Section_11_UI_UX/example.js',b'unchanged UI');run('add','.');run('commit','-qm','base')
        run('switch','-qc','cleanup')
        target=root/KNOWN_TEST_CONFLICT;target.parent.mkdir(parents=True,exist_ok=True);(root/old).rename(target)
        write(KNOWN_TEST_CONFLICT,base.replace(b"'../",b"'../../").replace(b"'base'",b"'cleanup version'"))
        new_report='Section_12_Research/reports/report.gz';(root/new_report).parent.mkdir(parents=True,exist_ok=True);(root/REPORT).rename(root/new_report)
        write('Section_13_Development/repository_layout/moves.json',json.dumps(dict(moves=[dict(old=old,new=KNOWN_TEST_CONFLICT),dict(old=REPORT,new=new_report)])).encode())
        run('add','-A');run('commit','-qm','cleanup');run('switch','-q','main')
        local=base.replace(b"'base'",b"'user version'")+b'// Keep this user assertion\n'
        write(old,local);run('add','.');run('commit','-qm','user fixture change')
        write(REPORT,b'\0local report');run('stash','push','-qm','report-before-cleanup');stash=report_stash(root)
        write(RUNTIME[0],b'{"cursor":999}')
        finish(root,'cleanup',stash,stop_services=self.stopped)
        self.assertEqual((root/KNOWN_TEST_CONFLICT).read_bytes(),local.replace(b"'../Section_11_UI_UX/",b"'../../Section_11_UI_UX/"))
        self.assertEqual((root/'Section_11_UI_UX/example.js').read_bytes(),b'unchanged UI')
        self.assertEqual((root/RUNTIME[0]).read_bytes(),b'{"cursor":999}')
        self.assertEqual((root/new_report).read_bytes(),b'\0local report')
