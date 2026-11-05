"""Permission-aware execution records and immutable accepted technical scope."""
import frappe


def validate_snapshot(program, row, old):
    tracked = ("capability", "source_request_item", "technical_configuration")
    if old:
        for field in tracked:
            current = frappe.parse_json(row.get(field)) if field == "technical_configuration" else row.get(field)
            previous = frappe.parse_json(old.get(field)) if field == "technical_configuration" else old.get(field)
            if current != previous:
                frappe.throw("方案的受理技术快照不可修改，请保留来源委托记录。")
    if not row.get("capability"):
        if row.get("technical_configuration"):
            frappe.throw("方案技术快照必须关联来源能力。")
        return
    if not program.test_request:
        frappe.throw("方案技术快照必须来自已受理委托。")
    request = frappe.get_doc("Test Request", program.test_request)
    request.check_permission("read")
    source = next((item for item in request.items if item.name == row.get("source_request_item")), None)
    if request.docstatus != 1 or not source or source.item_code != row.item_code:
        frappe.throw("方案技术快照的来源委托行无效。")
    if row.capability != source.capability or (
        frappe.parse_json(row.technical_configuration) != frappe.parse_json(source.technical_configuration)
    ):
        frappe.throw("方案必须保留正式受理的能力与条件快照。")


@frappe.whitelist()
def list_records(text=None, start=0):
    if not frappe.has_permission("Test Program", "read"):
        frappe.throw("没有试验记录读取权限。", frappe.PermissionError)
    programs = frappe.get_list("Test Program", fields=["name", "title"], limit_page_length=0)
    titles = {program.name: program.title for program in programs}
    if not titles:
        return {"rows": [], "has_more": False}
    rows = frappe.get_all("Test Program Item", filters={"parent": ["in", list(titles)]},
        fields=["name", "parent", "item_code", "test_project", "test_method", "standard", "test_condition", "technical_configuration",
                "status", "result", "conclusion", "raw_data", "actual_start", "actual_end"],
        order_by="modified desc, name asc", limit_page_length=0)
    projects = dict(frappe.get_all("Test Project", fields=["name", "project_name"], as_list=True))
    standards = dict(frappe.get_all("Test Standard", fields=["name", "full_name"], as_list=True))
    methods = dict(frappe.get_all("Test Method", fields=["name", "method_name"], as_list=True))
    term = (text or "").strip().casefold()[:100]
    matched = []
    for row in rows:
        configuration = frappe.parse_json(row.technical_configuration) or {}
        snapshot = configuration.get("snapshot") or {}
        row.project_label = snapshot.get("project_label") or projects.get(row.test_project) or methods.get(row.test_method) or row.item_code
        row.standard_label = snapshot.get("standard_label") or standards.get(row.standard) or row.standard
        row.pop("technical_configuration", None)
        row.program_title = titles[row.parent] or row.parent
        if not term or term in " ".join(str(value or "") for value in row.values()).casefold():
            matched.append(row)
    offset = max(0, int(start))
    return {"rows": matched[offset:offset + 20], "has_more": len(matched) > offset + 20}


def print_context(doc):
    from reli_lims.document_output.service import source_document, build_context, label_items
    from reli_lims.document_output.mapping.common import context
    if doc.doctype == "Test Report":
        return build_context(source_document("Test Report", doc.name))
    if doc.doctype != "Test Program":
        frappe.throw("不支持的试验打印单据。")
    program = label_items(source_document("Test Program", doc.name).as_dict())
    rows = [[row.get("test_project_label") or row.get("test_method_label") or row.get("item_code"),
             row.get("standard_label"), row.get("test_condition"), row.get("applicable_sample_names"),
             row.get("result"), row.get("conclusion")] for row in program.get("items", [])]
    return context("试验方案与记录", program,
        [("项目", program.get("project")), ("来源委托", program.get("test_request"))],
        ["检测项目", "检测依据（标准/方法）", "试验条件", "适用样品", "结果", "结论"], rows,
        notice="试验执行记录，报告签发状态以检测报告为准")
