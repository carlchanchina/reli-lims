"""实验室与客户围绕同一份 Test Request 草稿共同填写。

原生 Web Form（key_required）+ 原生 Web Form Request（key / expires_on / references）
负责免登录访问、有效期与单据绑定；本模块只补充撤销、操作审计、状态机与字段保护。
"""
import base64
import binascii
import json

import frappe
from frappe import _
from frappe.rate_limiter import rate_limit
from frappe.utils import add_days, add_to_date, cint, get_datetime, now_datetime

WEB_FORM = "customer-request"
EVENT_DOCTYPE = "Test Request Share Event"
SENTINEL = "_reli_customer_share_save"
LAB_ROLES = ("Lab Manager", "Lab Engineer")

# 客户可写的草稿状态；其余状态一律由服务端拒绝写入。
CUSTOMER_WRITABLE_STATES = ("Draft", "Awaiting Customer Confirmation", "Needs Reconfirmation")
# 已提交客户确认、等待或已完成实验室审核时，客户链接只能查看不可修改。
CUSTOMER_LOCKED_STATES = ("Customer Confirmed", "Awaiting Lab Review", "Lab Reviewed")
# 实验室审核通过后才允许正式受理（提交生成正式 Test Request 关联的 Project）。
SUBMITTABLE_STATES = ("Lab Reviewed",)
LEGACY_SUBMITTABLE_STATES = ("Customer Confirmed", "Lab Reviewed")

TECHNICAL_TABLES = ("samples", "items", "sample_assignments", "photos")
# 审计只记录业务字段；框架维护的字段不进入客户可见的变更清单。
SYSTEM_FIELDS = frozenset(("name", "owner", "creation", "modified", "modified_by", "idx",
                           "docstatus", "parent", "parentfield", "parenttype"))

# 客户唯一可写的字段集合；其余表单字段（编号、单位、状态、实验室预填项）
# 一律以服务端既有值为准，客户提交内容直接丢弃。
CUSTOMER_WRITABLE_FIELDS = (
    "delivery_date", "contact_person", "contact_phone", "contact_email", "applicant_address",
    "customer_shipping_details", "samples",
    "customer_expected_tests", "customer_reference_standards", "customer_declared_conditions",
    "result_judgment", "judgment_basis", "subcontract_consent", "method_choice_consent",
    "fixture_required", "fixture_provider",
    "report_requirements", "report_format", "report_copies", "sample_return",
    "sample_handling_notes", "customer_requirements",
    "customer_declaration_confirmed", "customer_attachment",
)


def in_customer_save():
    flags = getattr(frappe, "flags", None)
    return bool(flags.get(SENTINEL)) if flags is not None else False


class customer_save:
    """仅在受 token 校验的客户保存路径中放开内部权限读取。"""

    def __enter__(self):
        frappe.flags[SENTINEL] = True
        return self

    def __exit__(self, *exc):
        frappe.flags.pop(SENTINEL, None)
        return False


def _require_lab_role():
    from reli_lims.validation import require_role
    require_role(*LAB_ROLES)


def _client_ip():
    request = getattr(frappe.local, "request", None)
    environ = getattr(request, "environ", None) or {}
    return (environ.get("HTTP_X_FORWARDED_FOR") or environ.get("REMOTE_ADDR") or "")[:64]


def log_event(test_request, event, actor_type, actor=None, changed=None, detail=None, share=None):
    frappe.get_doc({
        "doctype": EVENT_DOCTYPE,
        "test_request": test_request,
        "web_form_request": share,
        "event": event,
        "actor_type": actor_type,
        "actor": actor or (frappe.session.user if frappe.session.user != "Guest" else "客户（免登录链接）"),
        "actor_ip": _client_ip(),
        "changed_fields": json.dumps(changed or [], ensure_ascii=False),
        "detail": detail,
        "event_time": now_datetime(),
    }).insert(ignore_permissions=True)


# ---------------------------------------------------------------- 链接生命周期

def shares_for(request_name):
    """所有绑定到该委托草稿的原生 Web Form Request（含已撤销）。"""
    rows = frappe.get_all(
        "Dynamic Link",
        filters={"parenttype": "Web Form Request", "parentfield": "references",
                 "link_doctype": "Test Request", "link_name": request_name},
        fields=["parent"], limit_page_length=200,
    )
    names = [row["parent"] for row in rows]
    if not names:
        return []
    return frappe.get_all(
        "Web Form Request",
        filters={"name": ["in", names], "web_form": WEB_FORM},
        fields=["name", "key", "expires_on", "first_used_on", "reli_revoked",
                "reli_revoked_on", "reli_customer_email", "reli_use_count", "reli_last_used_on"],
        order_by="creation desc", limit_page_length=200,
    )


def has_share(request_name):
    return bool(shares_for(request_name))


def active_share(request_name):
    now = now_datetime()
    for row in shares_for(request_name):
        if cint(row.get("reli_revoked")):
            continue
        if row.get("expires_on") and get_datetime(row.get("expires_on")) <= now:
            continue
        return row
    return None


def share_url(key, request_name):
    path = f"/{WEB_FORM}/{request_name}?web_form_request_key={key}"
    try:
        return frappe.utils.get_url(path)
    except Exception:
        return path


@frappe.whitelist(methods=["POST"])
def missing_required(doc):
    """客户无法填写、但提交必填的字段；用于发送链接与确认前的拦截提示。"""
    missing = []
    for df in frappe.get_meta(doc.doctype).fields:
        if not df.reqd or df.fieldtype in ("Section Break", "Column Break", "Tab Break", "Table"):
            continue
        if df.fieldname in CUSTOMER_WRITABLE_FIELDS:
            continue
        if not doc.get(df.fieldname):
            missing.append(str(df.label or df.fieldname))
    return missing


def send_link(name, expires_days=7, customer_email=None, note=None):
    """为指定草稿生成独立、有有效期、可撤销的客户填写链接。"""
    _require_lab_role()
    days = cint(expires_days) or 7
    if not 1 <= days <= 30:
        frappe.throw(_("链接有效期必须在 1 至 30 天之间。"))
    doc = frappe.get_doc("Test Request", name, for_update=True)
    doc.check_permission("write")
    if doc.docstatus != 0:
        frappe.throw(_("只能为未正式受理的委托申请草稿发送客户填写链接。"))
    if doc.customer_confirmation_state in CUSTOMER_LOCKED_STATES:
        frappe.throw(_("客户已确认或已进入实验室审核，请先在实验室审核中退回后再重新发送。"))
    blockers = missing_required(doc)
    if blockers:
        frappe.throw(_("请先在实验室侧补齐以下必填内容，否则客户无法完成确认：") + "、".join(blockers))

    for row in shares_for(name):
        if not cint(row.get("reli_revoked")):
            _revoke_share(row["name"], "发送新链接时自动撤销")

    values = {}
    for fieldname in ("customer", "company"):
        value = doc.get(fieldname)
        if value:
            values[fieldname] = value

    share = frappe.get_doc({
        "doctype": "Web Form Request",
        "web_form": WEB_FORM,
        "expires_on": add_days(now_datetime(), days),
        "reli_customer_email": customer_email or doc.get("contact_email"),
        "references": [{"link_doctype": "Test Request", "link_name": doc.name}],
        "doc_values": json.dumps(values, ensure_ascii=False),
    })
    share.insert(ignore_permissions=True)

    from reli_lims.request_confirmation import await_customer
    if doc.customer_confirmation_state not in ("Awaiting Customer Confirmation",):
        await_customer(doc)
    log_event(doc.name, "发送客户填写链接", "实验室", changed=None, share=share.name,
              detail=f"有效期至 {share.expires_on}")
    return {
        "share": share.name,
        "key": share.key,
        "url": share_url(share.key, doc.name),
        "expires_on": str(share.expires_on),
    }


def _revoke_share(share_name, reason=None):
    share = frappe.get_doc("Web Form Request", share_name)
    share.db_set({"expires_on": now_datetime(), "reli_revoked": 1,
                  "reli_revoked_on": now_datetime(),
                  "reli_revoked_by": frappe.session.user}, update_modified=True)
    return share


@frappe.whitelist(methods=["POST"])
def revoke_link(name):
    _require_lab_role()
    doc = frappe.get_doc("Test Request", name)
    doc.check_permission("write")
    active = active_share(name)
    if not active:
        frappe.throw(_("当前没有可撤销的客户填写链接。"))
    _revoke_share(active.name, "实验室撤销")
    log_event(doc.name, "撤销客户填写链接", "实验室", share=active.name)
    return {"share": active.name}


@frappe.whitelist()
def list_links(name):
    doc = frappe.get_doc("Test Request", name)
    doc.check_permission("read")
    now = now_datetime()
    result = []
    for row in shares_for(name):
        revoked = bool(cint(row.get("reli_revoked")))
        expired = bool(row.get("expires_on") and get_datetime(row.get("expires_on")) <= now)
        result.append({
            "name": row.get("name"),
            "url": share_url(row.get("key"), name),
            "expires_on": str(row.get("expires_on") or ""),
            "revoked": revoked,
            "expired": expired,
            "used": bool(row.get("first_used_on")),
            "used_on": str(row.get("first_used_on") or ""),
            "use_count": cint(row.get("reli_use_count")),
            "status": "已撤销" if revoked else ("已过期" if expired else "可用"),
        })
    return result


# ---------------------------------------------------------------- 客户侧授权

def _find_share(key):
    if not isinstance(key, str) or not key.strip():
        frappe.throw(_("链接无效，请联系实验室重新获取。"), frappe.PermissionError)
    rows = frappe.get_all("Web Form Request", filters={"web_form": WEB_FORM, "key": key},
                          fields=["name"], limit_page_length=2)
    if len(rows) != 1:
        frappe.throw(_("链接无效，请联系实验室重新获取。"), frappe.PermissionError)
    return frappe.get_doc("Web Form Request", rows[0]["name"])


def authorize(key, request_name=None):
    """链接必须存在、未撤销、未过期，并且只绑定唯一一份委托草稿。"""
    share = _find_share(key)
    if cint(share.get("reli_revoked")):
        frappe.throw(_("该填写链接已被实验室撤销，请联系实验室重新发送。"), frappe.PermissionError)
    if share.expires_on and get_datetime(share.expires_on) <= now_datetime():
        frappe.throw(_("该填写链接已过期，请联系实验室重新发送。"), frappe.PermissionError)
    bound = [row.link_name for row in share.references]
    if len(bound) != 1 or not frappe.db.exists("Test Request", bound[0]):
        frappe.throw(_("链接无效，请联系实验室重新获取。"), frappe.PermissionError)
    if request_name and str(request_name) != str(bound[0]):
        frappe.throw(_("该链接不属于此委托申请。"), frappe.PermissionError)
    return share, bound[0]


@frappe.whitelist(allow_guest=True, methods=["POST"])
@rate_limit(key="web_form_request_key", limit=30, seconds=60)
def log_view(web_form_request_key=None):
    """客户打开链接的访问审计；同一链接 30 分钟内刷新不重复记录。"""
    share, bound = authorize(web_form_request_key)
    recent = frappe.get_all(
        EVENT_DOCTYPE,
        filters={"web_form_request": share.name, "event": "客户打开链接",
                 "event_time": [">", add_to_date(now_datetime(), minutes=-30)]},
        limit_page_length=1,
    )
    if recent:
        return {"logged": False}
    log_event(bound, "客户打开链接", "客户", share=share.name)
    return {"logged": True}


def _assert_customer_editable(doc):
    if doc.docstatus != 0:
        frappe.throw(_("该委托已正式受理，不能再修改。"))
    if doc.customer_confirmation_state in CUSTOMER_LOCKED_STATES:
        if doc.customer_confirmation_state == "Lab Reviewed":
            frappe.throw(_("实验室已审核通过本次委托，内容已锁定。如需修改请联系实验室。"))
        frappe.throw(_("您已确认本次委托，实验室审核前不能再修改。如需补充，请联系实验室退回。"))


def _next_code(prefix, used):
    index = 1
    while f"{prefix}{index}" in used:
        index += 1
    return f"{prefix}{index}"


def prepare_customer_rows(doc):
    """客户新增样品行没有内部编号时按序补号，保证原生 scope 校验可用。"""
    if not in_customer_save():
        return
    used = {row.get("sample_code") for row in doc.samples if row.get("sample_code")}
    for row in doc.samples:
        row.sample_code = (row.get("sample_code") or "").strip()
        if not row.sample_code:
            row.sample_code = _next_code("S", used)
            used.add(row.sample_code)
        for fieldname in ("product_name", "model", "customer_sample_code", "dimensions"):
            value = row.get(fieldname)
            if isinstance(value, str):
                row.set(fieldname, value.strip())
        if row.get("notes"):
            row.notes = row.notes.strip()
    if doc.get("order_scope_snapshot") and len(doc.samples) == 1 and not doc.sample_assignments:
        # One declared sample is unambiguous. Multiple samples need explicit lab allocation.
        for row in doc.items:
            doc.append("sample_assignments", {"item_code": row.item_code, "sample_code": doc.samples[0].sample_code})


def fill_new_sample_codes(data, doc):
    """客户新增行按序补号；已有行沿用原编号，避免每次保存编号漂移。"""
    rows = data.get("samples") or []
    existing = list(doc.samples or [])
    used = {row.get("sample_code") for row in existing if row.get("sample_code")}
    taken = {str(r.get("sample_code") or "").strip() for r in rows
             if str(r.get("sample_code") or "").strip()}
    for index, row in enumerate(rows):
        if str(row.get("sample_code") or "").strip():
            continue
        candidate = existing[index].get("sample_code") if index < len(existing) else None
        if candidate and candidate not in taken:
            row["sample_code"] = candidate
            taken.add(candidate)
            continue
        code = _next_code("S", used | taken)
        row["sample_code"] = code
        taken.add(code)
    return data


def customer_scope_errors(data):
    """客户保存未完成草稿时的宽松校验：只拦会破坏数据结构的输入。"""
    errors = []
    codes = [str(row.get("sample_code") or "").strip() for row in data.get("samples") or []]
    if not codes:
        errors.append("请至少填写一条样品信息。")
    if any(not code for code in codes) or len(codes) != len(set(codes)):
        errors.append("样品编号出现重复或缺失，请刷新页面后重试。")
    for row in data.get("samples") or []:
        quantity = row.get("quantity")
        if quantity in (None, ""):
            continue
        try:
            if float(quantity) <= 0:
                errors.append("样品数量必须大于 0。")
        except (TypeError, ValueError):
            errors.append("样品数量必须是数字。")
    return sorted(set(errors))


CUSTOMER_ATTACH_FIELDS = ("customer_attachment",)

# 客户上传是唯一由 Guest 触发的写文件入口，服务端必须自己兜住大小、类型与内容。
MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024
MAX_ATTACHMENTS_PER_REQUEST = 20
CUSTOMER_ATTACHMENT_PREFIX = "客户附件-"
ATTACHMENT_TYPES = {
    "image/png": ("png", (b"\x89PNG\r\n\x1a\n",)),
    "image/jpeg": ("jpg", (b"\xff\xd8\xff",)),
    "image/webp": ("webp", (b"RIFF",)),
    "application/pdf": ("pdf", (b"%PDF-",)),
}


def _attachment_error(message):
    frappe.throw(_(message))


def decode_attachment(value):
    """校验并解码客户提交的 base64 附件，返回 (bytes, 扩展名)。

    不信任浏览器给的文件名与 MIME：扩展名由服务端按 MIME 决定，内容必须匹配
    文件头，大小不得超过 10MB，空文件直接拒绝。
    """
    header, _, encoded = value.partition(",")
    if not header.startswith("data:") or ";base64" not in header or not encoded:
        _attachment_error("附件格式无效，请重新上传图片或 PDF。")
    mime = header[5:].split(";", 1)[0].strip().lower()
    if mime not in ATTACHMENT_TYPES:
        _attachment_error("附件只支持 PNG、JPG、WEBP 图片或 PDF 文件。")
    try:
        payload = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError):
        _attachment_error("附件内容已损坏，请重新上传。")
    if not payload:
        _attachment_error("附件内容为空，请重新上传。")
    if len(payload) > MAX_ATTACHMENT_BYTES:
        _attachment_error("附件超过 10MB 上限，请压缩后重新上传。")
    extension, signatures = ATTACHMENT_TYPES[mime]
    if not any(payload.startswith(signature) for signature in signatures):
        _attachment_error("附件内容与文件类型不符，请重新上传。")
    if extension == "webp" and payload[8:12] != b"WEBP":
        _attachment_error("附件内容与文件类型不符，请重新上传。")
    return payload, extension


def _customer_attachment_count(doc):
    return cint(frappe.db.count("File", {
        "attached_to_doctype": "Test Request", "attached_to_name": doc.name,
        "file_name": ["like", f"{CUSTOMER_ATTACHMENT_PREFIX}%"],
    }))


def prepare_attachments(payload, doc):
    """把客户上传的 data URL 提前落盘为私有文件。

    原生 Web Form 在 Guest 会话下保存 File 会触发角色权限校验，这里先用受控
    权限写入附件，再把 file_url 交给原生流程，避免客户看到 403。
    """
    for fieldname in CUSTOMER_ATTACH_FIELDS:
        value = payload.get(fieldname)
        if not isinstance(value, str) or "base64" not in value or "," not in value:
            continue
        if _customer_attachment_count(doc) >= MAX_ATTACHMENTS_PER_REQUEST:
            _attachment_error("本委托的客户附件数量已达上限，请联系实验室整理后再上传。")
        content, extension = decode_attachment(value)
        filename = f"{CUSTOMER_ATTACHMENT_PREFIX}{doc.name}-{now_datetime():%Y%m%d%H%M%S}.{extension}"
        from frappe.utils.file_manager import save_file
        previous = frappe.flags.get("ignore_permissions")
        frappe.flags.ignore_permissions = True
        try:
            file_doc = save_file(filename, content, "Test Request", doc.name,
                                 is_private=1, decode=False)
        finally:
            frappe.flags.ignore_permissions = previous
        payload[fieldname] = file_doc.file_url
    return payload


def sanitize_payload(payload, doc):
    """按白名单裁剪提交内容；未授权字段用服务端现值回填。

    原生 Web Form 保存时会遍历全部表单字段逐个 doc.set()，缺失即写空。
    因此在交给原生 accept 之前，先把非白名单字段补成既有值，既避免只读字段被
    客户清空，也让客户提交的任何内部字段在源头失效。
    """
    form = frappe.get_doc("Web Form", WEB_FORM)
    meta = frappe.get_meta(doc.doctype)
    clean = {"name": doc.name}
    for row in form.web_form_fields:
        fieldname = row.fieldname
        if not fieldname:
            continue
        if fieldname in CUSTOMER_WRITABLE_FIELDS and fieldname in payload:
            clean[fieldname] = payload[fieldname]
        elif fieldname == "samples":
            clean[fieldname] = [item.as_dict() for item in (doc.get("samples") or [])]
        elif meta.has_field(fieldname):
            clean[fieldname] = doc.get(fieldname)
    return clean


# ---------------------------------------------------------------- 保存与确认

@frappe.whitelist(allow_guest=True, methods=["POST", "PUT"])
@rate_limit(key="web_form_request_key", limit=10, seconds=60)
def accept(web_form, data, web_form_request_key=None):
    """覆盖原生 accept：仅对本功能表单增加撤销/状态/审计/编号保护。"""
    from frappe.website.doctype.web_form import web_form as native

    if web_form != WEB_FORM:
        return native.accept(web_form, data, web_form_request_key)

    payload = json.loads(data) if isinstance(data, str) else dict(data)
    docname = payload.get("name")
    if not docname:
        frappe.throw(_("客户链接只能修改已存在的委托申请草稿。"), frappe.PermissionError)
    share, bound = authorize(web_form_request_key, docname)

    doc = frappe.get_doc("Test Request", bound, for_update=True)
    _assert_customer_editable(doc)
    before = snapshot(doc)

    payload = fill_new_sample_codes(payload, doc)
    errors = customer_scope_errors(payload)
    if errors:
        frappe.throw(" ".join(errors))

    payload = sanitize_payload(payload, doc)
    payload = prepare_attachments(payload, doc)

    with customer_save():
        result = native.accept(web_form, json.dumps(payload, ensure_ascii=False), web_form_request_key)

    after = frappe.get_doc("Test Request", bound)
    changed = diff(before, snapshot(after))
    share.db_set({"reli_use_count": cint(share.get("reli_use_count")) + 1,
                  "reli_last_used_on": now_datetime()}, update_modified=False)
    if after.customer_confirmation_state in ("Awaiting Customer Confirmation", "Needs Reconfirmation") \
            and after.get("customer_confirmation_fingerprint"):
        log_event(bound, "客户保存（需重新确认）", "客户", changed=changed, share=share.name)
    else:
        log_event(bound, "客户保存", "客户", changed=changed, share=share.name)
    return result


def snapshot(doc):
    meta = frappe.get_meta("Test Request")
    fields = [df.fieldname for df in meta.fields
              if df.fieldtype not in ("Section Break", "Column Break", "Tab Break", "Table", "HTML", "Button")
              and not df.fieldname.startswith("__")]
    data = {fieldname: doc.get(fieldname) for fieldname in fields}
    for table in TECHNICAL_TABLES:
        data[table] = [dict(row.as_dict()) for row in (doc.get(table) or [])]
    return data


def _normalize(value):
    if isinstance(value, float):
        return round(value, 6)
    if isinstance(value, int) and not isinstance(value, bool):
        return float(value)
    return "" if value is None else str(value)


def diff(before, after):
    meta = frappe.get_meta("Test Request")
    labels = {df.fieldname: _(df.label) for df in meta.fields if df.label}
    changed = []
    for fieldname, label in labels.items():
        if fieldname in TECHNICAL_TABLES or fieldname in SYSTEM_FIELDS:
            continue
        if _normalize(before.get(fieldname)) != _normalize(after.get(fieldname)):
            changed.append(label)
    for table in TECHNICAL_TABLES:
        old_rows, new_rows = before.get(table) or [], after.get(table) or []
        if len(old_rows) != len(new_rows):
            changed.append(f"{labels.get(table, table)}（行数 {len(old_rows)} → {len(new_rows)}）")
            continue
        for index, (old, new) in enumerate(zip(old_rows, new_rows), start=1):
            keys = {key for key in set(old) | set(new) if key not in ("name", "idx")}
            touched = [key for key in keys
                       if not key.startswith("_") and key not in SYSTEM_FIELDS
                       and _normalize(old.get(key)) != _normalize(new.get(key))]
            for key in sorted(touched):
                changed.append(f"{labels.get(table, table)} 第{index}行 · {_field_label(table, key)}")
    return sorted(set(changed))


def _field_label(table, fieldname):
    for df in frappe.get_meta(doctype_for(table)).fields:
        if df.fieldname == fieldname:
            return _(df.label or fieldname)
    return fieldname


def doctype_for(table):
    return {"samples": "Test Request Sample", "items": "Test Request Item",
            "sample_assignments": "Test Request Item Sample",
            "photos": "Test Request Photo"}[table]


@frappe.whitelist(allow_guest=True, methods=["POST"])
def customer_confirm(web_form_request_key, declaration=None):
    """客户在免登录页面确认；确认后进入实验室审核，不再允许客户修改。"""
    share, bound = authorize(web_form_request_key)
    doc = frappe.get_doc("Test Request", bound, for_update=True)
    if doc.docstatus != 0:
        frappe.throw(_("该委托已正式受理，无需再次确认。"))
    if doc.customer_confirmation_state in ("Awaiting Lab Review", "Lab Reviewed"):
        frappe.throw(_("本次委托已确认，正在等待实验室审核。"))
    if not cint(doc.get("customer_declaration_confirmed")):
        frappe.throw(_("请先勾选“我确认以上信息真实完整”。"))

    blockers = missing_required(doc)
    if blockers:
        frappe.throw(_("以下内容需要实验室补充后才能确认，请联系实验室：") + "、".join(blockers))

    from reli_lims.request_confirmation import (confirm, confirmation_blockers,
                                                current_fingerprint)
    blockers = confirmation_blockers(doc)
    if blockers:
        frappe.throw(_("请先补齐必填内容后再确认：") + "、".join(blockers))

    receipt = {
        "fingerprint": current_fingerprint(doc),
        "confirmed_by": share.get("reli_customer_email") or f"客户链接 {share.key[:8]}",
        "confirmed_at": now_datetime(),
    }
    with customer_save():
        confirm(doc, receipt)
        doc.reload()
        doc.customer_confirmation_state = "Awaiting Lab Review"
        doc.flags._reli_customer_confirmation_mutation = _mutation_token()
        try:
            doc.save(ignore_permissions=True)
        finally:
            doc.flags.pop("_reli_customer_confirmation_mutation", None)

    log_event(bound, "客户确认提交", "客户", share=share.name,
              detail=f"确认人：{receipt['confirmed_by']}")
    return {"state": doc.customer_confirmation_state, "confirmed_at": str(receipt["confirmed_at"])}


def _mutation_token():
    from reli_lims.request_confirmation import _MUTATION
    return _MUTATION


# ---------------------------------------------------------------- 实验室审核

@frappe.whitelist(methods=["POST"])
def lab_review(name, approve=1, note=None):
    _require_lab_role()
    doc = frappe.get_doc("Test Request", name, for_update=True)
    doc.check_permission("write")
    if doc.docstatus != 0:
        frappe.throw(_("只能审核未正式受理的委托申请草稿。"))
    if doc.customer_confirmation_state != "Awaiting Lab Review":
        frappe.throw(_("当前委托不在待实验室审核状态。"))
    from reli_lims.request_confirmation import current_fingerprint
    if doc.get("customer_confirmation_fingerprint") and \
            current_fingerprint(doc) != doc.customer_confirmation_fingerprint:
        frappe.throw(_("客户确认后技术内容已变化，请客户重新确认。"))

    approved = bool(cint(approve))
    doc.customer_confirmation_state = "Lab Reviewed" if approved else "Awaiting Customer Confirmation"
    doc.lab_reviewed_by = frappe.session.user
    doc.lab_reviewed_at = now_datetime()
    if note:
        doc.engineering_review_notes = str(note)[:2000]
    doc.flags._reli_customer_confirmation_mutation = _mutation_token()
    try:
        doc.save(ignore_permissions=True)
    finally:
        doc.flags.pop("_reli_customer_confirmation_mutation", None)
    log_event(doc.name, "实验室审核通过" if approved else "实验室退回补充", "实验室",
              detail=note)
    return {"state": doc.customer_confirmation_state}


def prevent_linked_trash(doc, method=None):
    """已生成客户链接的委托草稿必须保留审计轨迹，不允许直接删除。"""
    if shares_for(doc.name):
        frappe.throw(_("该委托已有客户填写链接与操作记录，不能删除。"))
