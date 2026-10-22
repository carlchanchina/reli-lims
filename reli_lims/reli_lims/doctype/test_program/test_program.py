from collections import defaultdict

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime

from reli_lims.request_provenance import validate_program_source
from reli_lims.validation import field_values, require_role, validate_transition


ITEM_TRANSITIONS = {'Pending': ('Ready',), 'Ready': ('Running',),
                    'Running': ('Completed',), 'Completed': ('Reviewed',), 'Reviewed': ()}
LOCKED_STATES = ('Running', 'Completed', 'Reviewed')
BASIS_FIELDS = ('item_code', 'test_method', 'standard', 'engineer', 'asset', 'workstation', 'test_condition')


class TestProgram(Document):
    def validate(self):
        previous = self.get_doc_before_save()
        validate_program_source(self, previous)
        self.customer = frappe.db.get_value('Project', self.project, 'customer')
        if previous and frappe.db.exists('Test Report', {'test_program': self.name, 'status': ('in', ['Issued', 'Revised'])}):
            if field_values(self) != field_values(previous):
                frappe.throw(_('已有签发报告的检测方案不能修改。'))
        if not self.samples or not self.items:
            frappe.throw(_('检测方案至少需要一个样品和一个检测项目。'))
        samples = [row.sample for row in self.samples]
        if len(samples) != len(set(samples)):
            frappe.throw(_('同一样品在方案中只能出现一次。'))
        for sample in samples:
            if frappe.db.get_value('Sample', sample, 'project') != self.project:
                frappe.throw(_('所有样品必须属于检测方案关联的项目。'))
        items = {row.item_code: row for row in self.items}
        if len(items) != len(self.items) or not all(items):
            frappe.throw(_('方案内的检测项目编号不能为空或重复。'))
        assignments = defaultdict(set)
        for row in self.sample_assignments:
            if row.item_code not in items or row.sample not in samples:
                frappe.throw(_('样品分配只能引用本方案内的检测项目和样品。'))
            if row.sample in assignments[row.item_code]:
                frappe.throw(_('同一检测项目与样品不能重复分配。'))
            assignments[row.item_code].add(row.sample)
        old_items = {row.name: row for row in previous.items} if previous else {}
        old_assignments = defaultdict(set)
        if previous:
            for row in previous.sample_assignments:
                old_assignments[row.item_code].add(row.sample)
            new_names = {row.name for row in self.items}
            if any(row.status in LOCKED_STATES and row.name not in new_names for row in previous.items):
                frappe.throw(_('已经开始执行的检测项目不能删除。'))
            if previous.project != self.project and any(row.status in LOCKED_STATES for row in previous.items):
                frappe.throw(_('开始执行后不能更改所属项目。'))
        for row in self.items:
            if not row.standard or not row.test_method or not assignments[row.item_code]:
                frappe.throw(_('每个检测项目必须有检测方法、一个执行标准和至少一个适用样品。'))
            row.applicable_sample_names = '、'.join(sorted(assignments[row.item_code]))
            old = old_items.get(row.name)
            if old and old.item_code != row.item_code:
                frappe.throw(_('已有检测项目编号不能修改。'))
            validate_transition(old.status if old else 'Pending', row.status, ITEM_TRANSITIONS)
            if old and old.status in LOCKED_STATES:
                if any(row.get(key) != old.get(key) for key in BASIS_FIELDS) or assignments[row.item_code] != old_assignments[old.item_code]:
                    frappe.throw(_('开始执行后，检测依据与适用样品将锁定。'))
            if old and old.status == 'Reviewed' and field_values(row) != field_values(old):
                frappe.throw(_('已复核的检测项目不能修改。'))
            if row.status != 'Pending' and not row.engineer:
                frappe.throw(_('将检测项目设为待执行前，请先指定工程师。'))
            if row.status in ('Completed', 'Reviewed') and (not (row.result or '').strip() or not (row.conclusion or '').strip()):
                frappe.throw(_('完成检测项目时必须填写结果和结论。'))
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
                frappe.throw(_('取消检测方案时请勿同时修改内容。'))
        elif previous and previous.status == 'Cancelled':
            frappe.throw(_('已取消的检测方案不能重新打开。'))
        elif all(row.status in ('Completed', 'Reviewed') for row in self.items):
            self.status = 'Completed'
        elif any(row.status in LOCKED_STATES for row in self.items):
            self.status = 'Running'
        else:
            if self.status not in ('Draft', 'Approved'):
                frappe.throw(_('尚未开始的检测方案只能处于草稿或已批准状态。'))
            if self.status == 'Approved' and (not previous or previous.status != 'Approved'):
                require_role('Lab Manager')
