"""Idempotent additions to native Test Request; no parallel business DocType."""
FIELDS = [
 {'fieldname':'customer_requirements','label':'客户需求说明','fieldtype':'Small Text'},
 {'fieldname':'customer_expected_tests','label':'客户期望检测项目','fieldtype':'Small Text'},
 {'fieldname':'customer_reference_standards','label':'客户参考标准','fieldtype':'Small Text'},
 {'fieldname':'customer_declared_conditions','label':'客户声明试验条件','fieldtype':'Small Text'},
 {'fieldname':'customer_shipping_details','label':'客户送样信息','fieldtype':'Small Text'},
 {'fieldname':'execution_company','label':'执行公司','fieldtype':'Link','options':'Company'},
 {'fieldname':'lab_intake_notes','label':'受理信息','fieldtype':'Small Text'},
 {'fieldname':'customer_confirmation_state','label':'客户确认状态','fieldtype':'Select','options':'Draft\nAwaiting Customer Confirmation\nCustomer Confirmed\nNeeds Reconfirmation\nAccepted','default':'Draft','read_only':1},
 {'fieldname':'customer_confirmed_by','label':'客户确认人','fieldtype':'Data','read_only':1},
 {'fieldname':'customer_confirmed_at','label':'客户确认时间','fieldtype':'Datetime','read_only':1},
 {'fieldname':'customer_confirmation_fingerprint','label':'客户确认版本','fieldtype':'Data','read_only':1},
]

def after_migrate():
    from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
    create_custom_fields({'Test Request':[dict(field,insert_after='report_requirements') for field in FIELDS],
        'File':[{'fieldname':'reli_customer_visible','label':'客户可见委托附件','fieldtype':'Check','default':'0','read_only':1}]},update=True)
