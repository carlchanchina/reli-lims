import unittest
from reli_lims.request_scope import validate_scope


def scope():
    return dict(samples=[dict(sample_code='S1', product_name='Device', quantity=2)],
                items=[dict(item_code='LT', test_method='M1', standard='A')],
                sample_assignments=[dict(item_code='LT', sample_code='S1')],
                photos=[], report_copies=1, request_date='2026-10-17', delivery_date='2026-10-20')


class TestRequestScope(unittest.TestCase):
    def test_multiple_photos_and_independent_standard(self):
        data = scope()
        data['photos'] = [dict(sample_code='S1', photo='/private/files/one.png'),
                          dict(sample_code='S1', photo='/private/files/two.png')]
        validate_scope(data)

    def test_invalid_quantities(self):
        for value in (0, -1, float('nan'), float('inf'), 'bad'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                data = scope()
                data['samples'][0]['quantity'] = value
                validate_scope(data)

    def test_scope_integrity(self):
        changes = [lambda d: d['samples'].append(dict(d['samples'][0])),
                   lambda d: d['items'][0].update(standard=''),
                   lambda d: d.update(sample_assignments=[]),
                   lambda d: d['sample_assignments'][0].update(sample_code='OTHER'),
                   lambda d: d['photos'].append(dict(sample_code='OTHER', photo='x')),
                   lambda d: d.update(report_copies=1.5),
                   lambda d: d.update(delivery_date='2026-10-16'),
                   lambda d: d['samples'][0].update(product_name='  ')]
        for change in changes:
            with self.subTest(change=change), self.assertRaises(ValueError):
                data = scope()
                change(data)
                validate_scope(data)

    def test_duplicate_assignment_rejected(self):
        data = scope()
        data['sample_assignments'] *= 2
        with self.assertRaises(ValueError):
            validate_scope(data)

class TestRequestGeneration(unittest.TestCase):
    def test_program_mapping_preserves_selected_samples(self):
        from reli_lims.request_scope import program_data
        data = scope()
        data.update(name='REQ-1', title='Request', project='P1', delivery_date='2026-10-20')
        result = program_data(data, {'S1': 'SMP1'})
        self.assertEqual(result['sample_assignments'], [dict(item_code='LT', sample='SMP1')])
        self.assertEqual(result['items'][0]['standard'], 'A')
        self.assertEqual(result['items'][0]['status'], 'Pending')
        self.assertEqual(result['test_request'], 'REQ-1')
        self.assertEqual(result['planned_end'], '2026-10-20')
        with self.assertRaisesRegex(ValueError, 'S1'):
            program_data(data, {})

    def test_receipt_requires_explanation_and_valid_quantity(self):
        from reli_lims.request_scope import receipt_data
        row = scope()['samples'][0]
        with self.assertRaises(ValueError):
            receipt_data(row, dict(quantity=1, received_date='2026-10-17', received_by='user'))
        values = receipt_data(row, dict(quantity=1, received_date='2026-10-17',
                                       received_by='user', difference_reason='One missing'))
        self.assertEqual(values['quantity'], 1)
        self.assertIn('One missing', values['notes'])
        for bad in (float('nan'), 0, -1):
            with self.assertRaises(ValueError):
                receipt_data(row, dict(quantity=bad, received_date='2026-10-17', received_by='user'))

class TestReceiptRetry(unittest.TestCase):
    def test_execution_state_does_not_change_receipt_identity(self):
        from reli_lims.request_scope import same_receipt
        values = dict(quantity=1, received_date='2026-10-17', received_by='user', status='Received')
        stored = dict(values, quantity=1.0, status='Completed')
        self.assertTrue(same_receipt(stored, values))
        self.assertFalse(same_receipt(dict(stored, quantity=2), values))
