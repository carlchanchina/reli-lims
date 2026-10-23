import json

import frappe
from frappe import _
from frappe.model.document import Document


class CapabilitySource(Document):
    def validate(self):
        if self.issue_date and self.expiry_date and self.expiry_date < self.issue_date:
            frappe.throw(_("有效期不能早于签发日期。"))

        if self.documents_review_status != "Approved":
            frappe.throw(_("仅允许导入 wekona_documents 中已审核通过的结构化文档。"))

        try:
            payload = json.loads(self.structured_json) if isinstance(self.structured_json, str) else self.structured_json
        except (TypeError, ValueError):
            frappe.throw(_("审核后结构化结果必须是有效 JSON。"))

        if not isinstance(payload, dict):
            frappe.throw(_("审核后结构化结果必须是对象，并包含 items 能力数组。"))

        items = payload.get("items")
        if not isinstance(items, list) or not items:
            frappe.throw(_("审核后结构化结果必须包含非空 items 能力数组。"))

        for index, item in enumerate(items, start=1):
            if not isinstance(item, dict):
                frappe.throw(_("第 {0} 条能力必须是对象。", [index]))
            if not (item.get("test_method") or item.get("test_method_name")):
                frappe.throw(_("第 {0} 条能力缺少检测项目。", [index]))
            if not (item.get("standard_code") or item.get("test_standard")):
                frappe.throw(_("第 {0} 条能力缺少检测标准。", [index]))
