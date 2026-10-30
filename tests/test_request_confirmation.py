import copy,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

class ConfirmationFingerprintTest(unittest.TestCase):
 def setUp(self):
  try:from reli_lims import request_confirmation as api
  except ImportError:self.fail('Native customer confirmation semantics missing')
  self.api=api
  self.doc={'name':'REQ-1','customer':'C','company':'Lab','quotation':'Q','delivery_date':'2026-11-15',
   'samples':[{'sample_code':'S1','product_name':'Sample','quantity':1}],
   'items':[{'item_code':'I1','test_method':'M','standard':'S','test_condition':'-40 C'}],
   'sample_assignments':[{'item_code':'I1','sample_code':'S1'}], 'report_requirements':'PDF'}
 def test_technical_whitelist_changes_require_reconfirmation(self):
  original=self.api.fingerprint(self.doc,[])
  for key,value in [('delivery_date','2026-12-01'),('report_requirements','English'),('customer_declared_conditions','50h')]:
   self.assertNotEqual(original,self.api.fingerprint({**self.doc,key:value},[]))
  for table,field,value in [('samples','quantity',2),('samples','product_name','Other'),('items','test_method','M2'),('items','standard','S2'),('items','test_condition','-50 C'),('sample_assignments','sample_code','S2')]:
   changed=copy.deepcopy(self.doc);changed[table][0][field]=value
   self.assertNotEqual(original,self.api.fingerprint(changed,[]))
  self.assertNotEqual(original,self.api.fingerprint(self.doc,[{'name':'F','file_name':'spec.pdf','content_hash':'abc'}]))
 def test_internal_metadata_does_not_invalidate_confirmation(self):
  original=self.api.fingerprint(self.doc,[])
  changed={**self.doc,'modified':'later','engineering_review_notes':'private','responsible_engineer':'engineer','lab_intake_notes':'administrative','owner':'other','notes':'internal general note'}
  self.assertEqual(original,self.api.fingerprint(changed,[]))
  changed=copy.deepcopy(self.doc);changed['items'][0].update(name='db-row',modified='later',notes='internal only')
  self.assertEqual(original,self.api.fingerprint(changed,[]))
 def test_visible_attachment_cannot_be_rebound_between_requests(self):
  import types
  from unittest.mock import patch
  class Error(Exception):pass
  old=types.SimpleNamespace(attached_to_doctype='Test Request',attached_to_name='REQ-A',file_url='/private/files/a.pdf',get=lambda key:1 if key=='reli_customer_visible' else None)
  file=types.SimpleNamespace(attached_to_doctype='Test Request',attached_to_name='REQ-B',file_url='/private/files/a.pdf',is_private=1,flags={},get=lambda key:1 if key=='reli_customer_visible' else None,get_doc_before_save=lambda:old)
  def throw(message,*args):raise Error(message)
  fake=types.SimpleNamespace(get_meta=lambda dt:types.SimpleNamespace(has_field=lambda key:True),db=types.SimpleNamespace(get_value=lambda *args:0),throw=throw)
  with patch.dict(sys.modules,{'frappe':fake}),self.assertRaises(Error):self.api.validate_file_visibility(file)
 def test_native_request_confirmation_ignores_forged_receipt_fields_on_input_document(self):
  import types
  from unittest.mock import patch
  class Flags(dict):
   __getattr__=dict.get
   __setattr__=dict.__setitem__
  saved=[]
  class Doc:
   name='REQ-A';docstatus=0
   def __init__(self,actor):self.customer_confirmed_by=actor;self.flags=Flags()
   def check_permission(self,*args):pass
   def save(self,*args,**kwargs):saved.append(self.customer_confirmed_by)
  stored=Doc('original-customer');supplied=Doc('forged-customer')
  fake=types.SimpleNamespace(get_doc=lambda *args,**kwargs:stored,throw=lambda msg:(_ for _ in ()).throw(ValueError(msg)))
  with patch.dict(sys.modules,{'frappe':fake,'reli_lims.validation':types.SimpleNamespace(require_role=lambda *r:None)}):self.api.await_customer(supplied)
  self.assertEqual(saved,['original-customer'])
 def test_complete_confirmation_details_have_an_explicit_public_representation(self):
  data={**self.doc,'report_language':'English','report_copies':2,'fixture_required':'Yes','engineering_review_notes':'PRIVATE-NOT-PUBLIC'}
  data['samples']=[{**self.doc['samples'][0],'serial_no':'SERIAL-1','dimensions':'10x20','weight_kg':3}]
  details=self.api.technical_details(data)
  values=[row['value'] for row in details]
  for value in ('English','2','是','SERIAL-1','10x20','3'):self.assertIn(value,values)
  self.assertNotIn('PRIVATE-NOT-PUBLIC',str(details))
  self.assertEqual(set(self.api.TECHNICAL_FIELDS),set(self.api.TECHNICAL_LABELS)|set(self.api.PUBLIC_EDIT_FIELDS))
