from datetime import date
import unittest
from reli_lims.request_scope import validate_scope, receipt_data


class TestConvergence(unittest.TestCase):
    def test_minimal_request_has_no_invoice_or_report_copies_requirement(self):
        validate_scope(dict(request_date='2026-10-22', delivery_date='2026-10-23',
            samples=[dict(sample_code='S1', product_name='设备', quantity=1)],
            items=[dict(item_code='T1', test_method='M1', standard='A')],
            sample_assignments=[dict(item_code='T1', sample_code='S1')]))

    def test_receipt_keeps_serial_number(self):
        values = receipt_data(dict(product_name='设备', quantity=1, serial_no='SN-1'),
            dict(quantity=1, received_date='2026-10-22', received_by='Administrator'))
        self.assertEqual(values.get('serial_no'), 'SN-1')

    def test_business_stage_follows_all_samples_and_all_programs(self):
        from reli_lims.progress import business_stage
        self.assertEqual(business_stage(0, 2, 0, [], []), '待确认')
        self.assertEqual(business_stage(1, 2, 1, [], []), '待收样')
        self.assertEqual(business_stage(1, 2, 2, [], []), '已收样')
        self.assertEqual(business_stage(1, 2, 2, ['Pending'], []), '待试验')
        self.assertEqual(business_stage(1, 2, 2, ['Reviewed', 'Running'], []), '试验中')
        self.assertEqual(business_stage(1, 2, 2, ['Reviewed'], []), '待报告')
        self.assertEqual(business_stage(1, 2, 2, ['Reviewed'], ['Review']), '报告审核')
        self.assertEqual(business_stage(1, 2, 2, ['Reviewed'], ['Issued']), '已完成')
        self.assertEqual(business_stage(1, 2, 2, ['Pending'], ['Issued']), '待试验')

    def test_overdue_excludes_completed_and_cancelled_requests(self):
        from reli_lims.progress import overdue
        self.assertTrue(overdue('待收样', '2026-10-21', date(2026,10,22)))
        self.assertFalse(overdue('已完成', '2026-10-21', date(2026,10,22)))
        self.assertFalse(overdue('待收样', '2026-10-21', date(2026,10,22), docstatus=2))
