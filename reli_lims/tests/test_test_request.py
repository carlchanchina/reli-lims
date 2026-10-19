"""Database-writing acceptance tests: run on a disposable site only."""
import uuid

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, today

from reli_lims.services.test_request import make_test_program, receive_samples


class TestTestingRequest(IntegrationTestCase):
    def setUp(self):
        super().setUp()
        token = uuid.uuid4().hex[:8]
        self.company = frappe.get_doc(dict(doctype='Company', company_name=f'Intake {token}',
            abbr=f'I{token}', default_currency='USD', country='United States',
            chart_of_accounts='Standard')).insert()
        self.customer = frappe.get_doc(dict(doctype='Customer',customer_name=f'Intake {token}',
            customer_type='Company',customer_group='All Customer Groups',territory='All Territories')).insert()
        self.method = frappe.get_doc(dict(doctype='Test Method',method_name=f'Intake {token}')).insert()
        self.standard = frappe.get_doc(dict(doctype='Test Standard',standard_code=f'I-{token}',
            title='Intake standard',version='1',status='Active')).insert()

    def request(self):
        return frappe.get_doc(dict(doctype='Test Request',title='DEMO intake',
            customer=self.customer.name,company=self.company.name,request_date=today(),
            delivery_date=add_days(today(),7),report_copies=1,
            samples=[dict(sample_code=code,product_name='Device '+code,model='A',
                          quantity=1,dimensions='100 x 200 mm') for code in ('S1','S2')],
            items=[dict(item_code='LT',test_method=self.method.name,standard=self.standard.name)],
            sample_assignments=[dict(item_code='LT',sample_code=code) for code in ('S1','S2')])).insert()

    def receipts(self):
        return [dict(sample_code=code,quantity=1,received_date=today(),received_by='Administrator')
                for code in ('S1','S2')]

    def image_file(self, request, private=1):
        from io import BytesIO
        from PIL import Image
        buffer = BytesIO()
        Image.new('RGB', (2, 2), color='white').save(buffer, format='PNG')
        return frappe.get_doc(dict(doctype='File', file_name='sample.png', is_private=private,
            content=buffer.getvalue(), attached_to_doctype='Test Request',
            attached_to_name=request.name)).insert()

    def test_confirmation_receipt_and_program_are_idempotent(self):
        request=self.request()
        self.assertFalse(request.project)
        request.submit()
        self.assertTrue(request.project)
        self.assertEqual(frappe.db.get_value('Project',request.project,'customer'),self.customer.name)
        self.assertFalse(frappe.db.exists('Sample',{'test_request':request.name}))
        samples=receive_samples(request.name,self.receipts())
        self.assertEqual(samples,receive_samples(request.name,self.receipts()))
        program=make_test_program(request.name)
        self.assertEqual(program,make_test_program(request.name))
        doc=frappe.get_doc('Test Program',program)
        self.assertEqual({r.sample for r in doc.samples},set(samples))
        self.assertEqual(len(doc.sample_assignments),2)
        self.assertEqual(doc.items[0].status,'Pending')
        self.assertEqual(str(doc.planned_end),str(request.delivery_date))

    def test_receipt_requires_confirmation_and_all_samples_before_program(self):
        request=self.request()
        with self.assertRaises(frappe.ValidationError):
            receive_samples(request.name,self.receipts())
        request.submit()
        receive_samples(request.name,self.receipts()[:1])
        with self.assertRaisesRegex(frappe.ValidationError,'S2'):
            make_test_program(request.name)

    def test_private_photo_must_belong_to_request(self):
        request=self.request()
        photo = self.image_file(request, private=0)
        request.append('photos',dict(sample_code='S1',photo=photo.file_url))
        with self.assertRaises(frappe.ValidationError):
            request.save()

    def test_confirmation_fields_cannot_be_forged(self):
        request=self.request()
        request.project='forged'
        with self.assertRaises(frappe.ValidationError):
            request.save()

    def test_received_sample_source_cannot_be_reassigned(self):
        request=self.request().submit()
        name=receive_samples(request.name,self.receipts())[0]
        sample=frappe.get_doc('Sample',name)
        sample.test_request=None
        sample.request_sample_row=None
        with self.assertRaises(frappe.ValidationError):
            sample.save()

    def test_confirmed_fields_and_receipt_state_are_protected(self):
        request = self.request().submit()
        request.confirmed_by = 'Guest'
        with self.assertRaises(frappe.ValidationError):
            request.save()
        request.reload()
        names = receive_samples(request.name, self.receipts())
        sample = frappe.get_doc('Sample', names[0])
        sample.status = 'Testing'
        sample.save()
        self.assertEqual(names, receive_samples(request.name, self.receipts()))

    def test_private_photo_is_copied_to_received_sample(self):
        request = self.request()
        image = self.image_file(request)
        request.append('photos', dict(sample_code='S1', photo=image.file_url))
        request.save().submit()
        name = receive_samples(request.name, self.receipts()[:1])[0]
        self.assertTrue(frappe.db.exists('File', dict(file_url=image.file_url, is_private=1,
            attached_to_doctype='Sample', attached_to_name=name)))
        self.assertTrue(frappe.db.exists('File',image.name))

    def test_cross_request_photo_is_rejected(self):
        first = self.request()
        other = self.request()
        photo = self.image_file(other)
        first.append('photos',dict(sample_code='S1',photo=photo.file_url))
        with self.assertRaises(frappe.ValidationError):
            first.save()

    def test_project_failure_rolls_back_confirmation(self):
        from unittest.mock import patch
        request = self.request()
        frappe.db.savepoint('request_confirm_failure')
        try:
            with patch('erpnext.projects.doctype.project.project.Project.after_insert',
                       create=True, side_effect=frappe.ValidationError('forced project failure')):
                with self.assertRaises(frappe.ValidationError):
                    request.submit()
        finally:
            frappe.db.rollback(save_point='request_confirm_failure')
        self.assertEqual(frappe.db.get_value('Test Request',request.name,'docstatus'),0)
        self.assertFalse(frappe.db.exists('Project',{'project_name':f'{request.name} - {request.title}'}))

    def test_partial_receipt_failure_rolls_back_batch(self):
        from unittest.mock import patch
        request = self.request().submit()
        frappe.db.savepoint('request_receipt_failure')
        try:
            with patch('reli_lims.services.test_request.copy_sample_photos',
                       side_effect=[None,frappe.ValidationError('forced photo failure')]):
                with self.assertRaises(frappe.ValidationError):
                    receive_samples(request.name,self.receipts())
        finally:
            frappe.db.rollback(save_point='request_receipt_failure')
        self.assertFalse(frappe.db.exists('Sample',{'test_request':request.name}))

    def test_engineer_cannot_confirm(self):
        request = self.request()
        user = frappe.get_doc(dict(doctype='User',email=f'intake-{uuid.uuid4().hex}@example.test',
            first_name='Intake Engineer',send_welcome_email=0,roles=[dict(role='Lab Engineer')])).insert()
        try:
            frappe.set_user(user.name)
            with self.assertRaises(frappe.PermissionError):
                frappe.get_doc('Test Request',request.name).submit()
        finally:
            frappe.set_user('Administrator')
