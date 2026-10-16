"""Framework-independent validation for the customer-declared testing scope."""
from datetime import date
from math import isfinite


def positive_number(value, label):
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError(f'{label} must be a finite positive number.') from None
    if not isfinite(number) or number <= 0:
        raise ValueError(f'{label} must be a finite positive number.')
    return number


def _codes(rows, field, label):
    codes = []
    for row in rows:
        code = str(row.get(field) or '')
        if not code.strip() or code != code.strip():
            raise ValueError(f'{label} codes must be nonempty without surrounding spaces.')
        codes.append(code)
    if not codes or len(codes) != len(set(codes)):
        raise ValueError(f'{label} codes must be present and unique.')
    return set(codes)


def validate_scope(data):
    samples = data.get('samples') or []
    items = data.get('items') or []
    sample_codes = _codes(samples, 'sample_code', 'Sample')
    item_codes = _codes(items, 'item_code', 'Test item')
    for row in samples:
        if not str(row.get('product_name') or '').strip():
            raise ValueError('Every sample needs a product name.')
        positive_number(row.get('quantity'), 'Sample quantity')
    for row in items:
        if not row.get('test_method') or not row.get('standard'):
            raise ValueError('Every test item needs a method and one standard.')
    pairs = set()
    assigned = set()
    for row in data.get('sample_assignments') or []:
        pair = (row.get('item_code'), row.get('sample_code'))
        if pair[0] not in item_codes or pair[1] not in sample_codes:
            raise ValueError('Assignments must reference this request’s items and samples.')
        if pair in pairs:
            raise ValueError('Duplicate item/sample assignment.')
        pairs.add(pair)
        assigned.add(pair[0])
    if assigned != item_codes:
        raise ValueError('Every test item needs at least one applicable sample.')
    for photo in data.get('photos') or []:
        if photo.get('sample_code') not in sample_codes or not photo.get('photo'):
            raise ValueError('Every photo needs a sample from this request and an image.')
    copies = positive_number(data.get('report_copies'), 'Report copies')
    if not copies.is_integer():
        raise ValueError('Report copies must be a positive integer.')
    try:
        start = date.fromisoformat(str(data.get('request_date')))
        end = date.fromisoformat(str(data.get('delivery_date')))
    except (TypeError, ValueError):
        raise ValueError('Valid request and delivery dates are required.') from None
    if end < start:
        raise ValueError('Delivery date cannot precede the request date.')


def receipt_data(row, receipt):
    quantity = positive_number(receipt.get('quantity'), 'Received quantity')
    try:
        received = date.fromisoformat(str(receipt.get('received_date')))
    except (TypeError, ValueError):
        raise ValueError('A valid received date is required.') from None
    if not receipt.get('received_by'):
        raise ValueError('A receiver is required.')
    reason = str(receipt.get('difference_reason') or '').strip()
    if quantity != float(row['quantity']) and not reason:
        raise ValueError('Explain the difference between requested and received quantities.')
    return dict(product_name=row['product_name'], model=row.get('model'),
                dimensions=row.get('dimensions'), quantity=quantity,
                received_date=received.isoformat(), received_by=receipt['received_by'],
                condition=receipt.get('condition') or '', status='Received',
                notes='\n'.join(x for x in (row.get('notes'), reason) if x))


def program_data(request, sample_names):
    missing = [r['sample_code'] for r in request['samples'] if r['sample_code'] not in sample_names]
    if missing:
        raise ValueError('Receive these samples first: ' + ', '.join(missing))
    return dict(doctype='Test Program', project=request['project'], test_request=request['name'],
                title=request['title'], status='Draft', planned_end=request['delivery_date'],
                samples=[dict(sample=sample_names[r['sample_code']], sample_label=r['sample_code'])
                         for r in request['samples']],
                items=[dict(item_code=r['item_code'], test_method=r['test_method'],
                            standard=r['standard'], test_condition=r.get('test_condition'), status='Pending')
                       for r in request['items']],
                sample_assignments=[dict(item_code=r['item_code'], sample=sample_names[r['sample_code']])
                                    for r in request['sample_assignments']])


def same_receipt(stored, values):
    """Workflow progress is not part of the original receiving facts."""
    return float(stored.get('quantity') or 0) == values['quantity'] and all(
        str(stored.get(key) or '') == str(value or '')
        for key, value in values.items() if key not in ('quantity', 'status'))
