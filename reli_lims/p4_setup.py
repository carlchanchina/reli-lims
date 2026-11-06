"""Idempotent extensions to native commercial and asset documents."""
import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

TYPES = "\n检测服务\n普通服务\n实物商品"
TECHNICAL = {
    "custom_reli_capability": ("检测能力", "Link", "Laboratory Capability"),
    "custom_reli_test_project": ("检测项目", "Link", "Test Project"),
    "custom_reli_test_object": ("检测对象", "Link", "Test Object"),
    "custom_reli_test_standard": ("检测依据", "Link", "Test Standard"),
    "custom_reli_configuration": ("技术条件快照", "JSON", None),
}


def field(name, label, kind, options=None, **kwargs):
    return dict(fieldname=name, label=label, fieldtype=kind, options=options, **kwargs)


def after_migrate():
    fields = {"Item": [field("custom_reli_business_type", "业务分类", "Select", TYPES,
                             insert_after="item_name", in_list_view=1)],
              "Quotation Item": [field("custom_reli_business_type", "业务分类", "Select", TYPES, read_only=1, in_list_view=1)],
              "Sales Order Item": [field("custom_reli_business_type", "业务分类", "Select", TYPES, read_only=1, in_list_view=1),
                  field("custom_reli_request", "检测委托单", "Link", "Test Request", read_only=1, allow_on_submit=1),
                  field("custom_reli_split_group", "委托拆分组", "Data", description="留空归入同一委托。按实验室或履约要求填写独立组名。")],
              "Sales Order": [field("custom_reli_generation_status", "检测委托生成状态", "Select", "\n无需委托\n待生成\n已生成\n生成失败\n需人工处理", read_only=1, allow_on_submit=1),
                  field("custom_reli_generation_error", "生成错误或订单差异", "Small Text", read_only=1, allow_on_submit=1),
                  field("custom_reli_requests", "检测委托关联", "HTML")],
              "Asset": [field("custom_reli_laboratory", "所属实验室", "Link", "Laboratory Profile"),
                  field("custom_reli_model", "设备型号", "Data"),
                  field("custom_reli_serial_no", "设备序列号", "Data"),
                  field("custom_reli_parameters", "技术参数与工作范围", "Small Text"),
                  field("custom_reli_equipment_status", "实验设备状态", "Select", "\n启用\n停用\n维护"),
                  field("custom_reli_calibration_until", "校准／检定有效期", "Date"),
                  field("custom_reli_scopes", "可执行检测项目与能力", "Table", "Laboratory Equipment Scope")]}
    fields["Quotation"] = [
        field("custom_reli_customer_accepted_by", "客户接受记录", "Data", read_only=1, allow_on_submit=1, no_copy=1),
        field("custom_reli_customer_accepted_at", "客户接受时间", "Datetime", read_only=1, allow_on_submit=1, no_copy=1),
        field("custom_reli_delivery_date", "承诺交期", "Date"),
    ]
    for name, (label, kind, options) in TECHNICAL.items():
        fields["Sales Order Item"].append(field(name, label, kind, options, read_only=1))
    for doctype, anchor, names in (
        ("Sales Order", "customer", ["custom_reli_generation_status", "custom_reli_generation_error", "custom_reli_requests"]),
        ("Quotation", "valid_till", ["custom_reli_delivery_date", "custom_reli_customer_accepted_by", "custom_reli_customer_accepted_at"]),
        ("Asset", "asset_name", [f["fieldname"] for f in fields["Asset"]]),
    ):
        for name in names:
            entry = next(f for f in fields[doctype] if f["fieldname"] == name)
            entry["insert_after"] = anchor
            anchor = name
    create_custom_fields(fields, update=True)
    # Only an explicit existing unified project establishes testing-service identity.
    frappe.db.sql("""update tabItem set custom_reli_business_type='检测服务'
        where ifnull(custom_reli_business_type,'')='' and ifnull(custom_reli_test_project,'')!=''
        and is_stock_item=0 and is_sales_item=1""")
    for name in TECHNICAL:
        custom = frappe.db.get_value("Custom Field", {"dt": "Quotation Item", "fieldname": name}, "name")
        if custom:
            frappe.db.set_value("Custom Field", custom, "print_hide", 1, update_modified=False)
    from frappe.custom.doctype.property_setter.property_setter import make_property_setter
    make_property_setter("Quotation", None, "default_print_format", "Reli Customer Quotation", "Data", for_doctype=True)
    frappe.clear_cache()
