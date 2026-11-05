"""正式受理与检测执行链路验收（只在 Carl 开发站执行）。

用"经过审核发布"的演示能力走完整链路，不放宽任何真实校验：

    演示能力（待确认 → 已确认 → 已发布）
      → 客户报价（已提交）
      → 委托草稿 + 客户免登录填写/确认
      → 实验室审核
      → 正式受理（生成 Project）
      → 收样 → 试验方案 → 执行（待执行/执行中/完成/复核）
      → 报告草稿

所有校验（客户确认、实验室审核、Active 标准、启用项目、已发布能力、商业来源）
都按生产逻辑执行，脚本只负责提供合法的演示数据。

用法：
    ~/pilot/benches/dev-bench/env/bin/python tools/acceptance/formal_acceptance_flow.py
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

import frappe

APP_ROOT = os.environ.get("RELI_APP_ROOT", os.path.expanduser("~/pilot/benches/dev-bench/apps/reli_lims"))
if APP_ROOT not in sys.path:
    sys.path.insert(0, APP_ROOT)

RESULTS = []
ARTIFACTS = {}
TODAY = None
DEMO_STANDARD_CODE = "RELI-DEMO-20261105"
DEMO_PROJECT = "高低温复合试验（开发演示）"
DEMO_METHOD = "低温贮存试验（开发演示）"
DEMO_OBJECT = "控制盒（开发演示）"
DEMO_CUSTOMER = "演示客户（正式受理验收）"


def check(name, ok, detail=""):
    RESULTS.append({"name": name, "ok": bool(ok), "detail": detail})
    print(("PASS  " if ok else "FAIL  ") + name + ("  | " + detail if detail else ""), flush=True)


def http(method, path, data=None):
    body = urllib.parse.urlencode(data).encode() if data else None
    request = urllib.request.Request(BASE + path, data=body, headers={"Host": SITE}, method=method)
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return response.status, response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", "replace")


def ensure_user(email, first_name, roles):
    if not frappe.db.exists("User", email):
        frappe.get_doc({"doctype": "User", "email": email, "first_name": first_name,
                        "send_welcome_email": 0,
                        "roles": [{"role": role} for role in roles]}).insert(ignore_permissions=True)
    else:
        user = frappe.get_doc("User", email)
        existing = {row.role for row in user.roles}
        missing = [role for role in roles if role not in existing]
        if missing:
            for role in missing:
                user.append("roles", {"role": role})
            user.save(ignore_permissions=True)
    frappe.db.commit()
    return email


def as_user(user):
    frappe.set_user(user)


def ensure_laboratory():
    rows = frappe.get_all("Laboratory Profile", fields=["name"], limit=1)
    if rows:
        return rows[0].name
    return frappe.get_doc({"doctype": "Laboratory Profile",
                           "laboratory_name": "苏州可靠性检测实验室"}).insert(ignore_permissions=True).name


def ensure_object():
    name = frappe.db.get_value("Test Object", {"object_name": DEMO_OBJECT})
    if name:
        return name
    return frappe.get_doc({"doctype": "Test Object", "object_name": DEMO_OBJECT,
                           "category": "环境试验"}).insert(ignore_permissions=True).name


CONDITION_SCHEMA = [
    {"key": "temp_c", "label": "试验温度（℃）", "type": "number"},
    {"key": "duration_h", "label": "保持时间（小时）", "type": "number"},
    {"key": "mode", "label": "试验阶段", "type": "text"},
]


def ensure_masters():
    standard = frappe.db.get_value("Test Standard", {"standard_code": DEMO_STANDARD_CODE})
    if not standard:
        doc = frappe.get_doc({"doctype": "Test Standard", "standard_code": DEMO_STANDARD_CODE,
                              "title": "开发演示：低温贮存与高温工作（非 CNAS 认可范围）",
                              "version": "2026-11-05", "status": "Draft",
                              "basis_type": "企业标准", "effective_date": TODAY,
                              "notes": "开发站流程验收专用；不代表 CNAS 认可范围，禁止对外签发。"})
        doc.insert(ignore_permissions=True)
        standard = doc.name
    project = frappe.db.get_value("Test Project", {"project_name": DEMO_PROJECT})
    if not project:
        project = frappe.get_doc({
            "doctype": "Test Project", "project_name": DEMO_PROJECT, "normalized_name": DEMO_PROJECT,
            "category": "环境试验", "classification_status": "已归类", "active": 1,
            "description": "开发站演示项目，用于正式受理与执行链路验收。",
            "condition_template": json.dumps(CONDITION_SCHEMA, ensure_ascii=False),
        }).insert(ignore_permissions=True).name
    method = frappe.db.get_value("Test Method", {"method_name": DEMO_METHOD})
    if not method:
        method = frappe.get_doc({"doctype": "Test Method", "method_name": DEMO_METHOD,
                                 "test_project": project, "category": "环境试验", "active": 1,
                                 "default_standard": standard,
                                 "notes": "开发站演示方法"}).insert(ignore_permissions=True).name
    ARTIFACTS.update({"standard": standard, "project": project, "method": method})
    return standard, project, method


def standard_release(standard, manager):
    """标准启用走实验室负责人正常编辑，不绕过状态字段。"""
    doc = frappe.get_doc("Test Standard", standard)
    if doc.status == "Active":
        return doc
    as_user(manager)
    doc.status = "Active"
    doc.save()
    as_user("Administrator")
    return doc


def ensure_capability(standard, project, method, laboratory, test_object, reviewer, manager):
    name = frappe.db.get_value("Laboratory Capability",
                               {"test_standard": standard, "test_method": method,
                                "laboratory": laboratory})
    if name:
        doc = frappe.get_doc("Laboratory Capability", name)
    else:
        doc = frappe.get_doc({
            "doctype": "Laboratory Capability",
            "laboratory": laboratory, "test_project": project, "test_object": test_object,
            "test_method": method, "test_standard": standard,
            "product_scope": "控制盒、车载电子部件",
            "capability_scope": "开发演示：低温贮存 -40℃ 与高温工作 +85℃",
            "limitation": "开发演示能力，不用于真实对外报告。",
            "accreditation_type": "演示（非认可）", "certificate_no": "DEMO-ONLY",
            "demo_only": 1, "scope_effective_date": TODAY,
            "industry": "轨道交通", "project_parameter": "温度环境适应性",
            "condition_schema": json.dumps(CONDITION_SCHEMA, ensure_ascii=False),
            "status": "待确认",
        })
        doc.insert(ignore_permissions=True)
    # 演示能力必须在审核前就标清楚，否则一旦进入已确认/已发布，内容即被冻结。
    if doc.status == "待确认" and (not doc.get("demo_only")
                                   or doc.get("accreditation_type") != "演示（非认可）"
                                   or not (doc.get("certificate_no") or "").startswith("DEMO")):
        as_user(manager)
        doc.reload()
        doc.demo_only = 1
        doc.accreditation_type = "演示（非认可）"
        doc.certificate_no = "DEMO-ONLY"
        doc.scope_effective_date = TODAY
        doc.save()
        as_user("Administrator")
        doc.reload()
    # 走真实状态机：待确认 → 已确认（实验室审核员）→ 已发布（实验室负责人）。
    if doc.status == "待确认":
        as_user(reviewer)
        frappe.get_attr("reli_lims.capability_api.confirm_capability")(doc.name)
    if frappe.db.get_value("Laboratory Capability", doc.name, "status") == "已确认":
        as_user(manager)
        frappe.get_attr("reli_lims.capability_api.publish_capability")(doc.name)
    as_user("Administrator")
    doc.reload()
    ARTIFACTS["capability"] = doc.name
    return doc


def ensure_customer():
    if not frappe.db.exists("Customer", DEMO_CUSTOMER):
        template = frappe.get_all("Customer", fields=["customer_group", "territory"], limit=1)
        doc = frappe.get_doc({"doctype": "Customer", "customer_name": DEMO_CUSTOMER,
                              "customer_type": "Company",
                              "customer_group": template[0].customer_group if template else None,
                              "territory": template[0].territory if template else None})
        doc.insert(ignore_permissions=True)
    return DEMO_CUSTOMER


def ensure_quotation(customer, company, item_code, manager):
    """演示报价由管理员预置：报价属商业单据，不应要求实验室账号具备销售权限。"""
    existing = frappe.get_all("Quotation", filters={"party_name": customer, "docstatus": 1},
                              fields=["name"], limit=1)
    if existing:
        return existing[0].name
    as_user("Administrator")
    quote = frappe.get_doc({
        "doctype": "Quotation", "quotation_to": "Customer", "party_name": customer,
        "company": company, "transaction_date": TODAY, "valid_till": frappe.utils.add_days(TODAY, 30),
        "currency": frappe.db.get_value("Company", company, "default_currency") or "CNY",
        "conversion_rate": 1, "plc_conversion_rate": 1,
        "items": [{"item_code": item_code, "qty": 1, "rate": 1200,
                   "uom": frappe.db.get_value("Item", item_code, "stock_uom") or "Nos"}],
    })
    quote.insert(ignore_permissions=True)
    quote.submit()
    return quote.name


def build_request(customer, company, quotation, capability, samples, manager):
    """受理建单由实验室负责人完成：Lab Engineer 无能力目录读权限，不能选能力。"""
    from reli_lims.capability_request import prepare_items

    as_user(manager)
    items = prepare_items([{"capability_id": capability.name,
                            "conditions": {"temp_c": -40, "duration_h": 24, "mode": "低温贮存"}},
                           {"capability_id": capability.name,
                            "conditions": {"temp_c": 85, "duration_h": 48, "mode": "高温工作"}}])
    for index, row in enumerate(items, start=1):
        # 委托行编号由受理人分配，能力选择只提供技术字段。
        row["item_code"] = f"CAP-{index}"
    doc = frappe.get_doc({
        "doctype": "Test Request", "title": "控制盒 KZH-833 高低温试验（演示受理）",
        "request_date": TODAY, "delivery_date": frappe.utils.add_days(TODAY, 20),
        "customer": customer, "company": company, "quotation": quotation,
        "contact_person": "周工", "contact_phone": "13800001111",
        "contact_email": "zhou@example.com", "applicant_address": "苏州市吴中区",
        "customer_requirements": "按 -40℃/24h 与 +85℃/48h 执行，出具中文电子报告。",
        "customer_expected_tests": "低温贮存、高温工作",
        "customer_shipping_details": "顺丰 SF1234567890，1 箱",
        "result_judgment": "Not Required", "subcontract_consent": "No",
        "method_choice_consent": "Yes", "fixture_required": "No",
        "report_format": "Electronic", "report_copies": 1, "sample_return": "Self Pickup",
        "samples": samples, "items": items,
        "sample_assignments": [{"item_code": row["item_code"], "sample_code": code}
                               for row in items for code in ("S1", "S2")],
    })
    doc.insert()
    as_user("Administrator")
    return doc


def guest_fill_and_confirm(url_key, name, samples):
    payload = {
        "name": name,
        "samples": samples,
        "contact_person": "周工（客户确认）",
        "contact_phone": "13800001111",
        "contact_email": "zhou@example.com",
        "delivery_date": str(frappe.utils.add_days(TODAY, 20)),
        "customer_requirements": "按 -40℃/24h 与 +85℃/48h 执行，出具中文电子报告。",
        "customer_expected_tests": "低温贮存、高温工作",
        "customer_declared_conditions": "-40℃ 24h；+85℃ 48h",
        "customer_declaration_confirmed": 1,
    }
    status, body = http("POST", "/api/method/frappe.website.doctype.web_form.web_form.accept", {
        "web_form": "customer-request", "web_form_request_key": url_key,
        "data": json.dumps(payload, ensure_ascii=False)})
    check("客户免登录保存", status == 200, f"HTTP {status} {body[:100]}")
    status, body = http("POST", "/api/method/reli_lims.customer_share.customer_confirm",
                        {"web_form_request_key": url_key})
    check("客户确认提交", status == 200 and "Awaiting Lab Review" in body, f"HTTP {status}")


def main():
    global BASE, SITE, TODAY
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", default="carl")
    parser.add_argument("--base", default="http://127.0.0.1:8000")
    parser.add_argument("--sites-path", default=os.path.expanduser("~/pilot/benches/dev-bench/sites"))
    parser.add_argument("--output", default=os.path.expanduser("~/pilot/state/formal-acceptance.json"))
    args = parser.parse_args()
    BASE, SITE = args.base, args.site
    frappe.init(site=SITE, sites_path=args.sites_path)
    frappe.connect()
    frappe.set_user("Administrator")
    TODAY = frappe.utils.today()

    reviewer = ensure_user("demo-lab-reviewer@example.com", "演示审核员", ["Lab Reviewer"])
    # 最小权限组合：实验室岗位 + Projects User（履约项目读写）。
    # 不授予 Sales User：lab 侧读报价/客户改走有界投影，见 reli_lims/commercial_access.py。
    manager = ensure_user("demo-lab-manager@example.com", "演示负责人",
                          ["Lab Manager", "Projects User"])
    engineer = ensure_user("demo-lab-engineer@example.com", "演示工程师",
                           ["Lab Engineer", "Projects User"])
    for email, forbidden in ((manager, "Sales User"), (engineer, "Sales User")):
        check(f"受理/执行账号不含无关角色 {forbidden}（{email}）",
              forbidden not in {row.role for row in frappe.get_doc("User", email).roles})

    laboratory = ensure_laboratory()
    test_object = ensure_object()
    standard, project, method = ensure_masters()
    ARTIFACTS.update({"laboratory": laboratory, "test_object": test_object})

    standard_doc = standard_release(standard, manager)
    check("演示标准经负责人启用为 Active", standard_doc.status == "Active", standard_doc.name)

    capability = ensure_capability(standard, project, method, laboratory, test_object, reviewer, manager)
    check("演示能力经审核发布", capability.status == "已发布" and capability.published == 1,
          f"{capability.name} / {capability.status}")

    customer = ensure_customer()
    company = frappe.defaults.get_global_default("company") or frappe.get_all("Company", limit=1)[0].name
    item_code = frappe.db.get_value("Item", {"item_name": "疲劳载荷试验", "is_sales_item": 1}) \
        or frappe.get_all("Item", filters={"is_sales_item": 1}, limit=1)[0].name
    quotation = ensure_quotation(customer, company, item_code, manager)
    check("客户报价已提交", frappe.db.get_value("Quotation", quotation, "docstatus") == 1, quotation)

    samples = [
        {"sample_code": "S1", "product_name": "控制盒 KZH-833", "model": "KZH-833",
         "quantity": 2, "serial_no": "SN-2026-0001"},
        {"sample_code": "S2", "product_name": "控制盒 KZH-833（备样）", "model": "KZH-833",
         "quantity": 1},
    ]
    request = build_request(customer, company, quotation, capability, samples, manager)
    ARTIFACTS.update({"request": request.name, "quotation": quotation})
    check("委托草稿引用已发布能力", all(row.capability == capability.name for row in request.items),
          f"{len(request.items)} 条检测项目")

    as_user(manager)
    link = request.run_method("send_customer_fill_link", expires_days=7,
                              customer_email="zhou@example.com")
    as_user("Administrator")
    # 客户页面由另一个进程读取，必须先提交事务，否则链接不可见。
    frappe.db.commit()
    ARTIFACTS["customer_url"] = link["url"]
    sample_payload = [{"sample_code": row.sample_code, "product_name": row.product_name,
                       "model": row.model, "quantity": row.quantity,
                       "serial_no": row.serial_no} for row in request.samples]
    guest_fill_and_confirm(link["key"], request.name, sample_payload)
    frappe.db.commit()

    as_user(manager)
    request.reload()
    request.run_method("review_customer_fill", approve=1, note="演示链路：实验室审核通过")
    check("实验室审核通过", frappe.db.get_value("Test Request", request.name,
                                                "customer_confirmation_state") == "Lab Reviewed")

    frappe.db.commit()
    request.reload()
    request.submit()
    frappe.db.commit()
    as_user("Administrator")
    request.reload()
    check("正式受理生成项目", bool(request.project) and request.docstatus == 1,
          f"{request.name} → {request.project}")

    as_user(engineer)
    from reli_lims.services.test_request import make_test_program, receive_samples
    received = receive_samples(request.name, [
        {"sample_code": "S1", "quantity": 2, "received_date": TODAY, "received_by": engineer},
        {"sample_code": "S2", "quantity": 1, "received_date": TODAY, "received_by": engineer},
    ])
    check("样品收样登记", len(received) == 2, "、".join(received))
    program_name = make_test_program(request.name)
    program = frappe.get_doc("Test Program", program_name)
    ARTIFACTS.update({"program": program_name, "samples": received})

    # ---------------- 传递校验：样品 / 检测项目 / 标准方法 / 技术条件
    check("方案样品与委托一致", len(program.samples) == len(request.samples),
          f"{len(program.samples)} 行")
    sample_rows = {row.sample: frappe.get_doc("Sample", row.sample) for row in program.samples}
    check("样品绑定项目与来源委托", all(row.project == request.project and row.test_request == request.name
                                        for row in sample_rows.values()))
    check("样品保留客户填写信息", any(row.serial_no == "SN-2026-0001" for row in sample_rows.values()),
          "序列号 SN-2026-0001")
    request_items = {row.item_code: row for row in request.items}
    mismatched = [row.item_code for row in program.items
                  if row.standard != request_items[row.item_code].standard
                  or row.test_method != request_items[row.item_code].test_method
                  or row.test_project != request_items[row.item_code].test_project]
    check("方案标准/方法/项目与委托逐行一致", not mismatched, "、".join(mismatched))
    check("方案保留技术条件原文", all(row.test_condition for row in program.items),
          "；".join(row.test_condition for row in program.items))
    check("方案保留能力与条件快照", all(row.capability and row.technical_configuration
                                        for row in program.items))
    check("方案保留来源委托行", all(row.source_request_item for row in program.items))
    assignments = {(row.item_code, row.sample) for row in program.sample_assignments}
    check("样品分配继承委托", len(assignments) == len(request.sample_assignments),
          f"{len(assignments)} 组")

    # ---------------- 执行链路
    for row in program.items:
        row.engineer = engineer
        row.status = "Ready"
    program.save()
    for row in program.items:
        row.status = "Running"
    program.save()
    for row in program.items:
        row.status = "Completed"
        row.result = "外观正常，功能正常"
        row.conclusion = "符合委托条件"
    program.save()
    as_user(reviewer)
    program.reload()
    for row in program.items:
        row.status = "Reviewed"
    program.save()
    as_user("Administrator")
    program.reload()
    check("试验执行记录完成复核", program.status == "Completed"
          and all(row.status == "Reviewed" for row in program.items), program.status)

    from reli_lims.execution_records import list_records
    records = list_records(start=0)
    check("试验记录可检索到本次执行", any(row["parent"] == program_name for row in records["rows"]),
          f"{len(records['rows'])} 行")

    report = frappe.get_doc({"doctype": "Test Report", "test_program": program_name,
                             "project": program.project, "engineer": engineer,
                             "status": "Draft", "test_start": TODAY, "test_end": TODAY,
                             "version": "V1", "notes": "开发站演示报告草稿"})
    report.insert(ignore_permissions=True)
    ARTIFACTS["report"] = report.name
    check("报告草稿继承来源委托", report.test_request == request.name
          and report.customer == customer and report.project == program.project,
          f"{report.name} → {report.test_request}")

    from reli_lims.document_output.service import build_context, source_document
    context = build_context(source_document("Test Report", report.name))
    rendered = json.dumps(context, ensure_ascii=False, default=str)
    check("报告上下文包含样品与条件", "控制盒 KZH-833" in rendered and "-40" in rendered,
          "样品按产品名称呈现")

    frappe.db.commit()
    passed = sum(1 for row in RESULTS if row["ok"])
    summary = {"total": len(RESULTS), "passed": passed, "failed": len(RESULTS) - passed,
               "artifacts": ARTIFACTS, "results": RESULTS}
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as handle:
        json.dump(summary, handle, ensure_ascii=False, indent=2, default=str)
    print(f"\n合计 {passed}/{len(RESULTS)} 通过；明细写入 {args.output}")
    frappe.destroy()
    return 0 if passed == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
