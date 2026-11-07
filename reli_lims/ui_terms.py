"""站点级中文术语收敛。

Frappe 核心/ERPNext 自带的中文词典会覆盖应用翻译，例如把检测执行里的
Completed 译成"成功"、Running 译成"运行中"。这里用站点级 Translation 记录
覆盖少量与检测业务直接相关的词，保证界面口径统一。
"""
import frappe

UI_TERMS = {
    "Completed": "已完成",
    "Running": "执行中",
}


def after_migrate():
    for source, translated in UI_TERMS.items():
        name = frappe.db.get_value("Translation", {"language": "zh", "source_text": source})
        if name:
            if frappe.db.get_value("Translation", name, "translated_text") != translated:
                frappe.db.set_value("Translation", name, "translated_text", translated,
                                    update_modified=False)
        else:
            frappe.get_doc({"doctype": "Translation", "language": "zh",
                            "source_text": source, "translated_text": translated,
                            "context": ""}).insert(ignore_permissions=True)
    frappe.clear_cache()
