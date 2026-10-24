"""Extend native ERPNext Project connections without replacing its dashboard."""
from copy import deepcopy

from frappe import _

LAB_DOCUMENTS = ('Test Request', 'Sample', 'Test Program', 'Test Report')


def get_data(data):
    result = deepcopy(data)
    groups = result.setdefault('transactions', [])
    existing = {item for group in groups for item in group.get('items', [])}
    missing = [doctype for doctype in LAB_DOCUMENTS if doctype not in existing]
    if missing:
        groups.append({'label': _('检测业务'), 'items': missing})
    fields = result.setdefault('non_standard_fieldnames', {})
    for doctype in LAB_DOCUMENTS:
        fields[doctype] = 'project'
    return result
