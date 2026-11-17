"""No upload bytes or sessions before current consent; receipt expires with intake."""
import http.client
import json
import unittest
from pathlib import Path
import sys
sys.path[:0]=[str(Path(__file__).resolve().parents[1]/'apps/workbench')]
from test_intake import IntakeHTTPTests, recording
from upload_policy import VERSION
from temporary_uploads import TemporaryUploads


class UploadConsentTests(unittest.TestCase):
    setUpClass=classmethod(IntakeHTTPTests.setUpClass.__func__)
    tearDownClass=classmethod(IntakeHTTPTests.tearDownClass.__func__)

    def request(self, headers, data=None):
        conn=http.client.HTTPConnection('127.0.0.1',self.server.server_port,timeout=5)
        self.addCleanup(conn.close)
        conn.putrequest('POST','/api/v1/intakes')
        for key,value in {'Content-Type':'application/octet-stream','X-Filename':'public.edf',
                          'Content-Length':str(len(data) if data else 1000000000),**headers}.items():
            conn.putheader(key,value)
        conn.endheaders()
        if data:conn.send(data)
        reply=conn.getresponse();return reply.status,json.loads(reply.read())

    def test_missing_stale_or_false_consent_rejected_without_reading_body(self):
        before=set(self.server.store.intakes.root.iterdir())
        for headers in ({},{'X-QC-Privacy-Consent':'agree','X-QC-Privacy-Version':'old'},
                        {'X-QC-Privacy-Consent':'false','X-QC-Privacy-Version':VERSION}):
            code,result=self.request(headers)
            self.assertEqual(code,403);self.assertEqual(result['code'],'privacy_consent_required')
        self.assertEqual(before,set(self.server.store.intakes.root.iterdir()))

    def test_rejection_does_not_create_private_session(self):
        from server import Store
        self.server.temporary=TemporaryUploads(self.server.store,Store)
        try:
            self.assertEqual(self.request({})[0],403)
            self.assertFalse(self.server.temporary.sessions)
        finally:
            self.server.temporary.shutdown();self.server.temporary=None

    def test_current_receipt_saved_with_intake_and_policy_readable(self):
        code,value=self.request({'X-QC-Privacy-Consent':'agree','X-QC-Privacy-Version':VERSION},recording())
        self.assertEqual(code,201)
        saved=self.server.store.intakes.get(value['id'])['upload_consent']
        self.assertEqual(saved['version'],VERSION);self.assertIn('accepted_at',saved)
        self.assertEqual(set(saved),{'version','accepted_at'})
        with self.opener.open(self.url+'/api/v1/upload-policy') as response:
            self.assertEqual(json.load(response)['version'],VERSION)
        with self.opener.open(self.url+'/privacy') as response:
            text=response.read().decode()
            self.assertIn('隐私与数据处理协议',text)
            self.assertIn('仅在上传它的浏览器',text)


if __name__=='__main__':unittest.main()
