import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from Section_11_UI_UX.server import drawing_routes as routes


class DrawingTests(unittest.TestCase):
    def test_account_isolation_revisions_validation_and_delete(self):
        drawing={'type':'horizontal','anchors':[{'time':123,'offset':0,'price':100}],
                 'style':{'color':'#abcdef','width':3,'pattern':'dotted','fillOpacity':.2},'locked':True,'timeframes':['1m','15m']}
        server=SimpleNamespace(headers={'Host':'127.0.0.1:8000','Origin':'http://127.0.0.1:8000'})
        with tempfile.TemporaryDirectory() as folder,patch.object(routes.auth,'USERS_FILE',Path(folder)/'users.json'),patch.object(routes.admin_routes,'user',return_value={'role':'user','username':'alice'}) as identity:
            self.assertEqual(routes.handle_get('/api/drawings','symbol=ETHUSDT',server)[1]['revision'],0)
            payload={'symbol':'ETHUSDT','revision':0,'drawings':[drawing]}
            self.assertEqual(routes.handle_post('/api/drawings',json.dumps(payload),server)[0],200)
            self.assertEqual(routes.handle_get('/api/drawings','symbol=ETHUSDT',server)[1]['drawings'][0],drawing)
            self.assertEqual(routes.handle_post('/api/drawings',json.dumps(payload),server)[0],409)
            identity.return_value={'role':'user','username':'bob'}
            self.assertEqual(routes.handle_get('/api/drawings','symbol=ETHUSDT',server)[1]['drawings'],[])
            identity.return_value={'role':'user','username':'alice'}
            payload['revision']=1;payload['drawings']=[]
            self.assertEqual(routes.handle_post('/api/drawings',json.dumps(payload),server)[0],200)
            self.assertEqual(routes.handle_get('/api/drawings','symbol=ETHUSDT',server)[1]['drawings'],[])
            server.headers['Origin']='https://other.example'
            self.assertEqual(routes.handle_post('/api/drawings',json.dumps(payload),server)[0],403)
            identity.return_value={'role':'guest'}
            self.assertEqual(routes.handle_get('/api/drawings','symbol=ETHUSDT',server)[0],401)
            self.assertEqual(routes.handle_post('/api/drawings',json.dumps(payload),server)[0],401)
        for invalid in [{'type':'bad'},{**drawing,'anchors':[{'time':float('nan'),'offset':0,'price':1}]},{**drawing,'timeframes':['bad']}]:
            with self.assertRaises(ValueError):routes.validate([invalid])
