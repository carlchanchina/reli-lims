from collections import defaultdict

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime

from reli_lims.validation import field_values, require_role, validate_transition


ITEM_TRANSITIONS = {'Pending': ('Ready',), 'Ready': ('Running',),
                    'Running': ('Completed',), 'Completed': ('Reviewed',), 'Reviewed': ()}
LOCKED_STATES = ('Running', 'Completed', 'Reviewed')
BASIS_FIELDS = ('item_code', 'test_method', 'standard', 'engineer', 'asset', 'workstation', 'test_condition')


class TestProgram(Document):
    def validate(self):
        previous = self.get_doc_before_save()
        self.customer = frappe.db.get_value('Project', self.project, 'customer')
        if previous and frappe.db.exists('Test Report', {'test_program': self.name, 'status': ('in', ['Issued', 'Revised'])}):
            if field_values(self) != field_values(previous):
                frappe.throw(_('A program with an issued report cannot be changed.'))
        if not self.samples or not self.items:
            frappe.throw(_('A program needs at least one sample and one test item.'))
        samples = [row.sample for row in self.samples]
        if len(samples) != len(set(samples)):
            frappe.throw(_('Each sample may appear only once in the program.'))
        for sample in samples:
            if frappe.db.get_value('Sample', sample, 'project') != self.project:
                frappe.throw(_('Every sample must belong to the program Project.'))
        items = {row.item_code: row for row in self.items}
        if len(items) != len(self.items) or not all(items):
            frappe.throw(_('Test item codes must be nonempty and unique in the program.'))
        assignments = defaultdict(set)
        for row in self.sample_assignments:
            if row.item_code not in items or row.sample not in samples:
                frappe.throw(_('Sample assignments must reference items and samples in this program.'))
            if row.sample in assignments[row.item_code]:
                frappe.throw(_('Duplicate item/sample assignment.'))
            assignments[row.item_code].add(row.sample)
        old_items = {row.name: row for row in previous.items} if previous else {}
        old_assignments = defaultdict(set)
        if previous:
            for row in previous.sample_assignments:
                old_assignments[row.item_code].add(row.sample)
            new_names = {row.name for row in self.items}
            if any(row.status in LOCKED_STATES and row.name not in new_names for row in previous.items):
                frappe.throw(_('An item that has started cannot be removed.'))
            if previous.project != self.project and any(row.status in LOCKED_STATES for row in previous.items):
                frappe.throw(_('The Project cannot change after execution starts.'))
        for row in self.items:
            if not row.standard or not row.test_method or not assignments[row.item_code]:
                frappe.throw(_('Every item needs a method, one standard and at least one sample.'))
            old = old_items.get(row.name)
            if old and old.item_code != row.item_code:
                frappe.throw(_('An existing test item code cannot change.'))
            validate_transition(old.status if old else 'Pending', row.status, ITEM_TRANSITIONS)
            if old and old.status in LOCKED_STATES:
                if any(row.get(key) != old.get(key) for key in BASIS_FIELDS) or assignments[row.item_code] != old_assignments[old.item_code]:
                    frappe.throw(_('The execution basis and applicable samples are locked once running.'))
            if old and old.status == 'Reviewed' and field_values(row) != field_values(old):
                frappe.throw(_('A reviewed item cannot be changed.'))
            if row.status != 'Pending' and not row.engineer:
                frappe.throw(_('Assign an engineer before making an item Ready.'))
            if row.status in ('Completed', 'Reviewed') and (not (row.result or '').strip() or not (row.conclusion or '').strip()):
                frappe.throw(_('Completed items require both result and conclusion.'))
            if row.status == 'Reviewed' and (not old or old.status != 'Reviewed'):
                require_role('Lab Reviewer', 'Lab Manager')
            row.actual_start = old.actual_start if old else None
            row.actual_end = old.actual_end if old else None
            if row.status == 'Running' and (not old or old.status != 'Running'):
                row.actual_start = now_datetime()
            if row.status == 'Completed' and old.status == 'Running':
                row.actual_end = now_datetime()
        if self.status == 'Cancelled':
            require_role('Lab Manager')
            if previous and field_values(self, ('status',)) != field_values(previous, ('status',)):
                frappe.throw(_('Cancel the program without changing its content.'))
        elif previous and previous.status == 'Cancelled':
            frappe.throw(_('A cancelled program cannot be reopened.'))
        elif all(row.status in ('Completed', 'Reviewed') for row in self.items):
            self.status = 'Completed'
        elif any(row.status in LOCKED_STATES for row in self.items):
            self.status = 'Running'
        else:
            if self.status not in ('Draft', 'Approved'):
                frappe.throw(_('An unstarted program must be Draft or Approved.'))
            if self.status == 'Approved' and (not previous or previous.status != 'Approved'):
                require_role('Lab Manager')
