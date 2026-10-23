import json

import frappe
from frappe import _
from frappe.model.document import Document


class CapabilitySource(Document):
    def validate(self):
        if self.issue_date and self.expiry_date and self.expiry_date < self.issue_date:
            frappe.throw(_("有效期不能早于签发日期。"))

        if self.parsed_json:
            try:
                payload = json.loads(self.parsed_json) if isinstance(self.parsed_json, str) else self.parsed_json
            except (TypeError, ValueError):
                frappe.throw(_("结构化解析结果必须是有效 JSON。"))

            if not isinstance(payload, list):
                frappe.throw(_("结构化解析结果必须是能力候选数组。"))

            if self.parser_status == "待解析":
                self.parser_status = "已解析"
