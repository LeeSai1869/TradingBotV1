import io
import json
from pathlib import Path
import stat
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch
import reset_password as recovery
from Section_11_UI_UX.server import auth


class Recovery(unittest.TestCase):
    def setUp(self):
        root=Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.path=root/'users.json'
        self.enterContext(patch.object(auth,'USERS_FILE',self.path))
        salt='12'*16
        self.original={'admin':dict(role='admin',salt=salt,hash=auth.digest('old-password-123',salt),custom=True),
            '0_Master.Jhanzeeb':dict(role='user',salt=salt,hash=auth.digest('other-password-123',salt))}
        self.path.write_text(json.dumps(self.original))

    def test_only_target_credentials_change_and_hash_matches_new_password(self):
        recovery.reset_password('admin','new-password-123')
        result=auth.users()
        self.assertEqual(result['0_Master.Jhanzeeb'],self.original['0_Master.Jhanzeeb'])
        self.assertEqual(result['admin']['role'],'admin');self.assertTrue(result['admin']['custom'])
        self.assertEqual(result['admin']['hash'],auth.digest('new-password-123',result['admin']['salt']))
        self.assertNotEqual(result['admin']['hash'],self.original['admin']['hash'])
        self.assertEqual(stat.S_IMODE(self.path.stat().st_mode),0o600)
        self.assertNotIn('new-password-123',self.path.read_text())

    def test_existing_custom_username_is_supported(self):
        recovery.reset_password('0_Master.Jhanzeeb','custom-password-123')
        self.assertEqual(auth.users()['admin'],self.original['admin'])
        self.assertEqual(auth.users()['0_Master.Jhanzeeb']['role'],'user')

    def test_invalid_input_and_failed_replace_leave_accounts_unchanged(self):
        before=self.path.read_bytes()
        for username,password in [('missing','password-long-123'),('admin','short')]:
            with self.assertRaises(ValueError):recovery.reset_password(username,password)
            self.assertEqual(self.path.read_bytes(),before)
        with patch.object(recovery.os,'replace',side_effect=OSError('write failed')),self.assertRaises(OSError):
            recovery.reset_password('admin','new-password-123')
        self.assertEqual(self.path.read_bytes(),before)
        self.assertEqual(set(p.name for p in self.path.parent.iterdir()),{'users.json','users.lock'})

    def test_listing_excludes_hashes_and_salts(self):
        with patch('sys.argv',['reset_password.py','--list']),redirect_stdout(io.StringIO()) as output:recovery.main()
        self.assertIn('0_Master.Jhanzeeb',output.getvalue())
        for account in self.original.values():
            self.assertNotIn(account['hash'],output.getvalue());self.assertNotIn(account['salt'],output.getvalue())
