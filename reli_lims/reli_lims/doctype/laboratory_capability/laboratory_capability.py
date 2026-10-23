import frappe
from frappe import _
from frappe.model.document import Document


class LaboratoryCapability(Document):
    def validate(self):
        old = self.get_doc_before_save()
        previous = old.status if old else "待确认"
        allowed = {
            "待确认": {"待确认", "已确认", "已停用"},
            "已确认": {"已确认", "已发布", "待确认", "已停用"},
            "已发布": {"已发布", "已确认", "已停用"},
            "已停用": {"已停用", "待确认"},
        }
        if self.status not in allowed.get(previous, set()):
            frappe.throw(_("请先人工确认能力，再发布。"))
        roles = set(frappe.get_roles())
        if self.status != previous:
            required = {"Lab Manager", "System Manager"}
            if previous == "待确认" and self.status == "已确认":
                required.add("Lab Reviewer")
            if not roles.intersection(required):
                frappe.throw(_("没有权限变更能力状态。"), frappe.PermissionError)
        fields = ("laboratory", "test_method", "test_standard", "product_scope",
                  "capability_scope", "limitation", "accreditation_type",
                  "certificate_no", "source", "source_row", "evidence")
        if old and previous in {"已确认", "已发布"}:
            if any(self.get(key) != old.get(key) for key in fields):
                frappe.throw(_("请先取消发布并退回待确认，再修改能力内容。"))

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
