"""CNAS 能力审核工作流：按实验室/项目/标准筛选、批量审核、逐条留痕、受控发布。

设计边界（有意为之）：

  * 批量只是"省点击"，不是"免审核"：审核与发布是两个角色、两次调用，
    任何一条能力都必须先有审核记录（reviewed_by）才可能被发布；
  * 单次批量上限 50 条，杜绝"一键发布 650 条历史导入"；
  * 演示能力与真实认可能力必须分开：演示能力强行要求 `accreditation_type=演示（非认可）`
    且证书号以 DEMO 开头，批量发布时需显式 `include_demo=True`；
  * 真实 CNAS/CMA 能力发布前必须具备证书编号与范围生效日期，否则拦截；
  * 每次动作都在能力上追加一条 `Capability Review Log`，逐条可追溯。
"""
import json

import frappe
from frappe import _
from frappe.utils import now_datetime

REVIEW_ROLES = ("Lab Reviewer", "Lab Manager", "System Manager")
PUBLISH_ROLES = ("Lab Manager", "System Manager")
STATUSES = ("待确认", "已确认", "已发布", "已停用")
DEMO = "演示（非认可）"
BATCH_LIMIT = 50
NOTE_MIN_LENGTH = 4


def _require(*roles):
    if frappe.session.user == "Administrator":
        return
    if not set(roles).intersection(set(frappe.get_roles())):
        frappe.throw(_("没有权限执行此操作。"), frappe.PermissionError)


def _acting_role(roles=REVIEW_ROLES):
    granted = set(frappe.get_roles())
    if frappe.session.user == "Administrator":
        return "System Manager"
    for role in roles:
        if role in granted:
            return role
    return ""


def _names(names):
    if isinstance(names, str):
        names = json.loads(names)
    if not isinstance(names, list) or not names:
        frappe.throw(_("请先选择至少一条能力。"))
    clean = []
    for name in names:
        if isinstance(name, dict):
            name = name.get("name")
        if name and name not in clean:
            clean.append(name)
    if len(clean) > BATCH_LIMIT:
        frappe.throw(_("单次最多处理 {0} 条能力，当前选择了 {1} 条。请分组审核。")
                     .format(BATCH_LIMIT, len(clean)))
    return clean


def _note(note, required=True):
    text = (note or "").strip()
    if required and len(text) < NOTE_MIN_LENGTH:
        frappe.throw(_("请填写至少 {0} 个字的处理说明，作为审核留痕。").format(NOTE_MIN_LENGTH))
    return text


def _log(doc, action, before, note):
    doc.append("review_log", {
        "action": action,
        "from_status": before,
        "to_status": doc.status,
        "actor": frappe.session.user,
        "actor_role": _acting_role(),
        "at": now_datetime(),
        "note": note,
    })


def publish_blockers(doc):
    """发布前的硬性前置；返回中文原因列表，空列表表示可发布。"""
    problems = []
    scope = (doc.get("capability_scope") or "").strip()
    limitation = (doc.get("limitation") or "").strip()
    certificate = (doc.get("certificate_no") or "").strip()

    if doc.get("demo_only"):
        if doc.get("accreditation_type") != DEMO:
            problems.append("演示能力的认可类型必须为「演示（非认可）」")
        if not certificate.upper().startswith("DEMO"):
            problems.append("演示能力的证书编号必须以 DEMO 开头，避免与真实证书混淆")
    else:
        if doc.get("accreditation_type") == DEMO:
            problems.append("认可类型为「演示（非认可）」时必须勾选演示能力")
        if doc.get("accreditation_type") in ("CNAS", "CMA"):
            if not certificate:
                problems.append("CNAS/CMA 能力必须填写证书编号")
            if not doc.get("scope_effective_date"):
                problems.append("CNAS/CMA 能力必须填写范围生效日期")

    if not scope:
        problems.append("必须填写能力范围（依据条款/参数）")
    if not limitation:
        problems.append("必须填写限制或适用说明")
    if not doc.get("test_project"):
        problems.append("必须关联统一检测项目")
    if not doc.get("test_standard"):
        problems.append("必须关联检测依据")
    if not doc.get("reviewed_by"):
        problems.append("尚未经过审核，不能发布")
    if doc.get("status") != "已确认":
        problems.append("只有「已确认」的能力可以发布")
    return problems


def _row(doc):
    problems = publish_blockers(doc)
    return {
        "name": doc.name,
        "laboratory": doc.get("laboratory"),
        "test_project": doc.get("test_project"),
        "test_standard": doc.get("test_standard"),
        "test_method": doc.get("test_method"),
        "product_scope": doc.get("product_scope"),
        "capability_scope": doc.get("capability_scope"),
        "accreditation_type": doc.get("accreditation_type"),
        "certificate_no": doc.get("certificate_no"),
        "status": doc.get("status"),
        "published": bool(doc.get("published")),
        "demo_only": bool(doc.get("demo_only")),
        "reviewed_by": doc.get("reviewed_by"),
        "reviewed_on": str(doc.get("reviewed_on") or ""),
        "published_on": str(doc.get("published_on") or ""),
        "source": doc.get("source"),
        "blockers": problems,
        "publishable": not problems,
    }


@frappe.whitelist()
def filter_options():
    """筛选下拉的数据源；只返回编号与展示名，供能力中心审核台使用。"""
    frappe.has_permission("Laboratory Capability", "read", throw=True)
    laboratories = frappe.get_all("Laboratory Profile", fields=["name", "laboratory_name"],
                                  order_by="laboratory_name", limit_page_length=200)
    projects = frappe.get_all("Test Project", fields=["name", "project_name"],
                              order_by="project_name", limit_page_length=500)
    standards = frappe.get_all("Test Standard", fields=["name", "standard_code", "title"],
                               order_by="standard_code", limit_page_length=500)
    return {
        "laboratories": [{"value": row.name, "label": row.laboratory_name or row.name}
                         for row in laboratories],
        "projects": [{"value": row.name, "label": row.project_name or row.name}
                     for row in projects],
        "standards": [{"value": row.name,
                       "label": "｜".join(filter(None, [row.standard_code, row.title])) or row.name}
                      for row in standards],
    }


@frappe.whitelist()
def search(laboratory=None, test_project=None, test_standard=None, status=None,
           keyword=None, start=0, limit=50):
    """按实验室、项目、标准、状态筛选能力；默认只看待确认。"""
    frappe.has_permission("Laboratory Capability", "read", throw=True)
    filters = {}
    for field, value in (("laboratory", laboratory), ("test_project", test_project),
                         ("test_standard", test_standard), ("status", status or "待确认")):
        if value:
            filters[field] = value
    or_filters = None
    if keyword:
        like = f"%{keyword}%"
        or_filters = [["capability_scope", "like", like], ["product_scope", "like", like],
                      ["name", "like", like], ["certificate_no", "like", like]]
    limit = max(1, min(int(limit or 50), 200))
    rows = frappe.get_list("Laboratory Capability", filters=filters, or_filters=or_filters,
                           fields=["name"], order_by="modified desc",
                           limit_start=int(start or 0), limit_page_length=limit)
    docs = [frappe.get_doc("Laboratory Capability", row.name) for row in rows]
    return {
        "rows": [_row(doc) for doc in docs],
        "total": frappe.db.count("Laboratory Capability", filters),
        "batch_limit": BATCH_LIMIT,
        "status_counts": status_counts(laboratory=laboratory),
    }


def status_counts(laboratory=None):
    # Frappe v16 禁止在 fields 里传裸 SQL 聚合，这里按状态逐个计数，数据集小且可走索引。
    filters = {"laboratory": laboratory} if laboratory else {}
    result = {status: frappe.db.count("Laboratory Capability", dict(filters, status=status))
              for status in STATUSES}
    result["演示"] = frappe.db.count("Laboratory Capability", dict(filters, demo_only=1))
    return result


@frappe.whitelist()
def preview(names):
    """只做预检，不写任何数据；界面用来提前显示哪几条会被拦。"""
    frappe.has_permission("Laboratory Capability", "read", throw=True)
    result = []
    for name in _names(names):
        doc = frappe.get_doc("Laboratory Capability", name)
        doc.check_permission("read")
        result.append({"name": name, "status": doc.get("status"),
                       "blockers": publish_blockers(doc),
                       "publishable": not publish_blockers(doc)})
    return result


@frappe.whitelist(methods=["POST"])
def review(names, decision="approve", note=None):
    """批量审核：approve=待确认→已确认，return=退回补充（→待确认）。"""
    _require(*REVIEW_ROLES)
    names = _names(names)
    note = _note(note)
    if decision not in ("approve", "return"):
        frappe.throw(_("未知的审核动作。"))

    done, skipped = [], []
    for name in names:
        doc = frappe.get_doc("Laboratory Capability", name)
        doc.check_permission("read")
        before = doc.get("status")
        if decision == "approve":
            if before == "已确认":
                skipped.append({"name": name, "reason": "已是已确认"})
                continue
            if before != "待确认":
                skipped.append({"name": name, "reason": f"当前状态为「{before}」，不能审核"})
                continue
            doc.status = "已确认"
            doc.reviewed_by = frappe.session.user
            doc.reviewed_on = now_datetime()
            doc.review_note = note
            _log(doc, "审核通过", before, note)
        else:
            if before not in ("待确认", "已确认"):
                skipped.append({"name": name, "reason": f"当前状态为「{before}」，请先取消发布"})
                continue
            doc.status = "待确认"
            doc.reviewed_by = None
            doc.reviewed_on = None
            doc.review_note = note
            _log(doc, "退回补充", before, note)
        doc.save()
        done.append(name)

    frappe.db.commit()
    return {"done": done, "skipped": skipped, "note": note,
            "summary": status_counts()}


@frappe.whitelist(methods=["POST"])
def publish(names, note=None, include_demo=False):
    """批量发布：全部条目必须通过预检，任一条不通过则整批不发布。"""
    _require(*PUBLISH_ROLES)
    names = _names(names)
    note = _note(note)

    blocked = []
    for name in names:
        doc = frappe.get_doc("Laboratory Capability", name)
        doc.check_permission("read")
        problems = publish_blockers(doc)
        if doc.get("demo_only") and not include_demo:
            problems.append("演示能力需显式勾选「包含演示能力」才能发布")
        if problems:
            blocked.append({"name": name, "reasons": problems})
    if blocked:
        frappe.throw(_("有 {0} 条能力未通过发布预检，本批次未发布任何能力。").format(len(blocked))
                     + " " + "；".join(f"{row['name']}:{'、'.join(row['reasons'])}" for row in blocked))

    published = []
    for name in names:
        doc = frappe.get_doc("Laboratory Capability", name)
        before = doc.get("status")
        doc.status = "已发布"
        doc.published_by = frappe.session.user
        doc.published_on = now_datetime()
        doc.review_note = note
        _log(doc, "发布", before, note)
        doc.save()
        published.append(name)

    frappe.db.commit()
    return {"published": published, "note": note, "summary": status_counts()}


@frappe.whitelist(methods=["POST"])
def retire(names, note=None):
    """批量停用：已发布/已确认/待确认 → 已停用，用于下架过期范围。"""
    _require(*PUBLISH_ROLES)
    names = _names(names)
    note = _note(note)
    done, skipped = [], []
    for name in names:
        doc = frappe.get_doc("Laboratory Capability", name)
        doc.check_permission("read")
        before = doc.get("status")
        if before == "已停用":
            skipped.append({"name": name, "reason": "已停用"})
            continue
        doc.status = "已停用"
        doc.review_note = note
        _log(doc, "停用", before, note)
        doc.save()
        done.append(name)
    frappe.db.commit()
    return {"done": done, "skipped": skipped, "note": note,
            "summary": status_counts()}
