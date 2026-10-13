from frappe.model.document import Document


class TestStandard(Document):
    def validate(self):
        self.full_name = f"{self.standard_code}:{self.version} — {self.title}"
