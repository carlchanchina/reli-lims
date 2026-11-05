#!/usr/bin/env python3
"""最小权限 + CNAS 能力批量审核验收。

覆盖：
  A. Lab Engineer 能读所属实验室的能力、项目、标准、方法；不能改/审核/发布。
  B. 批量审核：按实验室/项目/标准筛选、批量勾选、逐条留痕；审核与发布分权。
  C. 发布闸门：演示能力需显式确认、未审核不可发布、单次 ≤50 条、
     历史导入的待确认能力不会被"一键发布"。
  D. 对外投影区分演示能力与真实认可能力。

用法：
    python tools/acceptance/capability_review_and_roles.py [--site carl]
"""

from __future__ import annotations

import argparse
import json
import os
import sys

DEFAULT_SITES = os.path.expanduser("~/pilot/benches/dev-bench/sites")
DEFAULT_APPS = os.path.expanduser("~/pilot/benches/dev-bench/apps")
DEFAULT_OUT = os.path.expanduser("~/pilot/state/capability-review.json")

RESULTS: list[dict] = []
ARTIFACTS: dict = {}


def check(name, ok, detail=""):
    RESULTS.append({"name": name, "ok": bool(ok), "detail": str(detail)})
    print(f"[{'通过' if ok else '失败'}] {name} {detail}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", default="carl")
    parser.add_argument("--sites-path", default=DEFAULT_SITES)
    parser.add_argument("--apps-path", default=DEFAULT_APPS)
    parser.add_argument("--output", default=DEFAULT_OUT)
    args = parser.parse_args()

    if args.apps_path not in sys.path:
        sys.path.insert(0, args.apps_path)

    import frappe

    frappe.init(site=args.site, sites_path=args.sites_path)
    frappe.connect()
    frappe.set_user("Administrator")

    from reli_lims import capability_api, capability_review

    today = frappe.utils.today()

    # ------------------------------------------------------------ 基础数据
    rows = frappe.get_all("Laboratory Capability", fields=["laboratory"], limit_page_length=0)
    counts = {}
    for row in rows:
        if row.get("laboratory"):
            counts[row["laboratory"]] = counts.get(row["laboratory"], 0) + 1
    labs = sorted(counts.items(), key=lambda item: -item[1])
    if not labs:
        print("站点没有实验室能力，无法验收。")
        return 1
    lab_a, lab_a_total = labs[0]
    lab_b = labs[1][0] if len(labs) > 1 else None
    ARTIFACTS.update({"laboratory": lab_a, "laboratory_b": lab_b})
    baseline_pending = frappe.db.count("Laboratory Capability", {"status": "待确认"})
    baseline_total = frappe.db.count("Laboratory Capability")
    print(f"实验室 {lab_a}｜能力 {lab_a_total} 条｜待确认总数 {baseline_pending}")

    project = frappe.db.get_value("Test Project", {"active": 1}, "name") or \
        frappe.get_all("Test Project", pluck="name")[0]
    standard = frappe.get_all("Test Standard", fields=["name", "standard_code"], limit=1)[0]
    ARTIFACTS.update({"project": project, "standard": standard.name})

    def ensure_user(email, first_name, roles):
        if not frappe.db.exists("User", email):
            frappe.get_doc({"doctype": "User", "email": email, "first_name": first_name,
                            "send_welcome_email": 0,
                            "roles": [{"role": role} for role in roles]}).insert(ignore_permissions=True)
        else:
            user = frappe.get_doc("User", email)
            have = {row.role for row in user.roles}
            missing = [role for role in roles if role not in have]
            extra = [row for row in user.roles
                     if row.role not in roles and row.role not in ("All", "Guest")]
            if missing:
                for role in missing:
                    user.append("roles", {"role": role})
                user.save(ignore_permissions=True)
            if extra:
                for row in list(extra):
                    user.remove(row)
                user.save(ignore_permissions=True)
        frappe.clear_cache(user=email)
        return email

    engineer = ensure_user("cap-eng@example.com", "能力工程师", ["Lab Engineer"])
    reviewer = ensure_user("cap-rev@example.com", "能力审核员", ["Lab Reviewer"])
    manager = ensure_user("cap-mgr@example.com", "能力负责人", ["Lab Manager"])
    ARTIFACTS.update({"engineer": engineer, "reviewer": reviewer, "manager": manager})

    # 工程师只归属 A 实验室
    if not frappe.db.exists("User Permission",
                            {"user": engineer, "allow": "Laboratory Profile", "for_value": lab_a}):
        frappe.get_doc({"doctype": "User Permission", "user": engineer,
                        "allow": "Laboratory Profile", "for_value": lab_a,
                        "applicable_for": "Laboratory Capability"}).insert(ignore_permissions=True)
        frappe.clear_cache(user=engineer)
    frappe.db.commit()

    # ------------------------------------------------------------ A 最小权限
    frappe.set_user(engineer)
    visible = frappe.get_list("Laboratory Capability", fields=["name", "laboratory"],
                              limit_page_length=0)
    check("工程师可读实验室能力", len(visible) > 0, f"{len(visible)} 条")
    check("工程师只看到所属实验室的能力",
          all(row["laboratory"] == lab_a for row in visible),
          f"实验室集合 {sorted({row['laboratory'] for row in visible})}")
    if lab_b:
        other = frappe.get_all("Laboratory Capability", filters={"laboratory": lab_b},
                               pluck="name", limit=1)
        if other:
            try:
                frappe.get_doc("Laboratory Capability", other[0]).check_permission("read")
                check("工程师看不到其他实验室的能力", False, f"{other[0]} 仍可读")
            except frappe.PermissionError:
                check("工程师看不到其他实验室的能力", True, f"{other[0]} 被拒")
    for doctype in ("Test Project", "Test Standard", "Test Method"):
        try:
            count = len(frappe.get_list(doctype, limit_page_length=5))
            check(f"工程师可读主数据 {doctype}", count > 0, f"{count} 条")
        except Exception as exc:  # noqa: BLE001
            check(f"工程师可读主数据 {doctype}", False, str(exc))

    check("工程师无能力写入权限",
          not frappe.has_permission("Laboratory Capability", "write"), "has_permission=False")
    check("工程师无能力创建权限",
          not frappe.has_permission("Laboratory Capability", "create"), "has_permission=False")
    sample = visible[0]["name"] if visible else None
    if sample:
        try:
            doc = frappe.get_doc("Laboratory Capability", sample)
            doc.capability_scope = "越权修改尝试"
            doc.save()
            check("工程师修改能力被拒", False, "保存成功")
        except Exception as exc:  # noqa: BLE001
            check("工程师修改能力被拒", isinstance(exc, (frappe.PermissionError, frappe.ValidationError)),
                  type(exc).__name__)
    for label, call in (
        ("审核能力", lambda: capability_review.review([sample], "approve", note="工程师越权审核")),
        ("发布能力", lambda: capability_review.publish([sample], note="工程师越权发布")),
    ):
        try:
            call()
            check(f"工程师{label}被拒", False, "调用成功")
        except frappe.PermissionError:
            check(f"工程师{label}被拒", True, "PermissionError")
        except Exception as exc:  # noqa: BLE001
            check(f"工程师{label}被拒", "权限" in str(exc) or "没有" in str(exc), str(exc)[:60])
    frappe.set_user("Administrator")

    # ------------------------------------------------------------ 造测试能力
    def make_demo_capability(tag, demo=True):
        doc = frappe.get_doc({
            "doctype": "Laboratory Capability", "laboratory": lab_a,
            "test_project": project, "test_standard": standard.name,
            "capability_scope": f"验收用能力 {tag}：-40℃ 贮存 24h",
            "limitation": "验收用数据，不用于对外报告。",
            "accreditation_type": "演示（非认可）" if demo else "CNAS",
            "certificate_no": f"DEMO-{tag}",
            "demo_only": 1 if demo else 0,
            "scope_effective_date": today,
            "status": "待确认",
        })
        doc.insert(ignore_permissions=True)
        return doc.name

    names = [make_demo_capability(f"R{index}") for index in range(1, 4)]
    unreviewed = make_demo_capability("UNREV")
    ARTIFACTS["test_capabilities"] = names
    frappe.db.commit()

    # ------------------------------------------------------------ B 批量审核
    frappe.set_user(reviewer)
    found = capability_review.search(laboratory=lab_a, status="待确认", limit=50)
    found_names = {row["name"] for row in found["rows"]}
    check("按实验室筛选待确认能力", set(names).issubset(found_names), f"{len(found['rows'])} 条")
    by_standard = capability_review.search(laboratory=lab_a, test_standard=standard.name,
                                           status="待确认", limit=50)
    check("按标准筛选待确认能力",
          {row["test_standard"] for row in by_standard["rows"]} <= {standard.name},
          f"{len(by_standard['rows'])} 条")
    by_project = capability_review.search(test_project=project, status="待确认", limit=50)
    check("按项目筛选待确认能力",
          {row["test_project"] for row in by_project["rows"]} <= {project},
          f"{len(by_project['rows'])} 条")

    result = capability_review.review(names, "approve", note="验收：批量审核通过 3 条")
    check("审核员批量审核 3 条", sorted(result["done"]) == sorted(names), f"done={len(result['done'])}")
    logs_ok = True
    for name in names:
        doc = frappe.get_doc("Laboratory Capability", name)
        rows = [row for row in doc.review_log if row.action == "审核通过"]
        logs_ok = logs_ok and bool(rows) and rows[-1].actor == reviewer \
            and rows[-1].actor_role == "Lab Reviewer" and rows[-1].at is not None
        logs_ok = logs_ok and doc.reviewed_by == reviewer and doc.reviewed_on is not None
    check("每条能力保留独立审核记录", logs_ok, "action/actor/role/时间 均写入")
    try:
        capability_review.publish(names, note="审核员越权发布")
        check("审核员不能发布", False, "发布成功")
    except frappe.PermissionError:
        check("审核员不能发布", True, "PermissionError")
    frappe.set_user("Administrator")

    # ------------------------------------------------------------ C 发布闸门
    frappe.set_user(manager)
    try:
        capability_review.publish(names, note="未勾选演示能力直接发布")
        check("演示能力需显式确认后才发布", False, "直接发布成功")
    except Exception as exc:  # noqa: BLE001
        check("演示能力需显式确认后才发布", "演示" in str(exc), str(exc)[:80])

    try:
        capability_review.publish([f"CAP-{index:05d}" for index in range(60)], note="批量超限测试")
        check("单次发布上限 50 条", False, "超过上限仍执行")
    except Exception as exc:  # noqa: BLE001
        check("单次发布上限 50 条", "50" in str(exc), str(exc)[:60])

    try:
        capability_review.publish([unreviewed], note="未审核发布", include_demo=True)
        check("未审核能力不能发布", False, "发布成功")
    except Exception as exc:  # noqa: BLE001
        check("未审核能力不能发布", "尚未经过审核" in str(exc), str(exc)[:80])

    result = capability_review.publish(names, note="验收：显式包含演示能力", include_demo=True)
    check("显式确认后发布演示能力", sorted(result["published"]) == sorted(names),
          f"published={len(result['published'])}")
    demo_doc = frappe.get_doc("Laboratory Capability", names[0])
    published_logs = [row for row in demo_doc.review_log if row.action == "发布"]
    check("发布动作同样逐条留痕", bool(published_logs) and published_logs[-1].actor == manager,
          f"发布人 {demo_doc.published_by}")
    frappe.set_user("Administrator")

    public = capability_api.get_public_capability(names[0])
    check("对外投影标注演示能力", public.get("demo_only") is True
          and public.get("accreditation_type") == "演示（非认可）",
          str(public.get("accreditation_type")))

    # 历史导入不被批量发布：待确认总量只减少我们审核的 3 条
    pending_now = frappe.db.count("Laboratory Capability", {"status": "待确认"})
    check("历史待确认能力未被批量发布",
          pending_now >= baseline_pending - len(names) + 1,
          f"待确认 {baseline_pending} → {pending_now}")

    # ------------------------------------------------------------ D 停用
    frappe.set_user(manager)
    retired = capability_review.retire([names[2]], note="验收：停用一条演示能力")
    frappe.set_user("Administrator")
    check("停用后不再计入已发布",
          frappe.db.get_value("Laboratory Capability", names[2], "status") == "已停用"
          and not frappe.db.get_value("Laboratory Capability", names[2], "published"),
          "status=已停用, published=0")

    # ------------------------------------------------------------ 收尾
    frappe.set_user("Administrator")
    for name in names + [unreviewed]:
        if frappe.db.get_value("Laboratory Capability", name, "status") == "已发布":
            continue
        frappe.delete_doc("Laboratory Capability", name, ignore_permissions=True, force=True)
    frappe.db.commit()

    passed = sum(1 for row in RESULTS if row["ok"])
    print(f"\n结果：{passed}/{len(RESULTS)} 通过")
    payload = {"total": len(RESULTS), "passed": passed, "failed": len(RESULTS) - passed,
               "results": RESULTS, "artifacts": ARTIFACTS}
    os.makedirs(os.path.dirname(os.path.expanduser(args.output)), exist_ok=True)
    with open(os.path.expanduser(args.output), "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, default=str)
    frappe.destroy()
    return 0 if passed == len(RESULTS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
