import json

import frappe


DEMO_SELLER_ID = "sel_demo_reliability_lab"
DEMO_LAB_NAME = "苏州可靠性检测实验室"


def _get_or_create(doctype, filters, values):
    name = frappe.db.get_value(doctype, filters, "name")
    if name:
        return name
    doc = frappe.get_doc({"doctype": doctype, **values})
    doc.insert(ignore_permissions=True)
    return doc.name


def seed_demo_capabilities():
    lab = _get_or_create(
        "Laboratory Profile",
        {"mercur_seller_id": DEMO_SELLER_ID},
        {
            "mercur_seller_id": DEMO_SELLER_ID,
            "laboratory_name": DEMO_LAB_NAME,
            "review_status": "Approved",
        },
    )

    low_temp = _get_or_create(
        "Test Method",
        {"method_name": "低温试验"},
        {"method_name": "低温试验", "category": "气候环境", "active": 1},
    )
    low_temp_std = _get_or_create(
        "Test Standard",
        {"standard_code": "GB/T 2423.1-2008"},
        {
            "standard_code": "GB/T 2423.1-2008",
            "title": "电工电子产品环境试验 第2部分：试验方法 试验A：低温",
            "version": "2008",
            "status": "Active",
        },
    )

    vibration = _get_or_create(
        "Test Method",
        {"method_name": "随机振动试验"},
        {"method_name": "随机振动试验", "category": "力学环境", "active": 1},
    )
    vibration_std = _get_or_create(
        "Test Standard",
        {"standard_code": "GB/T 2423.56-2023"},
        {
            "standard_code": "GB/T 2423.56-2023",
            "title": "环境试验 第2部分：试验方法 试验Fh：宽带随机振动和导则",
            "version": "2023",
            "status": "Active",
        },
    )

    source = _get_or_create(
        "Capability Source",
        {"documents_source_id": "demo-doc-cnas-001"},
        {
            "laboratory": lab,
            "source_type": "其他",
            "certificate_no": "",
            "documents_source_id": "demo-doc-cnas-001",
            "documents_version": "1",
            "documents_review_status": "Approved",
            "source_file_url": "wekona_documents://demo-doc-cnas-001/v1",
            "structured_json": json.dumps({"items": [
                {
                    "test_method": "低温试验",
                    "standard_code": "GB/T 2423.1-2008",
                    "capability_scope": "-40 ℃ ～ 常温",
                    "accreditation_type": "未认证",
                    "source_row": "1",
                },
                {
                    "test_method": "随机振动试验",
                    "standard_code": "GB/T 2423.56-2023",
                    "capability_scope": "5 Hz ～ 2000 Hz",
                    "accreditation_type": "未认证",
                    "source_row": "2",
                },
            ]}, ensure_ascii=False),
            "remarks": "仅测试数据，不代表真实资质或认可。",
            "import_status": "待导入",
        },
    )

    _get_or_create(
        "Laboratory Capability",
        {"laboratory": lab, "source": source, "source_row": "1"},
        {
            "laboratory": lab,
            "test_method": low_temp,
            "test_standard": low_temp_std,
            "capability_scope": "-40 ℃ ～ 常温",
            "accreditation_type": "未认证",
            "certificate_no": "",
            "source": source,
            "source_row": "1",
            "status": "待确认",
        },
    )
    _get_or_create(
        "Laboratory Capability",
        {"laboratory": lab, "source": source, "source_row": "2"},
        {
            "laboratory": lab,
            "test_method": vibration,
            "test_standard": vibration_std,
            "capability_scope": "5 Hz ～ 2000 Hz",
            "accreditation_type": "未认证",
            "certificate_no": "",
            "source": source,
            "source_row": "2",
            "status": "待确认",
        },
    )

    return {"laboratory": lab, "source": source}
