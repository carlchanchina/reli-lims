"""Idempotent native Desk configuration and compatible V1 report migration."""
import json
import frappe
from reli_lims.progress import STAGES, refresh_all

CARD_STAGES = [('待确认委托', '待确认'), ('待收样', '待收样'), ('待试验', '待试验'),
               ('试验中', '试验中'), ('待报告', '待报告'), ('报告待审核', '报告审核'),
               ('超期', None)]
PERSONAL_STAGES = [('我的待试验', '待试验'), ('我的进行中', '试验中'), ('我的待报告', '待报告')]


def after_migrate():
    for old, new in [('Engineering Complete', 'Review'), ('Revised', 'Issued')]:
        for name in frappe.get_all('Test Report', filters={'status': old}, pluck='name'):
            report = frappe.get_doc('Test Report', name)
            report.add_comment('Info', f'V1 状态兼容迁移：{old} → {new}；保留原报告版本与附件。')
            frappe.db.set_value('Test Report', name, 'status', new, update_modified=False)
    refresh_all()
    for label, stage in CARD_STAGES:
        _request_card(label, stage)
    for label, stage in PERSONAL_STAGES:
        _request_card(label, stage, personal=True)
    board = dict(kanban_board_name='检测主流程', reference_doctype='Test Request',
        field_name='business_stage', private=0, is_standard='No', module='Reli LIMS',
        filters=json.dumps([['Test Request', 'docstatus', '!=', 2]]),
        fields=json.dumps(['name', 'customer', 'sample_summary', 'test_summary', 'responsible_engineer', 'delivery_date']),
        columns=[dict(column_name=stage, status='Active', indicator='Green' if stage == '已完成' else 'Blue', order='[]') for stage in STAGES])
    if frappe.get_meta('Kanban Board').has_field('use_kanban_v2'):
        board.update(use_kanban_v2=1, title_field='name', show_assigned_to=1,
            card_fields=[dict(fieldname=name, label=label) for name, label in [
                ('customer', '客户'), ('sample_summary', '样品'), ('test_summary', '检测项目'),
                ('responsible_engineer', '负责人'), ('delivery_date', '要求完成日期'), ('overdue_status', '超期标识')]])
    _upsert('Kanban Board', '检测主流程', board)
    sync_optional_sidebar()


def _request_card(label, stage, personal=False):
    """Idempotent Test Request number card; personal cards scope to the session user."""
    name = 'Reli LIMS ' + label
    filters = [['Test Request', 'docstatus', '!=', 2]]
    dynamic = []
    if personal:
        dynamic.append(['Test Request', 'responsible_engineer', '=', 'frappe.session.user'])
    if stage:
        filters.append(['Test Request', 'business_stage', '=', stage])
    else:
        filters.append(['Test Request', 'business_stage', '!=', '已完成'])
        dynamic.append(['Test Request', 'delivery_date', '<', 'frappe.datetime.get_today()'])
    values = dict(label=label, type='Document Type', document_type='Test Request',
        function='Count', is_public=1, is_standard=0, module='Reli LIMS',
        show_percentage_stats=0, filters_json=json.dumps(filters, ensure_ascii=False),
        dynamic_filters_json=json.dumps(dynamic),
        color='#cf4444' if stage is None else '#268575')
    _upsert('Number Card', name, values)


def _upsert(doctype, name, values):
    if frappe.db.exists(doctype, name):
        doc = frappe.get_doc(doctype, name)
        doc.update(values)
        doc.save(ignore_permissions=True)
    else:
        frappe.get_doc(dict(doctype=doctype, name=name, **values)).insert(ignore_permissions=True, set_name=name)


def sync_optional_sidebar():
    """Use native sections, including capability links only when installed."""
    if not frappe.db.exists('DocType', 'Sidebar') or not frappe.db.exists('Sidebar', 'Reli LIMS'):
        return
    sidebar = frappe.get_doc('Sidebar', 'Reli LIMS')
    targets = [('Workspace', 'Laboratory Capability Center', '实验室能力中心'),
               ('DocType', 'Capability Source', '能力来源'),
               ('DocType', 'Laboratory Capability', '实验室检测能力')]
    existing = {(row.link_type, row.link_to) for row in sidebar.items if row.type == 'Link'}
    missing = [(kind, target, label) for kind, target, label in targets
               if frappe.db.exists(kind, target) and (kind, target) not in existing]
    if not missing:
        return
    if not any(row.type == 'Section Break' and row.label == '实验室能力' for row in sidebar.items):
        sidebar.append('items', dict(type='Section Break', label='实验室能力',
                                     collapsible=1, keep_closed=1, indent=1))
    for kind, target, label in missing:
        sidebar.append('items', dict(type='Link', label=label, link_type=kind,
                                     link_to=target, child=1))
    sidebar.save(ignore_permissions=True)
