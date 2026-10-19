import frappe
import re
from frappe.model.document import Document
from frappe import _


class LaboratoryProfile(Document):
    def validate(self):
        if not isinstance(self.mercur_seller_id, str) or not re.fullmatch(r"sel_[A-Za-z0-9_]{1,96}", self.mercur_seller_id):
            frappe.throw(_("A valid Mercur seller ID is required"))
