#!/usr/bin/env python3
"""撤销开发站上仍在生效的客户免登录链接（密钥轮换）。

只要某个链接的完整 `web_form_request_key` 出现在聊天记录、PR、截图或文档里，
就必须立刻撤销并用新链接替代。本脚本是唯一认可的撤销入口，保证：

  * 只撤销 `customer-request` 表单的链接，不动其它 Web Form；
  * 每条撤销都在对应委托上写一条「撤销客户填写链接」审计，写明原因；
  * 输出只打印密钥前缀与长度，绝不回显完整密钥；
  * 结束后校验站点上已无可用链接。

用法：
    python tools/rotate_customer_links.py --dry-run
    python tools/rotate_customer_links.py --reason "链接在验收日志中泄露"
"""

from __future__ import annotations

import argparse
import os
import sys

DEFAULT_SITES = os.path.expanduser("~/pilot/benches/dev-bench/sites")
DEFAULT_APPS = os.path.expanduser("~/pilot/benches/dev-bench/apps")


def mask(key: str | None) -> str:
    if not key:
        return "<空>"
    return f"{key[:3]}****（共 {len(key)} 位）"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", default="carl")
    parser.add_argument("--sites-path", default=DEFAULT_SITES)
    parser.add_argument("--apps-path", default=DEFAULT_APPS)
    parser.add_argument("--request", help="仅撤销指定检测委托的客户链接")
    parser.add_argument("--reason", default="安全轮换：密钥曾出现在验收材料中")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.apps_path not in sys.path:
        sys.path.insert(0, args.apps_path)

    import frappe

    frappe.init(site=args.site, sites_path=args.sites_path)
    frappe.connect()
    frappe.set_user("Administrator")

    from reli_lims.customer_share import log_event
    from frappe.utils import get_datetime, now_datetime

    rows = frappe.get_all(
        "Web Form Request",
        filters={"web_form": "customer-request", "reli_revoked": 0},
        fields=["name", "key", "expires_on"],
    )
    now = now_datetime()
    active = [row for row in rows if not row.expires_on or get_datetime(row.expires_on) > now]
    print(f"站点 {args.site}：未撤销 {len(rows)} 条，其中仍可用 {len(active)} 条")

    revoked = 0
    for row in active:
        share = frappe.get_doc("Web Form Request", row.name)
        refs = [(link.link_doctype, link.link_name) for link in share.references]
        target = next((name for doctype, name in refs if doctype == "Test Request"), None)
        if args.request and target != args.request:
            continue
        print(f"  {row.name} -> {target or '未绑定委托'} | key {mask(row.key)}")
        if args.dry_run:
            continue
        share.db_set({"expires_on": now, "reli_revoked": 1, "reli_revoked_on": now,
                      "reli_revoked_by": "Administrator"}, update_modified=True)
        if target:
            log_event(target, "撤销客户填写链接", "实验室", share=share.name, detail=args.reason)
        revoked += 1

    if args.dry_run:
        print("dry-run：未写入任何变更")
        frappe.destroy()
        return 0

    frappe.db.commit()
    remaining = frappe.get_all("Web Form Request",
                               filters={"web_form": "customer-request", "reli_revoked": 0},
                               fields=["name", "expires_on"])
    still_usable = [row for row in remaining
                    if not row.expires_on or get_datetime(row.expires_on) > now]
    if args.request:
        still_usable = [row for row in still_usable if any(
            link.link_doctype == "Test Request" and link.link_name == args.request
            for link in frappe.get_doc("Web Form Request", row.name).references)]
    print(f"已撤销 {revoked} 条；剩余未撤销 {len(remaining)} 条，其中仍可用 {len(still_usable)} 条"
          f"（已过期但未标撤销的属正常）")
    frappe.destroy()
    return 0 if not still_usable else 1


if __name__ == "__main__":
    raise SystemExit(main())
