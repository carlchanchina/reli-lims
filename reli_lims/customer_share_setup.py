"""客户共同填写：原生 Web Form + 原生 Web Form Request 的幂等安装。

不新建业务单据：Test Request 草稿仍是唯一业务实体，本模块只补齐
展示字段、审核字段、链接撤销字段与一个原生 Web Form 配置。
"""
import frappe
from frappe import _

WEB_FORM = "customer-request"
WEB_FORM_TITLE = "检测委托 · 客户填写"
STATE_OPTIONS = ("Draft\nAwaiting Customer Confirmation\nCustomer Confirmed\n"
                 "Needs Reconfirmation\nAwaiting Lab Review\nLab Reviewed\nAccepted")

REQUEST_FIELDS = [
    {"fieldname": "customer_display_name", "label": "委托单位（只读展示）", "fieldtype": "Data",
     "read_only": 1, "no_copy": 1, "hidden": 1},
    {"fieldname": "customer_attachment", "label": "客户补充附件", "fieldtype": "Attach"},
    {"fieldname": "customer_declaration_confirmed", "label": "客户确认声明", "fieldtype": "Check",
     "default": "0"},
    {"fieldname": "lab_reviewed_by", "label": "实验室审核人", "fieldtype": "Data", "read_only": 1,
     "no_copy": 1},
    {"fieldname": "lab_reviewed_at", "label": "实验室审核时间", "fieldtype": "Datetime",
     "read_only": 1, "no_copy": 1},
]

SHARE_FIELDS = [
    {"fieldname": "reli_revoked", "label": "已撤销", "fieldtype": "Check", "default": "0",
     "read_only": 1, "no_copy": 1, "in_list_view": 1},
    {"fieldname": "reli_revoked_on", "label": "撤销时间", "fieldtype": "Datetime", "read_only": 1,
     "no_copy": 1},
    {"fieldname": "reli_revoked_by", "label": "撤销人", "fieldtype": "Data", "read_only": 1},
    {"fieldname": "reli_customer_email", "label": "客户邮箱", "fieldtype": "Data"},
    {"fieldname": "reli_use_count", "label": "填写次数", "fieldtype": "Int", "read_only": 1,
     "default": "0"},
    {"fieldname": "reli_last_used_on", "label": "最近填写时间", "fieldtype": "Datetime",
     "read_only": 1},
]

def SECTION(label, name):
    return {"fieldname": name, "fieldtype": "Section Break", "label": label}

WEB_FORM_FIELDS = [
    SECTION("委托信息（实验室已预填）", "sec_request"),
    {"fieldname": "customer_confirmation_state", "fieldtype": "Select", "label": "填写状态",
     "read_only": 1},
    {"fieldname": "customer_display_name", "fieldtype": "Data", "label": "委托单位", "read_only": 1},
    {"fieldname": "title", "fieldtype": "Data", "label": "委托名称", "read_only": 1},
    {"fieldname": "delivery_date", "fieldtype": "Date", "label": "要求完成日期", "reqd": 1},

    SECTION("联系人信息", "sec_contact"),
    {"fieldname": "contact_person", "fieldtype": "Data", "label": "联系人", "reqd": 1},
    {"fieldname": "contact_phone", "fieldtype": "Data", "label": "联系电话"},
    {"fieldname": "contact_email", "fieldtype": "Data", "label": "联系邮箱"},
    {"fieldname": "applicant_address", "fieldtype": "Small Text", "label": "委托单位地址"},

    SECTION("送样信息", "sec_samples"),
    {"fieldname": "customer_shipping_details", "fieldtype": "Small Text", "label": "送样方式与物流信息",
     "description": "例如：顺丰 SF1234567890；共 2 箱；预计 11 月 8 日送达。"},
    {"fieldname": "samples", "fieldtype": "Table", "label": "委托样品",
     "description": "请逐行填写送检样品，产品名称建议包含型号（例如：控制盒 KZH-833）。数量必须大于 0。"},

    SECTION("检测需求", "sec_tests"),
    {"fieldname": "customer_expected_tests", "fieldtype": "Small Text", "label": "期望检测项目",
     "description": "请用中文描述需要做的检测项目，例如：高温工作、低温贮存、随机振动。"},
    {"fieldname": "customer_reference_standards", "fieldtype": "Small Text", "label": "参考检测标准",
     "description": "如有指定标准请填写标准号与版本，例如：GB/T 2423.1-2008。"},
    {"fieldname": "customer_declared_conditions", "fieldtype": "Small Text", "label": "委托方声明的试验条件",
     "description": "例如：-40℃ 贮存 24h；+85℃ 工作 48h；振动 10-500Hz 2h/轴。"},
    {"fieldname": "result_judgment", "fieldtype": "Select", "label": "是否需要结果判定"},
    {"fieldname": "judgment_basis", "fieldtype": "Small Text", "label": "判定依据",
     "depends_on": "eval:doc.result_judgment=='Required'"},
    {"fieldname": "subcontract_consent", "fieldtype": "Select", "label": "是否接受分包检测"},
    {"fieldname": "method_choice_consent", "fieldtype": "Select", "label": "是否接受实验室选择检测方法"},
    {"fieldname": "fixture_required", "fieldtype": "Select", "label": "是否需要专用夹具"},
    {"fieldname": "fixture_provider", "fieldtype": "Select", "label": "夹具提供方",
     "depends_on": "eval:doc.fixture_required=='Yes'"},

    SECTION("报告与样品处置", "sec_report"),
    {"fieldname": "report_requirements", "fieldtype": "Small Text", "label": "报告特殊要求"},
    {"fieldname": "report_format", "fieldtype": "Select", "label": "报告形式"},
    {"fieldname": "report_copies", "fieldtype": "Int", "label": "报告份数"},
    {"fieldname": "sample_return", "fieldtype": "Select", "label": "检后样品处理方式"},
    {"fieldname": "sample_handling_notes", "fieldtype": "Small Text", "label": "样品处置补充说明"},
    {"fieldname": "customer_requirements", "fieldtype": "Small Text", "label": "其他要求与说明",
     "reqd": 1},

    SECTION("附件", "sec_files"),
    {"fieldname": "customer_attachment", "fieldtype": "Attach", "label": "补充附件",
     "description": "可上传样品照片、图纸或技术协议（单个文件不超过 10MB）。"},

    SECTION("确认", "sec_confirm"),
    {"fieldname": "customer_declaration_confirmed", "fieldtype": "Check", "label": "我确认以上信息真实完整"},
]

INTRODUCTION = """
<p>本页面由检测实验室发起，用于双方共同填写同一份检测委托申请。</p>
<p>实验室已预填的内容无需重复填写；您可以随时保存草稿，并在有效期内通过本链接再次补充。
填写完成后请点击“确认并提交实验室”，确认后内容将锁定并进入实验室审核。</p>
"""

CLIENT_SCRIPT = r"""
(function () {
  var key = new URLSearchParams(window.location.search).get('web_form_request_key');
  if (!key) return;
  var state = (frappe.reference_doc || {}).customer_confirmation_state || 'Draft';
  var locked = ['Customer Confirmed', 'Awaiting Lab Review', 'Lab Reviewed'].includes(state);

  function inject() {
    var area = document.querySelector('.web-form-footer .right-area');
    if (!area) return false;
    if (locked) {
      var banner = document.createElement('div');
      banner.className = 'alert alert-info reli-locked';
      banner.textContent = '本委托已确认，正在实验室审核中，页面上不可再修改。如需补充请联系实验室。';
      var form = document.querySelector('.web-form-body');
      if (form && !document.querySelector('.reli-locked')) form.prepend(banner);
      document.querySelectorAll('.web-form-footer button').forEach(function (b) { b.disabled = true; });
      return true;
    }
    if (document.getElementById('reli-confirm-submit')) return true;
    var button = document.createElement('button');
    button.type = 'button';
    button.id = 'reli-confirm-submit';
    button.className = 'btn btn-primary btn-sm ml-2';
    button.textContent = '确认并提交实验室';
    button.addEventListener('click', function () {
      if (!frappe.web_form.doc.customer_declaration_confirmed) {
        frappe.msgprint('请先勾选“我确认以上信息真实完整”。');
        return;
      }
      frappe.confirm('确认后内容将锁定并进入实验室审核，是否继续？', function () {
        frappe.web_form.save().then(function () {
          frappe.call({
            method: 'reli_lims.customer_share.customer_confirm',
            type: 'POST',
            args: {web_form_request_key: key},
            freeze: true,
            callback: function () {
              document.querySelector('.web-form-container').classList.add('hide');
              document.querySelector('.success-page').classList.remove('hide');
              document.querySelector('.success-title').textContent = '已提交实验室审核';
              document.querySelector('.success-message').textContent =
                '感谢您的配合。实验室完成审核后将与您联系。';
            },
          });
        });
      });
    });
    area.appendChild(button);
    return true;
  }

  if (!inject()) {
    var tries = 0;
    var timer = setInterval(function () {
      if (inject() || ++tries > 40) clearInterval(timer);
    }, 150);
  }
})();
"""

CUSTOM_CSS = """
.web-form-container { max-width: 860px; }
.web-form-footer .right-area { flex-wrap: wrap; gap: .5rem; }
.web-form-container .form-grid .row-index { display: none; }
.web-form-container .form-grid-container { overflow-x: auto; }
.web-form-container .form-grid .col[data-fieldname="product_name"],
.web-form-container .form-grid .col[data-fieldname="model"] {
  flex: 1 1 0 !important; width: auto !important; min-width: 0 !important;
}
.web-form-container .form-grid .col[data-fieldname="quantity"] {
  flex: 0 0 84px !important; width: 84px !important;
}
.web-form-container .form-grid .static-area,
.web-form-container .form-grid .field-area .form-control { font-size: .82rem; }
@media (max-width: 576px) {
  .web-form-title h1 { font-size: 1.15rem; }
  .web-form-footer .right-area .btn { width: 100%; margin-left: 0 !important; }
  .web-form-container .form-grid .col[data-fieldname="quantity"] {
    flex: 0 0 84px !important; width: 84px !important;
  }
  /* 手机端优先保证可填写：型号并入产品名称，数量列固定可见。 */
  .web-form-container .form-grid .col[data-fieldname="model"] { display: none; }
  .web-form-container .form-grid .static-area,
  .web-form-container .form-grid .field-area .form-control { font-size: .75rem; }
}
"""


def _custom_fields():
    return {
        "Test Request": [dict(field, insert_after="report_requirements") for field in REQUEST_FIELDS],
        "Web Form Request": [dict(field, insert_after="expires_on") for field in SHARE_FIELDS],
    }


def _ensure_state_options():
    name = frappe.db.get_value("Custom Field", {"dt": "Test Request",
                                               "fieldname": "customer_confirmation_state"})
    if not name:
        return
    meta = frappe.get_meta("Test Request")
    field = meta.get_field("customer_confirmation_state")
    if field and set(field.options.split("\n")) != set(STATE_OPTIONS.split("\n")):
        frappe.db.set_value("Custom Field", name, "options", STATE_OPTIONS)
    frappe.clear_cache(doctype="Test Request")


def _ensure_web_form():
    if frappe.db.exists("Web Form", WEB_FORM):
        doc = frappe.get_doc("Web Form", WEB_FORM)
    else:
        doc = frappe.new_doc("Web Form")
        doc.name = WEB_FORM
        doc.route = WEB_FORM
        doc.title = WEB_FORM_TITLE
        doc.doc_type = "Test Request"
    doc.title = WEB_FORM_TITLE
    doc.route = WEB_FORM
    doc.doc_type = "Test Request"
    doc.is_standard = 0
    doc.published = 1
    doc.login_required = 0
    doc.key_required = 1
    doc.allow_edit = 1
    doc.allow_multiple = 0
    doc.allow_delete = 0
    doc.allow_print = 0
    doc.allow_comments = 0
    doc.allow_incomplete = 1
    doc.apply_document_permissions = 0
    doc.show_list = 0
    doc.show_attachments = 1
    doc.max_attachment_size = 10
    doc.introduction_text = INTRODUCTION
    doc.button_label = "保存草稿"
    doc.success_title = "已保存"
    doc.success_message = "本次填写已保存。实验室审核前，您可以通过同一链接再次进入补充或确认。"
    doc.client_script = CLIENT_SCRIPT
    doc.custom_css = CUSTOM_CSS
    doc.set("web_form_fields", [])
    meta = frappe.get_meta("Test Request")
    for row in WEB_FORM_FIELDS:
        data = dict(row, hidden=0)
        df = meta.get_field(row.get("fieldname")) if row.get("fieldname") else None
        if df and row["fieldtype"] in ("Select", "Table", "Link") and df.options:
            # Web Form 字段独立存储，下拉与子表选项必须从目标 DocType 复制。
            data["options"] = df.options
        doc.append("web_form_fields", data)
    doc.flags.ignore_permissions = True
    if doc.is_new():
        doc.insert(ignore_permissions=True)
    else:
        doc.save(ignore_permissions=True)
    return doc.name


def verify_schema():
    errors = []
    for doctype, fields in _custom_fields().items():
        meta = frappe.get_meta(doctype)
        for expected in fields:
            actual = meta.get_field(expected["fieldname"])
            if not actual:
                errors.append(f"{doctype}.{expected['fieldname']}: missing")
            elif actual.fieldtype != expected["fieldtype"]:
                errors.append(f"{doctype}.{expected['fieldname']}: fieldtype mismatch")
    meta = frappe.get_meta("Test Request")
    state = meta.get_field("customer_confirmation_state")
    if state and "Awaiting Lab Review" not in (state.options or ""):
        errors.append("Test Request.customer_confirmation_state: review states missing")
    if not frappe.db.exists("Web Form", WEB_FORM):
        errors.append(f"Web Form {WEB_FORM}: missing")
    else:
        form = frappe.get_doc("Web Form", WEB_FORM)
        if not (form.key_required and not form.login_required and form.allow_edit):
            errors.append("Web Form: key_required/login_required/allow_edit misconfigured")
        names = {row.fieldname for row in form.web_form_fields}
        for required in ("samples", "customer_attachment", "customer_declaration_confirmed"):
            if required not in names:
                errors.append(f"Web Form: missing field {required}")
    if not frappe.db.exists("DocType", "Test Request Share Event"):
        errors.append("DocType Test Request Share Event: missing")
    return errors


def after_migrate():
    from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
    create_custom_fields(_custom_fields(), update=True)
    _ensure_state_options()
    _ensure_web_form()
    errors = verify_schema()
    if errors:
        frappe.throw("客户共同填写安装校验失败：" + "；".join(errors))
