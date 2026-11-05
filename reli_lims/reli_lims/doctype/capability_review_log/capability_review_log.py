from frappe.model.document import Document


class CapabilityReviewLog(Document):
    """能力审核记录：只追加，不覆盖；用于逐条追溯审核与发布。"""

    pass
