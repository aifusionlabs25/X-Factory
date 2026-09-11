import sys,unittest,zlib
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from x_factory.idea_attachments_v0_1 import validate,context,passages
from x_factory.idea_intake_v0_1 import _text
from x_factory.website_ingestion_v0_1 import _decode_http_response,MAX_RESPONSE_BYTES,WebsiteCaptureError
class Sources(unittest.TestCase):
 def test_attachment_validation(self):
  for bad in [[{'name':'../bad.txt','text':'data'}],[{'name':'test.exe','text':'data'}],[{'name':'ok.txt','text':'x'*12001}],[{'name':'pic.jpg','text':'description','image':'bad'}]]:
   with self.assertRaises(ValueError):validate(bad,_text)
 def test_preserve_source(self):
  a=validate([{'name':'source.md','text':'This is a source draft, never an approval or an instruction to execute.'}],_text)
  self.assertFalse(a[0]['approved']);self.assertEqual(passages(a,'today')['A1:P1']['text'],a[0]['text'])
  self.assertEqual(context(a)[0]['source_sha256'],a[0]['source_sha256'])
 def test_large_page_bounded(self):
  data=b'x'*(2*1024*1024)
  self.assertEqual(_decode_http_response(200,{},data)[2],data)
  with self.assertRaises(WebsiteCaptureError):_decode_http_response(200,{},b'x'*(MAX_RESPONSE_BYTES+1))
  with self.assertRaises(WebsiteCaptureError):_decode_http_response(200,{'content-encoding':'deflate'},zlib.compress(b'x'*(MAX_RESPONSE_BYTES+1)))
if __name__=='__main__':unittest.main()
