#!/usr/bin/env python3
"""为演示/验收生成一条新的客户免登录链接。

约定（防止密钥再次外泄）：

  * 完整链接只写入本机状态文件（默认 `~/pilot/state/demo-link.json`，权限 600）；
  * 终端与日志只打印掩码，不打印完整 key；
  * 同一委托再次生成时，旧链接由 send_link 自动撤销，不会并存。

用法：
    python tools/acceptance/make_demo_link.py --request REQ-01481
    python tools/acceptance/make_demo_link.py --request REQ-01481 --days 3 --out ~/pilot/state/demo-link.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys

DEFAULT_SITES = os.path.expanduser("~/pilot/benches/dev-bench/sites")
DEFAULT_APPS = os.path.expanduser("~/pilot/benches/dev-bench/apps")
DEFAULT_OUT = os.path.expanduser("~/pilot/state/demo-link.json")


def mask(key: str) -> str:
    return f"{key[:3]}****（共 {len(key)} 位）"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", required=True, help="委托草稿编号")
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--site", default="carl")
    parser.add_argument("--sites-path", default=DEFAULT_SITES)
    parser.add_argument("--apps-path", default=DEFAULT_APPS)
    parser.add_argument("--out", default=DEFAULT_OUT)
    parser.add_argument("--actor", default="demo-lab-manager@example.com",
                        help="以哪个实验室账号签发（需有 Lab Manager 角色）")
    args = parser.parse_args()

    if args.apps_path not in sys.path:
        sys.path.insert(0, args.apps_path)

    import frappe

    frappe.init(site=args.site, sites_path=args.sites_path)
    frappe.connect()
    frappe.set_user(args.actor)

    from reli_lims.customer_share import send_link

    link = send_link(args.request, expires_days=args.days)
    frappe.db.commit()

    payload = {
        "request": args.request,
        "share": link["share"],
        "url": link["url"],
        "expires_on": link["expires_on"],
        "issued_by": args.actor,
    }
    out = os.path.expanduser(args.out)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    # 先建空文件再写，确保权限在写入前就是 600。
    descriptor = os.open(out, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")

    print(f"委托 {args.request} 新链接已生成")
    print(f"  分享号 {link['share']}｜有效期至 {link['expires_on']}")
    print(f"  密钥 {mask(link['key'])}（完整链接仅在本机文件）")
    print(f"  文件 {out}（权限 600，勿提交、勿粘贴到 PR/聊天）")

    frappe.destroy()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
