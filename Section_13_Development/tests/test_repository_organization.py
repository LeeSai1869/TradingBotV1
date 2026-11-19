from pathlib import Path
import subprocess
import tempfile
import unittest
from Section_14_Operations.organize_local_files import organize


class LocalOrganization(unittest.TestCase):
    def test_moves_only_untracked_artifacts_and_preserves_conflicts_and_data(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(['git','init','-q',str(root)], check=True)
            files = {
                'research_reports/local.txt': 'local',
                'research_reports/record.json': 'edited',
                'Section_12_Research/reports/record.json': 'committed',
                'research_reports/keep.db': 'db',
                'research_reports/.env': 'private',
                'research_reports/tracked.txt': 'tracked',
                'features_store.py.bak': 'backup',
                'Section_4_Features/processor.py.before-slope-write-policy': 'old code',
                'Section_1_Global_Core/memory_storage/Storage/features.db.compaction.json': 'keep report',
            }
            for name, content in files.items():
                path = root/name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content)
            subprocess.run(['git','add','research_reports/tracked.txt'], cwd=root, check=True)
            preview = organize(root)
            self.assertEqual(len(preview['moves']), 4)
            self.assertTrue((root/'research_reports/local.txt').exists())
            organize(root, apply=True)
            self.assertEqual((root/'Section_12_Research/reports/local.txt').read_text(),'local')
            self.assertEqual((root/'Section_12_Research/reports/record.json').read_text(),'committed')
            self.assertEqual((root/'Section_13_Development/local_archive/research_reports/record.json').read_text(),'edited')
            for name in ('keep.db','.env','tracked.txt'):
                self.assertTrue((root/'research_reports'/name).exists())
            self.assertEqual((root/'Section_13_Development/local_archive/Section_4_Features/processor.py.before-slope-write-policy').read_text(),'old code')
            self.assertTrue((root/'Section_1_Global_Core/memory_storage/Storage/features.db.compaction.json').exists())
            self.assertEqual(organize(root)['moves'], [])


class TrackedOrganization(unittest.TestCase):
    def test_every_recorded_move_exists_and_frozen_inputs_are_unchanged(self):
        import hashlib
        import json
        from Section_1_Global_Core.paths import REPO_ROOT
        document = json.loads((REPO_ROOT/'Section_13_Development/repository_layout/moves.json').read_text())
        for move in document['moves']:
            target = REPO_ROOT/move['new']
            self.assertTrue(target.is_file(), move['new'])
            self.assertFalse((REPO_ROOT/move['old']).is_file(), move['old'])
            if (move['old'].startswith('research_reports/') and target.suffix in ('.json','.csv','.gz','.html')) or target.suffix == '.pine':
                self.assertEqual(hashlib.sha256(target.read_bytes()).hexdigest(), move['original_sha256'], move['new'])

    def test_moved_commands_resolve_checkout_from_unrelated_working_directory(self):
        import sys
        from Section_1_Global_Core.paths import REPO_ROOT
        with tempfile.TemporaryDirectory() as directory:
            for script in ('Section_14_Operations/storage/compact_feature_storage.py',
                           'Section_13_Development/diagnostics/profile_chart_loading.py',
                           'Section_12_Research/cli/open_strategy_study.py'):
                result = subprocess.run([sys.executable,str(REPO_ROOT/script),'--help'],cwd=directory,text=True,capture_output=True)
                self.assertEqual(result.returncode,0,result.stderr)
                self.assertIn('usage:',result.stdout)

    def test_application_does_not_import_research_or_maintenance_packages(self):
        import ast
        from Section_1_Global_Core.paths import REPO_ROOT
        forbidden = ('Section_12_Research','Section_13_Development','Section_14_Operations')
        for section in REPO_ROOT.glob('Section_*'):
            if section.name.startswith(forbidden):
                continue
            for source in section.rglob('*.py'):
                for node in ast.walk(ast.parse(source.read_text())):
                    names = [a.name for a in node.names] if isinstance(node,ast.Import) else [node.module or ''] if isinstance(node,ast.ImportFrom) else []
                    for name in names:
                        self.assertFalse(name.startswith(forbidden),f'{source}: {name}')
