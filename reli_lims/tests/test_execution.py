import uuid
from io import BytesIO

from pypdf import PdfWriter

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import today


class TestExecution(IntegrationTestCase):
    def setUp(self):
        super().setUp()
        for dt in ('Test Program', 'Test Report'):
            self.assertTrue(frappe.db.exists('DocType', dt), f'{dt} is not installed')
        token = uuid.uuid4().hex[:10]
        company = frappe.get_doc(doctype='Company', company_name=f'Execution {token}', abbr=f'E{token}',
                                 default_currency='USD', country='United States', chart_of_accounts='Standard').insert()
        self.project = frappe.get_doc(doctype='Project', project_name=f'Execution {token}', company=company.name).insert()
        self.samples = [frappe.get_doc(doctype='Sample', project=self.project.name, received_date=today(), quantity=1).insert() for _ in range(2)]
        self.methods = [frappe.get_doc(doctype='Test Method', method_name=f'{name} {token}').insert() for name in ('Low Temperature', 'High Temperature', 'Vibration')]
        self.standards = [frappe.get_doc(doctype='Test Standard', standard_code=f'{code}-{token}', title=code, version='2026', status='Active').insert() for code in ('A', 'B', 'C')]

    def program(self):
        return frappe.get_doc(dict(doctype='Test Program', project=self.project.name,
            samples=[dict(sample=s.name) for s in self.samples],
            items=[dict(item_code=f'T{i+1}', test_method=m.name, standard=s.name, engineer='Administrator')
                   for i,(m,s) in enumerate(zip(self.methods,self.standards))],
            sample_assignments=[dict(item_code=f'T{i+1}', sample=s.name) for i in range(3) for s in self.samples]))

    def test_acceptance_path_two_samples_three_items_and_issue(self):
        program = self.program().insert()
        fixed_account = frappe.db.get_value('Account', {'company': self.project.company,
                                                        'account_type': 'Fixed Asset', 'is_group': 0}, 'name')
        category = frappe.get_doc(doctype='Asset Category', asset_category_name=uuid.uuid4().hex,
                                   non_depreciable_category=1, accounts=[dict(company_name=self.project.company,
                                                                              fixed_asset_account=fixed_account)]).insert()
        location = frappe.get_doc(doctype='Location', location_name=uuid.uuid4().hex).insert()
        equipment_item = frappe.get_doc(doctype='Item', item_code=uuid.uuid4().hex, item_name='Test Chamber',
                                         item_group='All Item Groups', stock_uom='Nos', is_stock_item=0,
                                         is_fixed_asset=1, asset_category=category.name).insert()
        equipment = frappe.get_doc(doctype='Asset', asset_name='Test Chamber', item_code=equipment_item.name,
                                   company=self.project.company, asset_category=category.name,
                                   asset_type='Existing Asset', asset_owner='Company', asset_quantity=1,
                                   purchase_date=today(), available_for_use_date=today(), location=location.name,
                                   net_purchase_amount=1000, purchase_amount=1000, calculate_depreciation=0).insert()
        raw = frappe.get_doc(doctype='File', file_name=f'{uuid.uuid4().hex}.csv', is_private=1,
                             content=b'sample,result\n1,PASS\n2,PASS\n',
                             attached_to_doctype='Test Program', attached_to_name=program.name).insert()
        for item in program.items:
            item.asset=equipment.name
            item.raw_data=raw.file_url
        for state in ('Ready','Running','Completed','Reviewed'):
            for item in program.items:
                item.status = state
                if state == 'Completed':
                    item.result = 'PASS'
                    item.conclusion = 'Meets the selected standard.'
            program.save()
        report = frappe.get_doc(doctype='Test Report', project=self.project.name, test_program=program.name,
                                overall_conclusion='PASS', reviewer='Administrator', approver='Administrator',
                                pdf_file='/private/files/test-report.pdf').insert()
        pdf = BytesIO()
        writer = PdfWriter()
        writer.add_blank_page(width=200, height=200)
        writer.write(pdf)
        file = frappe.get_doc(doctype='File', file_name=f'test-report-{uuid.uuid4().hex}.pdf', is_private=1,
                              content=pdf.getvalue(),
                              attached_to_doctype='Test Report', attached_to_name=report.name).insert()
        report.pdf_file = file.file_url
        for state in ('Engineering Complete','Review','Approved','Issued'):
            report.status = state
            report.save()
        self.assertTrue(all(item.asset == equipment.name and item.engineer == 'Administrator' and item.raw_data for item in program.items))
        self.assertEqual(report.status, 'Issued')
        self.assertTrue(report.issued_date)
        self.assertTrue(all(i.actual_start and i.actual_end for i in program.items))
        report.overall_conclusion = 'FAIL'
        with self.assertRaises(frappe.ValidationError):
            report.save()

    def test_program_rejects_samples_from_another_project(self):
        other = frappe.get_doc(doctype='Project',project_name=uuid.uuid4().hex, company=self.project.company).insert()
        self.samples[0].project=other.name
        self.samples[0].save()
        with self.assertRaises(frappe.ValidationError):
            self.program().insert()

    def test_assignment_requires_membership_and_valid_item(self):
        for change in ('sample','item_code'):
            program=self.program()
            program.sample_assignments[0].set(change, 'missing')
            with self.assertRaises(frappe.ValidationError):
                program.insert()

    def test_each_item_requires_one_standard_and_sample(self):
        program=self.program()
        program.items[0].standard=None
        with self.assertRaises(frappe.ValidationError):
            program.insert()
        program=self.program()
        program.sample_assignments=[r for r in program.sample_assignments if r.item_code!='T1']
        with self.assertRaises(frappe.ValidationError):
            program.insert()

    def test_cannot_skip_execution_states_or_complete_without_result(self):
        program=self.program().insert()
        program.items[0].status='Reviewed'
        with self.assertRaises(frappe.ValidationError):
            program.save()
        program.reload()
        program.items[0].status='Ready'
        program.save()
        program.items[0].status='Running'
        program.save()
        program.items[0].status='Completed'
        with self.assertRaises(frappe.ValidationError):
            program.save()

    def test_execution_basis_is_locked_once_running(self):
        program=self.program().insert()
        program.items[0].status='Ready'
        program.save()
        program.items[0].status='Running'
        program.save()
        program.items[0].standard=self.standards[1].name
        with self.assertRaises(frappe.ValidationError):
            program.save()

    def test_report_blocks_unreviewed_program_and_wrong_project(self):
        program=self.program().insert()
        report=frappe.get_doc(doctype='Test Report',project=self.project.name,test_program=program.name,
                             overall_conclusion='PASS',reviewer='Administrator',approver='Administrator',pdf_file='/private/files/test-report.pdf').insert()
        report.status='Engineering Complete'
        with self.assertRaises(frappe.ValidationError):
            report.save()
        other=frappe.get_doc(doctype='Project',project_name=uuid.uuid4().hex,company=self.project.company).insert()
        report.project=other.name
        report.status='Draft'
        with self.assertRaises(frappe.ValidationError):
            report.save()

    def test_sample_project_cannot_change_after_program_assignment(self):
        self.program().insert()
        other=frappe.get_doc(doctype='Project',project_name=uuid.uuid4().hex,company=self.project.company).insert()
        self.samples[0].project=other.name
        with self.assertRaises(frappe.ValidationError):
            self.samples[0].save()

    def test_reviewed_result_is_locked(self):
        program=self.program().insert()
        for state in ('Ready','Running','Completed','Reviewed'):
            program.items[0].status=state
            if state=='Completed':
                program.items[0].result='PASS'
                program.items[0].conclusion='Meets requirements'
            program.save()
        program.items[0].result='FAIL'
        with self.assertRaises(frappe.ValidationError):
            program.save()

    def test_engineer_cannot_review_even_when_doc_permission_is_bypassed(self):
        program=self.program().insert()
        for state in ('Ready','Running','Completed'):
            program.items[0].status=state
            if state=='Completed':
                program.items[0].result='PASS'
                program.items[0].conclusion='Meets requirements'
            program.save()
        user=frappe.get_doc(doctype='User',email=f'{uuid.uuid4().hex}@example.test',first_name='Engineer',
                            send_welcome_email=0,roles=[dict(role='Lab Engineer')]).insert()
        frappe.set_user(user.name)
        try:
            program.items[0].status='Reviewed'
            with self.assertRaises(frappe.PermissionError):
                program.save(ignore_permissions=True)
        finally:
            frappe.set_user('Administrator')

    def approved_report(self):
        program=self.program().insert()
        for state in ('Ready','Running','Completed','Reviewed'):
            for item in program.items:
                item.status=state
                if state=='Completed':
                    item.result='PASS'
                    item.conclusion='Meets requirements'
            program.save()
        report=frappe.get_doc(doctype='Test Report',project=self.project.name,test_program=program.name,
                             overall_conclusion='PASS',reviewer='Administrator').insert()
        pdf=BytesIO()
        writer=PdfWriter()
        writer.add_blank_page(width=200,height=200)
        writer.write(pdf)
        attachment=frappe.get_doc(doctype='File',file_name=f'{uuid.uuid4().hex}.pdf',is_private=1,
                                  content=pdf.getvalue(),attached_to_doctype='Test Report',attached_to_name=report.name).insert()
        report.pdf_file=attachment.file_url
        for state in ('Engineering Complete','Review','Approved'):
            report.status=state
            report.save()
        return program,report

    def test_engineer_cannot_rewrite_approved_report(self):
        _,report=self.approved_report()
        engineer=frappe.get_doc(doctype='User',email=f'{uuid.uuid4().hex}@example.test',first_name='Engineer',
                                send_welcome_email=0,roles=[dict(role='Lab Engineer')]).insert()
        frappe.set_user(engineer.name)
        try:
            report.overall_conclusion='FAIL'
            with self.assertRaises(frappe.ValidationError):
                report.save()
        finally:
            frappe.set_user('Administrator')

    def test_issued_report_cannot_be_deleted_and_program_stays_locked(self):
        program,report=self.approved_report()
        report.status='Issued'
        report.save()
        with self.assertRaises(frappe.ValidationError):
            frappe.delete_doc('Test Report',report.name)
        self.assertTrue(frappe.db.exists('Test Report',report.name))
        program.title='Changed after issue'
        with self.assertRaises(frappe.ValidationError):
            program.save()

    def test_cancellation_cannot_change_items_or_assignments(self):
        for change in ('remove','add','assignment'):
            program=self.program().insert()
            program.status='Cancelled'
            if change=='remove':
                program.items.pop(0)
                program.sample_assignments=[row for row in program.sample_assignments if row.item_code!='T1']
            elif change=='add':
                program.append('items',dict(item_code='T4',test_method=self.methods[0].name,standard=self.standards[0].name,
                                            engineer='Administrator',status='Pending'))
                program.append('sample_assignments',dict(item_code='T4',sample=self.samples[0].name))
            else:
                program.sample_assignments.pop(0)
            with self.assertRaises(frappe.ValidationError):
                program.save()
