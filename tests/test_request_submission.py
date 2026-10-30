import sys,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
class SubmissionGuard(unittest.TestCase):
 def test_confirmation_must_be_current_complete_and_draft(self):
  from reli_lims import request_submission as api
  valid=dict(docstatus=0,customer_confirmation_state='Customer Confirmed',customer_confirmation_fingerprint='a'*64,customer_confirmed_by='customer',customer_confirmed_at='2026-10-30')
  self.assertIsNone(api.confirmation_error(valid,'a'*64,[]))
  for changes in ({'docstatus':1},{'customer_confirmation_state':'Needs Reconfirmation'},{'customer_confirmation_state':'Awaiting Customer Confirmation'},{'customer_confirmation_fingerprint':'b'*64},{'customer_confirmed_by':''}):
   self.assertTrue(api.confirmation_error({**valid,**changes},'a'*64,[]))
  self.assertTrue(api.confirmation_error(valid,'a'*64,['contact_person']))
