#!/usr/bin/env python3
"""正式打印与 PDF 验收：报告/方案/委托能否按权限真实出 PDF。

验证点：
  1. 打印视图能真实渲染（含关键字段），不是空壳；
  2. 关键字段齐全：委托编号、报告编号、样品、检测依据；
  3. 未登录（Guest）不能打印内部单据；
  4. 无权限角色不能打印内部单据。

PDF 文件本身由 tools/acceptance/print_pdf.js 用无头 Chrome 从真实打印视图生成
（该 bench 的 wkhtmltopdf 是 unpatched qt，且 CLI 下无法访问站点静态资源）。

用法：
    python tools/acceptance/print_pdf_check.py
"""

from __future__ import annotations

import argparse
import json
import os
import sys

DEFAULT_SITES = os.path.expanduser("~/pilot/benches/dev-bench/sites")
DEFAULT_APPS = os.path.expanduser("~/pilot/benches/dev-bench/apps")
DEFAULT_OUT = os.path.expanduser("~/pilot/state/print-pdf.json")
PDF_DIR = os.path.expanduser("~/pilot/state/print")

RESULTS: list[dict] = []


def visible_text(html: str) -> str:
    """去掉样式与脚本，取打印视图里真正可见的文字。"""
    import re

    body = re.sub(r"(?s)<style.*?</style>", " ", html)
    body = re.sub(r"(?s)<script.*?</script>", " ", body)
    text = re.sub(r"<[^>]+>", " ", body)
    import html as html_module

    return re.sub(r"\s+", " ", html_module.unescape(text)).strip()


def check(name, ok, detail=""):
    RESULTS.append({"name": name, "ok": bool(ok), "detail": str(detail)})
    print(f"[{'通过' if ok else '失败'}] {name} {detail}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", default="carl")
    parser.add_argument("--sites-path", default=DEFAULT_SITES)
    parser.add_argument("--apps-path", default=DEFAULT_APPS)
    parser.add_argument("--output", default=DEFAULT_OUT)
    parser.add_argument("--copy-to", default="",
                        help="把一份报告 PDF 复制到该目录（用于提交验收证据）")
    args = parser.parse_args()

    if args.apps_path not in sys.path:
        sys.path.insert(0, args.apps_path)

    import frappe

    frappe.init(site=args.site, sites_path=args.sites_path)
    frappe.connect()
    frappe.set_user("Administrator")
    # CLI 上下文没有请求初始化：打印模板会调用 include_style/bundled_asset，
    # 依赖 assets.json 与 preload 容器。这里只补齐渲染上下文，不改生产代码。
    frappe.local.lang = "zh"
    frappe.local.preload_assets = {"style": [], "script": [], "icons": []}
    # 该 bench 没有生成 sites/assets/assets.json，bundled_asset() 会返回 None；
    # 这里让资源映射为空，打印模板回退到未哈希的原路径。
    frappe.utils.get_assets_json = lambda: {}
    os.makedirs(PDF_DIR, exist_ok=True)

    report = frappe.get_all("Test Report", fields=["name"], order_by="creation desc", limit=1)
    request = frappe.get_all("Test Request", fields=["name"], filters={"docstatus": 1},
                             order_by="creation desc", limit=1)
    program = frappe.get_all("Test Program", fields=["name"], order_by="creation desc", limit=1)
    if not report or not request:
        print("缺少已受理委托或报告，无法验收打印。")
        return 1
    report, request = report[0].name, request[0].name
    targets = [("Test Report", report), ("Test Request", request)]
    if program:
        targets.append(("Test Program", program[0].name))

    texts = {}
    for doctype, name in targets:
        html = frappe.get_print(doctype, name, doc=None)
        with open(os.path.join(PDF_DIR, f"{doctype}-{name}.html"), "w", encoding="utf-8") as handle:
            handle.write(html)
        check(f"{doctype} {name} 生成打印视图", len(html) > 2000, f"{len(html)} 字节")
        check(f"{doctype} {name} 打印视图无报错",
              "Traceback" not in html and "Internal Server Error" not in html)
        text = visible_text(html)
        texts[doctype] = text
        check(f"{doctype} 打印视图含正文", len(text.strip()) > 100, f"{len(text)} 字符")

    report_text = texts.get("Test Report", "")
    request_text = texts.get("Test Request", "")
    program_text = texts.get("Test Program", "")
    customer = frappe.db.get_value("Test Request", request, "customer_display_name") \
        or frappe.db.get_value("Test Request", request, "customer")
    check("报告含报告编号", report in report_text, report)
    check("报告含来源委托编号", request in report_text, request)
    check("报告含委托单位", bool(customer) and customer in report_text, str(customer))
    check("委托单打印含样品与客户要求",
          "样品" in request_text and (customer or "") in request_text,
          f"{len(request_text)} 字符")
    if program_text:
        # 检测依据在方案与报告明细里，从方案行取真实标准编号比对。
        program_doc = frappe.get_all("Test Program Item", filters={"parent": program[0].name},
                                     fields=["standard"], limit=1)
        standard_code = None
        if program_doc and program_doc[0].get("standard"):
            standard_code = frappe.db.get_value("Test Standard", program_doc[0]["standard"],
                                                "standard_code")
        check("方案打印含检测依据与标准编号",
              "检测依据" in program_text and (not standard_code or standard_code in program_text),
              str(standard_code))
        check("方案打印含样品标识", "SMP-" in program_text or "样品" in program_text)

    # 未登录不能打印内部单据
    frappe.set_user("Guest")
    try:
        frappe.get_print("Test Report", report)
        check("未登录不能打印报告", False, "打印成功")
    except Exception as exc:  # noqa: BLE001
        check("未登录不能打印报告", "Permission" in type(exc).__name__ or "权限" in str(exc),
              type(exc).__name__)

    # 客户角色（无实验室角色）不能打印内部委托
    customer_user = "print-customer@example.com"
    frappe.set_user("Administrator")
    if not frappe.db.exists("User", customer_user):
        frappe.get_doc({"doctype": "User", "email": customer_user, "first_name": "打印客户",
                        "send_welcome_email": 0}).insert(ignore_permissions=True)
    frappe.set_user(customer_user)
    try:
        frappe.get_print("Test Request", request)
        check("无实验室角色不能打印委托", False, "打印成功")
    except Exception as exc:  # noqa: BLE001
        check("无实验室角色不能打印委托", "Permission" in type(exc).__name__ or "权限" in str(exc),
              type(exc).__name__)
    frappe.set_user("Administrator")


    passed = sum(1 for row in RESULTS if row["ok"])
    print(f"\n结果：{passed}/{len(RESULTS)} 通过")
    payload = {"total": len(RESULTS), "passed": passed, "failed": len(RESULTS) - passed,
               "results": RESULTS, "report": report, "request": request,
               "pdf_dir": PDF_DIR}
    with open(os.path.expanduser(args.output), "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, default=str)
    frappe.destroy()
    return 0 if passed == len(RESULTS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
