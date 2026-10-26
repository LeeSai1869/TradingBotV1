import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from Section_1_Global_Core.tools import check_imports as guard

class ImportBoundaryTests(unittest.TestCase):
    def test_exact_integrations_do_not_authorize_unrelated_private_imports(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);core=root/'Section_1_Global_Core';core.mkdir()
            (root/'worker.py').write_text('from Section_1_Global_Core.memory_storage import Storage\n')
            grants=root/'grants.json';grants.write_text(json.dumps({'integrations':{'worker.py':['Section_1_Global_Core.memory_storage']}}))
            with patch.object(guard,'PROJECT_ROOT',root),patch.object(guard,'GLOBAL_CORE',core),patch.object(guard,'_INTEGRATIONS_FILE',grants),contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(guard.scan(),0)
                (root/'other.py').write_text('from Section_1_Global_Core.memory_storage import Storage\n')
                self.assertEqual(guard.scan(),1)

    def test_retired_engines_are_rejected_even_in_tests(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'tests').mkdir();core=root/'Section_1_Global_Core';core.mkdir()
            (root/'tests/test_old.py').write_text('import Section_6_Base_Scoring_Engines\n')
            with patch.object(guard,'PROJECT_ROOT',root),patch.object(guard,'GLOBAL_CORE',core),contextlib.redirect_stdout(io.StringIO()):self.assertEqual(guard.scan(),1)

    def test_registry_has_no_missing_files_and_runtime_processors_are_current(self):
        root=guard.PROJECT_ROOT
        for file,_ in guard._load_integrations():self.assertTrue((root/file).is_file(),file)
        processors=json.loads((root/'Section_1_Global_Core/processors.json').read_text())['processors']
        self.assertEqual([p['module'] for p in processors],['Section_4_Features.processor','Section_8_Decision_Engine.processor'])
