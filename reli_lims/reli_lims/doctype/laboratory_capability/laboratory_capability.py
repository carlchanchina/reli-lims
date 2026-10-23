import frappe
from frappe import _
from frappe.model.document import Document


class LaboratoryCapability(Document):
    def validate(self):
        if self.source:
            source = frappe.get_doc("Capability Source", self.source)
            if source.laboratory != self.laboratory:
                frappe.throw(_("能力来源与实验室不一致。"))
            if source.documents_review_status != "Approved":
                frappe.throw(_("只有 Documents 已审核通过的来源才能生成实验室能力。"))

        if self.status == "已发布":
            self.published = 1
        elif self.status in {"待确认", "已确认", "已停用"}:
            self.published = 0

        if self.published and self.status != "已发布":
            frappe.throw(_("发布标记与能力状态不一致。"))

    def on_trash(self):
        if self.status == "已发布":
            frappe.throw(_("已发布能力不能直接删除，请先取消发布或停用。"))
