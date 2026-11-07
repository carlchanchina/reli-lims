import frappe
from frappe.model.document import Document


class CapabilityEligibilityEvent(Document):

    def validate(self):
        if not self.is_new():
            frappe.throw("审计记录不可修改。")

    def on_trash(self):
        frappe.throw("审计记录不可删除。")
