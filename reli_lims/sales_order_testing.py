"""Native Sales Order → recoverable, idempotent testing-request drafts."""
from copy import deepcopy
import hashlib
import json

import frappe
from frappe.utils import today, flt

from reli_lims.p4_setup import TECHNICAL

TESTING = "检测服务"


def item_type(item):
    kind = item.get("custom_reli_business_type")
    if kind:
        return kind
    if item.get("custom_reli_test_project") and not item.is_stock_item:
        return TESTING
    return "实物商品" if item.is_stock_item else "普通服务"


def validate_item(doc, method=None):
    kind = doc.get("custom_reli_business_type")
    if kind == TESTING and (doc.is_stock_item or not doc.is_sales_item or not doc.get("custom_reli_test_project")):
        frappe.throw("检测服务必须为非库存销售商品，并关联统一检测项目。")


def validate_lines(doc, method=None):
    if doc.doctype == "Sales Order" and doc.docstatus != 2:
        from reli_lims.quotation_origin import validate_order_capacity
        validate_order_capacity(doc)
    previous = doc.get_doc_before_save()
    if doc.doctype == "Quotation":
        for key in ("custom_reli_customer_accepted_by", "custom_reli_customer_accepted_at"):
            if str(doc.get(key) or "") != str((previous.get(key) if previous else None) or ""):
                frappe.throw("客户接受记录须通过授权业务操作登记。")
    old = {row.name: row for row in previous.items} if previous else {}
    for row in doc.items:
        item = frappe.get_doc("Item", row.item_code)
        stored = old.get(row.name)
        # Submitted line identity remains the commercial fact even if the master changes.
        kind = stored.get("custom_reli_business_type") if stored and previous.docstatus == 1 else item_type(item)
        row.custom_reli_business_type = kind
        if kind != TESTING:
            if row.get("custom_reli_capability") or row.get("custom_reli_configuration"):
                frappe.throw("普通服务或实物商品不能带有检测能力快照，请核对商品分类。")
            continue
        row.item_name = item.item_name
        if doc.doctype == "Sales Order" and row.quotation_item:
            source = frappe.db.get_value("Quotation Item", row.quotation_item,
                ["parent", "item_code", *TECHNICAL], as_dict=True)
            if not source or source.parent != row.prevdoc_docname or source.item_code != row.item_code:
                frappe.throw("来源报价行与订单商品不一致。")
            quote = frappe.db.get_value("Quotation", source.parent,
                ["party_name", "company", "docstatus"], as_dict=True)
            expected_customer = quotation_customer(source.parent)
            if (not quote or quote.docstatus != 1 or not expected_customer
                    or expected_customer != doc.customer or quote.company != doc.company):
                frappe.throw("来源报价必须已提交且客户、公司一致。")
            if doc.docstatus == 1 and not frappe.db.get_value("Quotation", source.parent, "custom_reli_customer_accepted_at"):
                frappe.throw("请先记录来源报价的客户接受结果，再提交销售订单。")
            if not stored or stored.quotation_item != row.quotation_item:
                for key in TECHNICAL:
                    row.set(key, source.get(key))
            # 原生 make_sales_order 只复制同名字段；若上游把快照字段漏掉，这里必须报错而不是静默丢技术条件。
            if source.get("custom_reli_configuration") and not row.get("custom_reli_configuration"):
                frappe.throw("订单行丢失来源报价的技术条件快照，请重新从报价创建订单。")
        if not row.get("custom_reli_test_project"):
            row.custom_reli_test_project = item.custom_reli_test_project
        if row.custom_reli_test_project != item.custom_reli_test_project:
            frappe.throw("检测服务商品与检测项目不一致。")
        config = frappe.parse_json(row.get("custom_reli_configuration"))
        if config:
            snapshot = config.get("snapshot") or {}
            if config.get("capability_id") != row.get("custom_reli_capability"):
                frappe.throw("订单检测能力与技术快照不一致。")
            for field, snapshot_field in (("custom_reli_test_project", "test_project"),
                    ("custom_reli_test_object", "test_object"), ("custom_reli_test_standard", "test_standard")):
                if row.get(field) != snapshot.get(snapshot_field):
                    frappe.throw("订单检测项目、对象或依据与快照不一致。")
        if doc.doctype == "Sales Order" and not doc.docstatus:
            row.custom_reli_request = None
    if doc.doctype == "Sales Order" and not doc.docstatus:
        doc.custom_reli_generation_status = "待生成" if any(r.custom_reli_business_type == TESTING for r in doc.items) else "无需委托"


def quotation_customer(name):
    """Resolve the ERPNext customer behind a quotation, including CRM-origin ones.

    Frappe CRM creates quotations with ``quotation_to = "CRM Deal"``, so
    ``party_name`` is a deal and ``Quotation.customer`` does not exist. The
    resolution itself lives in :mod:`reli_lims.quotation_origin` so the lab
    intake, the sales order and the request validation share one answer.
    """
    from reli_lims.quotation_origin import quotation_customer as resolve

    return resolve(name)


@frappe.whitelist()
def resolve_quotation_customer(name):
    """Used by the native Sales Order form to prefill the mapped customer."""
    return quotation_customer(name)


def inherit_quotation_terms(doc, method=None):
    """Carry the promised delivery date from source quotations into the native order.

    ERPNext's ``make_sales_order`` only copies same-named fields, and a Quotation has no
    ``delivery_date``, so 承诺交期 would silently disappear on every native conversion.
    """
    if doc.doctype != "Sales Order" or doc.docstatus:
        return
    sources = sorted({row.prevdoc_docname for row in doc.items if row.prevdoc_docname})
    if not sources:
        return
    promised = [date for date in (
        frappe.db.get_value("Quotation", name, "custom_reli_delivery_date") for name in sources
    ) if date]
    if promised and not doc.delivery_date:
        doc.delivery_date = min(promised)
    if doc.delivery_date:
        for row in doc.items:
            if not row.delivery_date:
                row.delivery_date = doc.delivery_date


def order_scope(order):
    return {"customer": order.customer, "company": order.company,
        "delivery_date": str(order.delivery_date or ""),
        "items": [{"name": r.name, "item_code": r.item_code, "qty": flt(r.qty),
            "returned_qty": flt(r.returned_qty), "group": r.get("custom_reli_split_group") or "",
            "quotation": r.prevdoc_docname, "quotation_item": r.quotation_item,
            "type": r.custom_reli_business_type,
            **{key: frappe.parse_json(r.get(key)) if key == "custom_reli_configuration" else r.get(key) for key in TECHNICAL}}
            for r in order.items if r.custom_reli_business_type == TESTING]}


def scope_hash(scope):
    return hashlib.sha256(json.dumps(scope, sort_keys=True, default=str, ensure_ascii=False).encode()).hexdigest()


def validate_order_draft(doc):
    """Allow missing samples/technical scope only for traceable order drafts."""
    if not doc.get("sales_order") or doc.docstatus:
        return False
    if not doc.items or len({row.item_code for row in doc.items}) != len(doc.items):
        frappe.throw("订单委托草稿须保留唯一检测行编号。")
    if any(not row.item_code or flt(row.requested_quantity) <= 0 for row in doc.items):
        frappe.throw("订单委托草稿的服务数量必须大于零。")
    return True


def validate_request_source(doc, method=None):
    previous = doc.get_doc_before_save()
    if previous and (doc.sales_order != previous.sales_order or
            frappe.parse_json(doc.order_scope_snapshot) != frappe.parse_json(previous.order_scope_snapshot)):
        frappe.throw("订单来源和原始范围快照不能修改。")
    sourced = [r for r in doc.items if r.get("source_sales_order_item")]
    if previous and previous.get("order_scope_snapshot"):
        old_sources = {r.source_sales_order_item for r in previous.items}
        if {r.source_sales_order_item for r in doc.items} != old_sources:
            frappe.throw("订单生成的委托须保留原订单行，拆分请在订单提交前设置委托拆分组。")
    if not sourced and not doc.get("order_scope_snapshot"):
        return
    if not doc.sales_order:
        frappe.throw("订单来源行必须保留销售订单。")
    frappe.db.get_value("Sales Order", doc.sales_order, "name", for_update=True)
    order = frappe.get_doc("Sales Order", doc.sales_order)
    if order.docstatus != 1 or order.customer != doc.customer or order.company != doc.company:
        frappe.throw("订单来源已失效或与委托客户、公司不一致。")
    rows = {r.name: r for r in order.items}
    if not previous and doc.get("order_scope_snapshot") and scope_hash(frappe.parse_json(doc.order_scope_snapshot)) != scope_hash(order_scope(order)):
        frappe.throw("新委托的订单范围快照与来源不一致。")
    seen = set()
    for row in sourced:
        source = rows.get(row.source_sales_order_item)
        if not source or source.custom_reli_business_type != TESTING or row.service_item != source.item_code:
            frappe.throw("委托只能引用当前订单的检测服务行。")
        if row.source_quotation != source.prevdoc_docname or row.source_quotation_item != source.quotation_item:
            frappe.throw("委托报价来源必须与订单行一致。")
        if row.source_sales_order_item in seen:
            frappe.throw("同一订单行不能在委托内重复。")
        other = frappe.db.sql("""select i.parent from `tabTest Request Item` i
            join `tabTest Request` r on r.name=i.parent
            where r.sales_order=%s and i.source_sales_order_item=%s and i.parent!=%s limit 1""",
            (doc.sales_order, row.source_sales_order_item, doc.name))
        if other:
            frappe.throw("此订单行已关联另一委托，不能重复生成。")
        seen.add(row.source_sales_order_item)
    original = frappe.parse_json(doc.get("order_scope_snapshot"))
    changed = original and scope_hash(original) != scope_hash(order_scope(order))
    doc.order_difference = "订单数量、技术范围、交期或退货已变化，请核对并重新确认。" if changed else ""
    if doc.docstatus == 1 and changed:
        frappe.throw(doc.order_difference)
    if doc.get("order_scope_snapshot") and doc.docstatus == 1:
        if len(sourced) != len(doc.items):
            frappe.throw("订单委托不能加入无订单来源的检测行。")
        if any(flt(r.requested_quantity) != flt(rows[r.source_sales_order_item].qty) for r in sourced):
            frappe.throw("委托服务数量与订单不一致，请先处理商业差异。")


def generate(order):
    from reli_lims.capability_request import to_request_item
    scope = order_scope(order)
    candidates = [r for r in order.items if r.custom_reli_business_type == TESTING]
    if not candidates:
        order.db_set("custom_reli_generation_status", "无需委托", update_modified=False)
        return []
    existing = frappe.get_all("Test Request", filters={"sales_order": order.name}, pluck="name")
    if existing:
        linked = frappe.get_all("Test Request Item", filters={"parent": ["in", existing]}, pluck="source_sales_order_item")
        if set(linked) != {r.name for r in candidates}:
            frappe.throw("已有委托范围与订单不同，请人工处理差异，禁止重复生成。")
        for name in existing:
            request = frappe.get_doc("Test Request", name)
            if scope_hash(frappe.parse_json(request.order_scope_snapshot)) != scope_hash(scope):
                frappe.throw("已有委托与订单存在差异，请人工核对。")
        return existing
    if order.amended_from and frappe.db.exists("Test Request", {"sales_order": order.amended_from}):
        frappe.throw("原订单已有检测委托，修订订单须先人工处理原委托，禁止自动重复履约。")
    groups = {}
    for row in candidates:
        groups.setdefault(row.get("custom_reli_split_group") or "默认", []).append(row)
    names = []
    for group, rows in groups.items():
        quotations = {r.prevdoc_docname for r in rows if r.prevdoc_docname}
        request = frappe.get_doc(dict(doctype="Test Request", title=f"检测服务委托 · {order.name} · {group}",
            customer=order.customer, company=order.company, sales_order=order.name,
            quotation=next(iter(quotations)) if len(quotations) == 1 else None,
            request_date=today(), delivery_date=order.delivery_date or today(),
            customer_expected_tests="、".join(r.item_name for r in rows),
            order_scope_snapshot=scope, items=[]))
        for i, row in enumerate(rows, 1):
            config = frappe.parse_json(row.get("custom_reli_configuration"))
            values = to_request_item(deepcopy(config)) if config else dict(
                test_project=row.custom_reli_test_project, test_object=row.custom_reli_test_object,
                standard=row.custom_reli_test_standard)
            request.append("items", dict(values, item_code=f"T{i:03d}", service_item=row.item_code,
                source_sales_order_item=row.name, source_quotation=row.prevdoc_docname,
                source_quotation_item=row.quotation_item,
                requested_quantity=row.qty))
        # Internal automation is bounded by a locked, submitted order and its testing lines.
        request.insert(ignore_permissions=True)
        names.append(request.name)
        for row in rows:
            frappe.db.set_value("Sales Order Item", row.name, "custom_reli_request", request.name, update_modified=False)
    return names


def process(order):
    frappe.db.savepoint("reli_order_requests")
    try:
        names = generate(order)
        order.db_set({"custom_reli_generation_status": "已生成" if names else "无需委托",
                      "custom_reli_generation_error": ""}, update_modified=False)
        return names
    except Exception:
        frappe.db.rollback(save_point="reli_order_requests")
        error = frappe.log_error(title=f"检测委托生成失败 {order.name}", message=frappe.get_traceback())
        order.db_set({"custom_reli_generation_status": "生成失败",
            "custom_reli_generation_error": f"自动生成失败，请修正后重试。错误记录 {error.name}"}, update_modified=False)
        return []


def on_submit(doc, method=None):
    process(doc)


@frappe.whitelist(methods=["POST"])
def prepare_lines(selections):
    """直接开单：把选中的检测能力转成销售订单行，等价于报价单的“选择检测服务”。"""
    from reli_lims.capability_quotation import description, service_item
    from reli_lims.capability_selection import build_configuration

    if not (frappe.has_permission("Sales Order", "create") or frappe.has_permission("Sales Order", "write")):
        frappe.throw("没有销售订单权限。", frappe.PermissionError)
    selections = frappe.parse_json(selections)
    if not isinstance(selections, list) or not 1 <= len(selections) <= 30:
        frappe.throw("请一次选择 1 至 30 条能力。")
    result = []
    for selection in selections:
        config = build_configuration(selection["capability_id"], selection.get("conditions", {}), "sales_order")
        capability = frappe.get_doc("Laboratory Capability", config["capability_id"])
        item = service_item(capability, selection.get("item_code"))
        project = capability.test_project
        result.append({
            "item_code": item.name,
            "item_name": frappe.db.get_value("Test Project", project, "project_name"),
            "uom": item.stock_uom,
            "description": description(config),
            "qty": 1,
            "conversion_factor": 1,
            "custom_reli_business_type": TESTING,
            "custom_reli_capability": capability.name,
            "custom_reli_test_project": project,
            "custom_reli_test_object": capability.test_object,
            "custom_reli_test_standard": capability.test_standard,
            "custom_reli_configuration": config,
        })
    return result


@frappe.whitelist(methods=["POST"])
def retry(name):
    order = frappe.get_doc("Sales Order", name, for_update=True)
    order.check_permission("write")
    if order.docstatus != 1:
        frappe.throw("请先正式提交销售订单。")
    return process(order)


@frappe.whitelist()
def requests(name):
    order = frappe.get_doc("Sales Order", name)
    order.check_permission("read")
    rows = frappe.get_list("Test Request", filters={"sales_order": name},
        fields=["name", "title", "docstatus", "business_stage", "order_difference", "order_scope_snapshot"], page_length=100)
    for row in rows:
        original = frappe.parse_json(row.pop("order_scope_snapshot", None))
        if original and scope_hash(original) != scope_hash(order_scope(order)):
            row.order_difference = "订单范围或数量已变化，请人工核对委托。"
    return rows


def changed(doc, method=None):
    names = frappe.get_all("Test Request", filters={"sales_order": doc.name}, pluck="name")
    if not names:
        return
    difference = "订单已取消，请人工处理关联委托。" if doc.docstatus == 2 else ""
    for name in names:
        snapshot = frappe.parse_json(frappe.db.get_value("Test Request", name, "order_scope_snapshot"))
        if not snapshot or scope_hash(snapshot) != scope_hash(order_scope(doc)):
            difference = "订单数量、技术范围、交期或退货已变化，请人工处理关联委托。"
        frappe.db.set_value("Test Request", name, "order_difference", difference, update_modified=False)
    if difference:
        doc.db_set({"custom_reli_generation_status": "需人工处理", "custom_reli_generation_error": difference}, update_modified=False)
        frappe.msgprint(difference)


def before_cancel(doc, method=None):
    if frappe.db.exists("Test Request", {"sales_order": doc.name}):
        frappe.throw("订单已有检测委托，请先处理委托取消或变更，不允许静默取消商业来源。")


@frappe.whitelist(methods=["POST"])
def accept_quotation(name, customer_contact):
    quote = frappe.get_doc("Quotation", name, for_update=True)
    quote.check_permission("write")
    return record_customer_acceptance(quote, customer_contact)


def record_customer_acceptance(quote, customer_contact):
    """Internal business operation. Callers establish document write or Bridge scope."""
    name = quote.name
    customer = quotation_customer(name)
    if (quote.docstatus != 1 or quote.quotation_to not in ("Customer", "CRM Deal") or not customer
            or quote.status in ("Lost", "Cancelled", "Expired", "Closed")):
        frappe.throw("请先提交有效客户报价。")
    if quote.valid_till and str(quote.valid_till) < today():
        frappe.throw("报价已过有效期。")
    if not str(customer_contact or "").strip():
        frappe.throw("请填写客户接受人或接受凭据说明。")
    if not quote.custom_reli_customer_accepted_at:
        quote.db_set({"custom_reli_customer_accepted_by": str(customer_contact).strip()[:140],
                      "custom_reli_customer_accepted_at": frappe.utils.now_datetime()})
        quote.add_comment("Info", "客户接受报价，登记人 " + frappe.session.user)
    return quote.name


def commercial_return_changed(doc, method=None):
    names = {row.get("sales_order") or row.get("against_sales_order") for row in doc.items}
    for name in sorted(filter(None, names)):
        if frappe.db.exists("Test Request", {"sales_order": name}):
            changed(frappe.get_doc("Sales Order", name))


def reconcile_orders():
    names = frappe.get_all("Test Request", filters={"sales_order": ["is", "set"], "order_scope_snapshot": ["is", "set"]}, pluck="sales_order")
    for name in sorted(set(names)):
        changed(frappe.get_doc("Sales Order", name))
