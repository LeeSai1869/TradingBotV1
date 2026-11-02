import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from add_user import add_user
from Section_11_UI_UX.server import auth

class MobileUsers(unittest.TestCase):
    def test_add_user_preserves_other_accounts_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as directory,patch.object(auth,'USERS_FILE',Path(directory)/'users.json'):
            original={'admin':{'role':'admin','salt':'untouched','hash':'untouched'}};auth.USERS_FILE.write_text(json.dumps(original))
            add_user('friend','a-private-test-password')
            accounts=auth.users();self.assertEqual(accounts['admin'],original['admin']);self.assertEqual(accounts['friend']['role'],'user')
            with self.assertRaises(ValueError):add_user('admin','new-private-test-password')
            self.assertEqual(auth.users(),accounts);self.assertEqual(auth.USERS_FILE.stat().st_mode&0o777,0o600)
