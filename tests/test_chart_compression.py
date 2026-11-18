"""Large chart JSON negotiates lossless compression; small/live replies stay cheap."""
import gzip
import io
import json
from types import SimpleNamespace
import unittest
from Section_11_UI_UX.server.ui_server import Handler,_accepts_gzip


class ChartCompression(unittest.TestCase):
    def reply(self,packet,encoding=''):
        headers={};statuses=[]
        handler=SimpleNamespace(headers={'Accept-Encoding':encoding},wfile=io.BytesIO(),
            send_response=statuses.append,send_header=lambda k,v:headers.update({k:v}),end_headers=lambda:None)
        Handler._json(handler,packet)
        body=handler.wfile.getvalue()
        self.assertEqual(int(headers['Content-Length']),len(body))
        return headers,body

    def test_large_packet_roundtrips_and_reduces_transfer(self):
        packet={'bars':[{'features':{'ema50':100.,'formula_version':3,'notes':'retained values '*40}} for _ in range(1000)]}
        headers,body=self.reply(packet,'br, gzip;q=0.8')
        self.assertEqual(headers['Content-Encoding'],'gzip')
        self.assertEqual(headers['Vary'],'Accept-Encoding')
        self.assertEqual(json.loads(gzip.decompress(body)),packet)
        self.assertLess(len(body),len(json.dumps(packet).encode())/10)

    def test_disabled_or_missing_gzip_and_small_live_packets_are_plain(self):
        packet={'large':'test '*10000}
        for encoding in ('','br','gzip;q=0','gzip; q=0.0','gzip;q=invalid'):
            headers,body=self.reply(packet,encoding)
            self.assertNotIn('Content-Encoding',headers)
            self.assertEqual(json.loads(body),packet)
        headers,body=self.reply({'live':None},'gzip')
        self.assertNotIn('Content-Encoding',headers)
        self.assertTrue(_accepts_gzip({'Accept-Encoding':'GZIP; q=1'}))
