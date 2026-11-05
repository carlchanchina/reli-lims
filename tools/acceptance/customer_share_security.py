"""免登录共享安全验收（只在 Carl 开发站执行）。

覆盖链接权限、附件私有访问、跨客户隔离、上传限制、重复确认、撤销、过期
与审计完整性。脚本自己创建验收单据（标题以 SEC-验收 开头），通过真实
HTTP 请求以 Guest 身份访问，服务端断言用 Frappe 直连。

用法（开发站）：
    ~/pilot/benches/dev-bench/env/bin/python tools/acceptance/customer_share_security.py

输出：终端 PASS/FAIL 汇总，并把结果写入 --output 指定的 JSON。
"""
import argparse
import base64
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import timedelta

import frappe

RESULTS = []
ARTIFACTS = {}


def check(name, ok, detail=""):
    RESULTS.append({"name": name, "ok": bool(ok), "detail": detail})
    print(("PASS  " if ok else "FAIL  ") + name + ("  | " + detail if detail else ""), flush=True)


def http(method, path, data=None, timeout=60):
    body = urllib.parse.urlencode(data).encode() if data else None
    request = urllib.request.Request(BASE + path, data=body, headers={"Host": SITE}, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", "replace")


def guest_accept(key, payload):
    return http("POST", "/api/method/frappe.website.doctype.web_form.web_form.accept", {
        "web_form": "customer-request",
        "web_form_request_key": key,
        "data": json.dumps(payload, ensure_ascii=False),
    })


def api(method_name, data):
    return http("POST", f"/api/method/{method_name}", data)


PNG_BYTES = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000a49444154789c63000100000500010d0a2db40000000049454e44ae426082")
PNG = base64.b64encode(PNG_BYTES).decode()


def ensure_customer(name):
    if not frappe.db.exists("Customer", name):
        frappe.get_doc({"doctype": "Customer", "customer_name": name, "customer_type": "Company"}).insert(
            ignore_permissions=True)
    return name


def template_request():
    rows = frappe.get_all("Test Request Item", fields=["parent"], limit_page_length=50)
    for row in rows:
        doc = frappe.get_doc("Test Request", row.parent)
        if doc.items and doc.samples and doc.docstatus == 0 and not doc.project:
            return doc
    frappe.throw("找不到可用于构造验收草稿的委托模板。")


def new_request(customer, suffix, template):
    doc = frappe.copy_doc(template)
    doc.title = f"SEC-验收 {suffix}"
    doc.customer = customer
    doc.customer_display_name = customer
    doc.request_date = frappe.utils.today()
    doc.delivery_date = frappe.utils.add_days(frappe.utils.today(), 14)
    doc.customer_confirmation_state = "Draft"
    # 验收草稿只复刻技术范围，不继承模板的商业来源，避免客户与报价不一致。
    doc.quotation = None
    doc.sales_order = None
    for row in doc.items:
        row.source_quotation = None
        row.source_quotation_item = None
        row.quoted_quantity = None
        row.requested_quantity = None
    for field in ("customer_confirmed_by", "customer_confirmed_at", "customer_confirmation_fingerprint",
                  "lab_reviewed_by", "lab_reviewed_at", "customer_attachment"):
        if doc.meta.has_field(field):
            doc.set(field, None)
    doc.customer_declaration_confirmed = 0
    doc.insert(ignore_permissions=True)
    return doc


def create_link(doc, days=7):
    detail = doc.run_method("send_customer_fill_link", expires_days=days,
                            customer_email="sec-acceptance@example.com")
    return detail["key"]


def payload_for(doc, **overrides):
    data = {
        "name": doc.name,
        "delivery_date": str(frappe.utils.add_days(frappe.utils.today(), 14)),
        "contact_person": "安全验收联系人",
        "contact_phone": "13700000000",
        "contact_email": "sec-acceptance@example.com",
        "applicant_address": "苏州市工业园区",
        "customer_shipping_details": "顺丰 SF0000000000，1 箱",
        "customer_expected_tests": "高温工作、低温贮存",
        "customer_reference_standards": "GB/T 2423.1-2008",
        "customer_declared_conditions": "+85℃ 48h；-40℃ 24h",
        "result_judgment": "Not Required",
        "subcontract_consent": "No",
        "method_choice_consent": "Yes",
        "fixture_required": "No",
        "report_format": "Electronic",
        "report_copies": 1,
        "sample_return": "Self Pickup",
        "customer_requirements": "安全验收用草稿",
        "customer_declaration_confirmed": 1,
        "samples": [{"product_name": "控制盒 KZH-833", "model": "KZH-833", "quantity": 1}],
    }
    data.update(overrides)
    return data


def main():
    global BASE, SITE
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", default="carl")
    parser.add_argument("--base", default="http://127.0.0.1:8000")
    parser.add_argument("--sites-path", default=os.path.expanduser("~/pilot/benches/dev-bench/sites"))
    parser.add_argument("--output", default=os.path.expanduser("~/pilot/state/customer-share-security.json"))
    args = parser.parse_args()
    BASE, SITE = args.base, args.site

    frappe.init(site=SITE, sites_path=args.sites_path)
    frappe.connect()
    frappe.set_user("Administrator")

    template = template_request()
    customer_a, customer_b = ensure_customer("SEC-验收客户A"), ensure_customer("SEC-验收客户B")
    request_a = new_request(customer_a, "主体", template)
    request_b = new_request(customer_b, "隔离", template)
    request_c = new_request(customer_a, "过期", template)
    request_d = new_request(customer_a, "撤销", template)
    key_a = create_link(request_a)
    key_b = create_link(request_b)
    key_c = create_link(request_c)
    key_d = create_link(request_d)
    # 客户页面由另一个进程读取，先提交事务，否则链接在 HTTP 端不可见。
    frappe.db.commit()
    ARTIFACTS.update({
        "request_a": request_a.name, "request_b": request_b.name,
        "request_c": request_c.name, "request_d": request_d.name,
        # 产物文件会被贴进验收报告，只记录掩码，不落完整密钥。
        "key_a_masked": f"{key_a[:3]}****", "key_b_masked": f"{key_b[:3]}****",
    })

    # ---------------------------------------------------------------- 1 链接权限
    status, page = http("GET", f"/customer-request/{request_a.name}?web_form_request_key={key_a}")
    check("免登录打开客户页", status == 200, f"HTTP {status}")
    check("客户页不出现内部标准/方法编码", "STD-" not in page and "MTH-" not in page,
          "页面未泄露 STD-/MTH- 编码")
    check("客户页不出现另一客户名称", customer_b not in page)

    status, _ = http("GET", f"/customer-request/{request_a.name}")
    check("无 key 访问被拒", status in (403, 410), f"HTTP {status}")
    status, _ = http("GET", f"/customer-request/{request_a.name}?web_form_request_key={key_a[:-3]}xyz")
    check("错误 key 被拒", status in (403, 410), f"HTTP {status}")
    status, _ = http("GET", f"/customer-request/{request_b.name}?web_form_request_key={key_a}")
    check("跨单据使用链接被拒", status in (403, 410), f"HTTP {status}")

    for method_name in ("reli_lims.customer_share.send_link", "reli_lims.customer_share.revoke_link",
                        "reli_lims.customer_share.list_links", "reli_lims.customer_share.lab_review"):
        status, _ = api(method_name, {"name": request_a.name})
        check(f"客户身份不能调用 {method_name.split('.')[-1]}", status in (403, 404, 417), f"HTTP {status}")

    sales_user = "sec-acceptance-sales@example.com"
    if not frappe.db.exists("User", sales_user):
        frappe.get_doc({"doctype": "User", "email": sales_user, "first_name": "SEC Sales",
                        "send_welcome_email": 0, "roles": [{"role": "Sales User"}]}).insert(ignore_permissions=True)
    frappe.set_user(sales_user)
    denied = 0
    for call in ("send_customer_fill_link", "revoke_customer_fill_link"):
        try:
            request_d.run_method(call)
        except frappe.PermissionError:
            denied += 1
        except Exception:
            denied += 1
    frappe.set_user("Administrator")
    check("非实验室角色不能发送/撤销链接", denied == 2, f"{denied}/2 被拒")

    # ---------------------------------------------------------------- 2 上传限制
    base_payload = payload_for(request_a)
    oversize = base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"0" * (10 * 1024 * 1024 + 2)).decode()
    cases = {
        "超过 10MB 附件被拒": dict(customer_attachment=f"data:image/png;base64,{oversize}"),
        "非图片/PDF 类型被拒": dict(customer_attachment=f"data:text/plain;base64,{base64.b64encode(b'hello').decode()}"),
        "内容与声明类型不符被拒": dict(customer_attachment=f"data:image/png;base64,{base64.b64encode(b'<script>').decode()}"),
        "空附件被拒": dict(customer_attachment="data:image/png;base64,"),
    }
    for label, override in cases.items():
        status, body = guest_accept(key_a, dict(base_payload, **override))
        check(label, status in (417, 400), f"HTTP {status} {body[:80]}")

    status, body = guest_accept(key_a, dict(base_payload, customer_attachment=f"data:image/png;base64,{PNG}"))
    check("合法附件保存成功", status == 200, f"HTTP {status} {body[:80]}")
    frappe.db.commit()
    request_a.reload()
    attachment_url = request_a.customer_attachment or ""
    file_row = frappe.db.get_value("File", {"file_url": attachment_url}, ["name", "is_private", "attached_to_doctype",
                                                                        "attached_to_name"], as_dict=True) or {}
    check("附件落盘为私有文件", bool(file_row.get("is_private")) and attachment_url.startswith("/private/files/"),
          f"{attachment_url}")
    check("附件绑定当前委托", file_row.get("attached_to_doctype") == "Test Request"
          and file_row.get("attached_to_name") == request_a.name)
    status, _ = http("GET", urllib.parse.quote(attachment_url))
    check("客户附件不能匿名下载", status in (403, 302, 401), f"HTTP {status}")

    # ---------------------------------------------------------------- 3 越权字段
    company_before = request_a.company
    tampered = dict(base_payload, **{
        "customer": "HACK-CUSTOMER", "company": "HACK-COMPANY",
        "customer_confirmation_state": "Lab Reviewed",
        "customer_confirmed_by": "hacker", "items": [{"item_code": "HACK", "standard": "HACK"}],
        "samples": [{"product_name": "注入后样品", "quantity": 0}],
    })
    status, _ = guest_accept(key_a, tampered)
    request_a.reload()
    check("注入客户/公司/状态字段无效", request_a.customer == customer_a
          and request_a.company == company_before
          and request_a.customer_confirmation_state == "Awaiting Customer Confirmation",
          f"state={request_a.customer_confirmation_state}")
    check("注入检测项目无效", all(row.item_code != "HACK" for row in request_a.items))
    check("数量为 0 的样品行被拒", status in (417, 400), f"HTTP {status}")

    # ---------------------------------------------------------------- 4 跨客户隔离
    status, _ = guest_accept(key_a, dict(base_payload, name=request_b.name))
    request_b.reload()
    check("A 的链接不能写入 B 的委托", status in (403, 410)
          and request_b.customer_confirmation_state != "Awaiting Lab Review", f"HTTP {status}")
    check("B 的委托内容未被 A 修改", request_b.customer_requirements != "安全验收用草稿"
          and request_b.contact_person != "安全验收联系人")

    # ---------------------------------------------------------------- 5 确认与重复确认
    status, body = api("reli_lims.customer_share.customer_confirm", {"web_form_request_key": key_a})
    check("客户确认进入实验室审核", status == 200 and "Awaiting Lab Review" in body, f"HTTP {status} {body[:80]}")
    status, body = api("reli_lims.customer_share.customer_confirm", {"web_form_request_key": key_a})
    check("重复确认被拒", status in (417, 403), f"HTTP {status} {body[:80]}")
    status, body = guest_accept(key_a, base_payload)
    check("确认后客户不能再保存", status in (417, 403), f"HTTP {status}")
    frappe.db.commit()
    audit = frappe.get_all("Test Request Share Event", filters={"test_request": request_a.name},
                           fields=["event", "actor_type", "event_time", "actor_ip", "changed_fields"])
    check("确认动作写入审计", any(row.event == "客户确认提交" for row in audit), f"{len(audit)} 条事件")
    check("保存动作记录变更字段", any(row.event.startswith("客户保存") and row.changed_fields not in (None, "", "[]")
                                     for row in audit))

    # ---------------------------------------------------------------- 6 撤销
    request_d.reload()
    request_d.run_method("revoke_customer_fill_link")
    frappe.db.commit()
    status, body = http("GET", f"/customer-request/{request_d.name}?web_form_request_key={key_d}")
    check("撤销后链接不可打开", status in (403, 410), f"HTTP {status}")
    status, _ = guest_accept(key_d, payload_for(request_d))
    check("撤销后不能保存", status in (403, 410), f"HTTP {status}")
    events = frappe.get_all("Test Request Share Event", filters={"test_request": request_d.name},
                            fields=["event", "actor_type"])
    check("撤销动作写入审计", any(row.event == "撤销客户填写链接" and row.actor_type == "实验室" for row in events))

    # ---------------------------------------------------------------- 7 过期
    frappe.db.set_value("Web Form Request",
                        frappe.db.get_value("Web Form Request", {"key": key_c}), "expires_on",
                        frappe.utils.add_days(frappe.utils.now_datetime(), -1))
    frappe.db.commit()
    status, _ = http("GET", f"/customer-request/{request_c.name}?web_form_request_key={key_c}")
    check("过期链接不可打开", status in (403, 410), f"HTTP {status}")
    status, _ = guest_accept(key_c, payload_for(request_c))
    check("过期链接不能保存", status in (403, 410), f"HTTP {status}")

    # ---------------------------------------------------------------- 8 审计完整性
    frappe.db.commit()
    events = frappe.get_all("Test Request Share Event",
                            filters={"test_request": ["in", [request_a.name, request_b.name,
                                                             request_c.name, request_d.name]]},
                            fields=["name", "test_request", "event", "actor_type", "actor", "event_time",
                                    "actor_ip", "web_form_request", "changed_fields"])
    kinds = {row.event for row in events}
    check("审计覆盖发送/保存/确认/撤销", {"发送客户填写链接", "客户确认提交", "撤销客户填写链接"} <= kinds,
          "、".join(sorted(kinds)))
    check("审计含操作者类型与时间", all(row.actor_type and row.event_time for row in events))
    check("审计绑定客户链接", all(row.web_form_request for row in events))
    check("审计记录访问 IP", all(row.actor_ip is not None for row in events))

    # 客户（Guest）直接查询审计表应无权限
    status, _ = http("GET", "/api/resource/" + urllib.parse.quote("Test Request Share Event"))
    check("Guest 不能读取审计资源", status in (403, 401), f"HTTP {status}")

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
