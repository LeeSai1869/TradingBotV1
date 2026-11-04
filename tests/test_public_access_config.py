import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from Section_11_UI_UX.server import public_access,ui_server

class AccessConfig(unittest.TestCase):
    def setUp(self):
        temp=self.enterContext(tempfile.TemporaryDirectory())
        self.path=Path(temp)/'access.json';self.enterContext(patch.object(public_access,'CONFIG_FILE',self.path))
        self.enterContext(patch.object(public_access.mobile_push,'configuration',return_value={}))
        self.enterContext(patch.object(public_access.android_push,'configuration',return_value={}))

    def test_proxy_access_does_not_require_mobile_keys_or_hardcoded_host(self):
        public_access.save_origin('https://my-mac.example.ts.net/')
        self.assertEqual(public_access.configured_origin(),'https://my-mac.example.ts.net')
        server=type('Server',(),dict(headers={'Host':'my-mac.example.ts.net'},server=type('HTTP',(),dict(server_port=8000))()))()
        self.assertTrue(ui_server.Handler._local_host(server));self.assertTrue(public_access.public_request(server))
        server.headers={'Host':'other.example.ts.net'}
        self.assertFalse(ui_server.Handler._local_host(server));self.assertFalse(public_access.public_request(server))

    def test_invalid_or_conflicting_origins_are_rejected(self):
        for value in ('http://example.test','https://user:secret@example.test','https://example.test/path','https://example.test?token=secret','https://example.test:8443'):
            with self.assertRaises(ValueError):public_access.normalize_origin(value)
        self.path.write_text(json.dumps(dict(origin='https://one.test')))
        with patch.object(public_access.mobile_push,'configuration',return_value=dict(origin='https://two.test')):
            with self.assertRaises(ValueError):public_access.configured_origin()

    def test_unconfigured_access_stays_local(self):
        self.assertIsNone(public_access.configured_origin());self.assertFalse(self.path.exists())
