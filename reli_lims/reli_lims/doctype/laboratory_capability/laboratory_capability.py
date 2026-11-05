import frappe
from frappe import _
from frappe.model.document import Document


class LaboratoryCapability(Document):
    def validate(self):
        if not self.test_project and self.test_method:
            self.test_project = frappe.db.get_value("Test Method", self.test_method, "test_project")
        if self.test_method and self.test_project:
            method_project = frappe.db.get_value("Test Method", self.test_method, "test_project")
            if method_project and method_project != self.test_project:
                frappe.throw(_("检测项目与兼容方法指向的项目不一致。"))
        if not self.test_object and self.product_scope:
            self.test_object = frappe.db.get_value("Test Object", {"object_name": self.product_scope}, "name")
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
            if previous == "已确认" and self.status == "待确认":
                # 退回补充是审核动作，审核员必须具备。
                required.add("Lab Reviewer")
            if not roles.intersection(required):
                frappe.throw(_("没有权限变更能力状态。"), frappe.PermissionError)
        fields = ("laboratory", "test_project", "test_object", "test_method", "test_standard", "product_scope",
                  "capability_scope", "limitation", "accreditation_type",
                  "certificate_no", "source", "source_row", "evidence", "cnas_scope_key",
                  "industry", "project_parameter", "clause", "scope_effective_date", "condition_schema")
        if old and previous in {"已确认", "已发布"}:
            if any(self.get(key) != old.get(key) for key in fields):
                frappe.throw(_("请先取消发布并退回待确认，再修改能力内容。"))

        if self.source:
            source = frappe.get_doc("Capability Source", self.source)
            if source.laboratory != self.laboratory:
                frappe.throw(_("能力来源与实验室不一致。"))
            if source.documents_review_status != "Approved" and not (
                frappe.local.site == "carl" and self.status == "待确认"
                and source.documents_review_status == "Historical Preview"
            ):
                frappe.throw(_("只有 Documents 已审核通过的来源才能生成实验室能力。"))

        if self.status == "已发布":
            if not self.test_project:
                frappe.throw(_("发布前必须关联统一检测项目。"))
            if not frappe.db.get_value("Test Project", self.test_project, "active"):
                frappe.throw(_("检测项目已停用，不能发布能力。"))
            self.published = 1
        elif self.status in {"待确认", "已确认", "已停用"}:
            self.published = 0

        if self.published and self.status != "已发布":
            frappe.throw(_("发布标记与能力状态不一致。"))

    def on_update(self):
        from reli_lims.capability_catalog import ensure_project_relations
        if self.test_project:
            ensure_project_relations(self.test_project, self.test_standard, self.test_object)

    def on_trash(self):
        if self.status == "已发布":
            frappe.throw(_("已发布能力不能直接删除，请先取消发布或停用。"))
