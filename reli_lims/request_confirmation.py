"""Native Draft collaboration and customer confirmation; never Frappe Submit."""
import hashlib
import json
import math

# Explicit technical/declared scope only. Do not add modified/owner/audit, engineer,
# engineering_review_notes, item.notes or internal final execution fields here.
TECHNICAL_FIELDS = ('customer','company','quotation','sales_order','execution_company','delivery_date',
 'customer_requirements','customer_expected_tests','customer_reference_standards','customer_declared_conditions','customer_shipping_details',
 'contact_person','contact_phone','contact_email','applicant_address','report_requirements','report_company','report_address',
 'report_language','report_copies','report_format','sample_handling_notes','sample_return','result_judgment','judgment_basis',
 'fixture_required','fixture_provider','method_choice_consent','subcontract_consent')
CHILD_FIELDS = {
 'samples': ('sample_code','customer_sample_code','product_name','model','serial_no','quantity','dimensions','weight_kg'),
 'items': ('item_code','test_method','standard','test_condition'),
 'sample_assignments': ('item_code','sample_code'),
 'photos': ('sample_code','photo'),
}
PROTECTED = ('customer_confirmation_state','customer_confirmed_by','customer_confirmed_at','customer_confirmation_fingerprint')
_MUTATION = object()


def fingerprint(data, files):
    snapshot = {key: data.get(key) if data.get(key) is not None else '' for key in TECHNICAL_FIELDS}
    for table, fields in CHILD_FIELDS.items():
        snapshot[table] = [{field: row.get(field) if row.get(field) is not None else '' for field in fields} for row in data.get(table) or []]
        # Native generated row names and audit fields do not participate.
        for row in snapshot[table]:
            for field in ('quantity','weight_kg'):
                if field in row and row[field] != '':
                    row[field] = float(row[field])
    snapshot['attachments'] = sorted([{key: row.get(key) or '' for key in ('name','file_name','content_hash')} for row in files],key=lambda row:row['name'])
    return hashlib.sha256(json.dumps(snapshot,sort_keys=True,ensure_ascii=False,separators=(',',':'),default=str,allow_nan=False).encode()).hexdigest()


def attachments(name):
    import frappe
    return frappe.get_all('File',filters={'attached_to_doctype':'Test Request','attached_to_name':name,'is_private':1,'is_folder':0,'reli_customer_visible':1},
        fields=['name','file_name','content_hash'],order_by='name',limit_page_length=101)


def current_fingerprint(doc):
    files = attachments(doc.name) if doc.name else []
    if len(files)>100:
        import frappe
        frappe.throw('本委托附件超过确认处理上限，请联系实验室整理。')
    return fingerprint(doc.as_dict(),files)


def confirmation_missing(data):
    missing=[]
    for field in ('delivery_date','customer_requirements','customer_expected_tests','contact_person'):
        if not str(data.get(field) or '').strip():missing.append(field)
    if not data.get('contact_email') and not data.get('contact_phone'):missing.append('contact_email_or_phone')
    if not data.get('samples'):missing.append('samples')
    for row in data.get('samples') or []:
        if not str(row.get('product_name') or '').strip():missing.append('samples.product_name')
        qty=row.get('quantity')
        if isinstance(qty,bool) or not isinstance(qty,(int,float)) or not math.isfinite(qty) or qty<=0:missing.append('samples.quantity')
    return sorted(set(missing))


def validate_confirmation(doc):
    """Called by native TestRequest.validate, including normal laboratory Desk saves."""
    import frappe
    if not frappe.get_meta('Test Request').has_field('customer_confirmation_state'):return
    previous=doc.get_doc_before_save()
    if doc.flags.get('_reli_customer_confirmation_mutation') is not _MUTATION:
        for field in PROTECTED:
            old=previous.get(field) if previous else None
            if field=='customer_confirmation_state' and not old and doc.get(field) in (None,'','Draft'):
                continue
            if str(doc.get(field) or '') != str(old or ''):
                frappe.throw('客户确认记录不能直接修改，请使用受权确认操作。')
    if doc.docstatus==0 and doc.get('customer_confirmation_fingerprint'):
        if current_fingerprint(doc)!=doc.customer_confirmation_fingerprint:
            doc.customer_confirmation_state='Needs Reconfirmation'
    if doc.get('execution_company'):
        frappe.get_doc('Company',doc.execution_company).check_permission('read')


def confirm(doc, receipt):
    import frappe
    if doc.docstatus!=0:frappe.throw('只能确认检测委托申请草稿。')
    if confirmation_blockers(doc):frappe.throw('请先补齐客户必填资料并由实验室分享需要确认的照片。')
    if current_fingerprint(doc)!=receipt['fingerprint']:frappe.throw('技术委托内容已变化，请刷新后重新确认。')
    doc.customer_confirmation_state='Customer Confirmed'
    doc.customer_confirmed_by=receipt['confirmed_by']
    doc.customer_confirmed_at=receipt['confirmed_at']
    doc.customer_confirmation_fingerprint=receipt['fingerprint']
    doc.flags._reli_customer_confirmation_mutation=_MUTATION
    try:doc.save(ignore_permissions=True)
    finally:doc.flags.pop('_reli_customer_confirmation_mutation',None)


def await_customer(doc):
    import frappe
    from reli_lims.validation import require_role
    require_role('Lab Manager','Lab Engineer')
    doc=frappe.get_doc('Test Request',doc.name,for_update=True)
    doc.check_permission('write')
    if doc.docstatus!=0:frappe.throw('只能请求确认检测委托申请草稿。')
    doc.customer_confirmation_state='Awaiting Customer Confirmation'
    doc.flags._reli_customer_confirmation_mutation=_MUTATION
    try:doc.save()
    finally:doc.flags.pop('_reli_customer_confirmation_mutation',None)


def file_changed(file, method=None):
    """Private attachments are part of technical confirmation, including Desk uploads/deletes."""
    import frappe
    if file.attached_to_doctype!='Test Request' or not file.attached_to_name:return
    if not frappe.db.exists('Test Request',file.attached_to_name):return
    doc=frappe.get_doc('Test Request',file.attached_to_name,for_update=True)
    if doc.docstatus==0 and doc.get('customer_confirmation_fingerprint') and doc.get('customer_confirmation_state')!='Needs Reconfirmation':
        if current_fingerprint(doc)!=doc.customer_confirmation_fingerprint:
            # Native validate computes the transition; no confirmation identity is rewritten.
            doc.save(ignore_permissions=True)


def validate_file_visibility(file, method=None):
    import frappe
    if not frappe.get_meta('File').has_field('reli_customer_visible'):return
    previous=file.get_doc_before_save()
    old=previous.get('reli_customer_visible') if previous else 0
    if old and any(str(getattr(file,field,None) or '')!=str(getattr(previous,field,None) or '') for field in ('attached_to_doctype','attached_to_name','file_url')):
        frappe.throw('已分享的客户附件不能改绑委托或替换私有文件路径。')
    if bool(file.get('reli_customer_visible'))!=bool(old) and file.flags.get('_reli_customer_confirmation_mutation') is not _MUTATION:
        frappe.throw('客户附件可见性只能通过受权分享操作修改。')
    if file.get('reli_customer_visible'):
        if not file.is_private or file.attached_to_doctype!='Test Request' or not file.attached_to_name:
            frappe.throw('客户附件必须是当前检测委托的私有文件。')
        if frappe.db.get_value('Test Request',file.attached_to_name,'docstatus')!=0:
            frappe.throw('只能分享检测委托申请草稿的附件。')


def mark_customer_file(file):
    file.reli_customer_visible=1
    file.flags._reli_customer_confirmation_mutation=_MUTATION
    try:file.save(ignore_permissions=True)
    finally:file.flags.pop('_reli_customer_confirmation_mutation',None)
    import frappe
    gateway=frappe.conf.get('ntbln_portal_gateway_user')
    if gateway and frappe.db.exists('User',gateway):
        import frappe.share
        frappe.share.add('File',file.name,user=gateway,read=1,write=0,share=0,notify=0,flags={'ignore_share_permission':True})


def share_customer_attachment(doc, file_id):
    import frappe
    from reli_lims.validation import require_role
    require_role('Lab Manager','Lab Engineer')
    doc=frappe.get_doc('Test Request',doc.name,for_update=True)
    doc.check_permission('write')
    if doc.docstatus!=0 or not isinstance(file_id,str):frappe.throw('只能分享当前委托草稿附件。')
    file=frappe.get_doc('File',file_id)
    file.check_permission('read')
    if not file.is_private or file.attached_to_doctype!='Test Request' or file.attached_to_name!=doc.name:
        frappe.throw('附件不属于当前检测委托。',frappe.PermissionError)
    mark_customer_file(file)
    return {'fileId':file.name,'fileName':file.file_name}


TECHNICAL_LABELS = {
 'customer':'委托单位','company':'商业所属公司','quotation':'关联报价','sales_order':'关联销售订单','execution_company':'执行公司（指定值）',
 'report_company':'报告抬头','report_address':'报告地址','report_language':'报告语言','report_copies':'报告份数','report_format':'报告形式',
 'sample_handling_notes':'样品处置要求','sample_return':'样品返还安排','result_judgment':'结果判定要求','judgment_basis':'判定依据',
 'fixture_required':'工装要求','fixture_provider':'工装提供方','method_choice_consent':'方法选择许可','subcontract_consent':'分包许可',
}
PUBLIC_EDIT_FIELDS = ('customer_requirements','customer_expected_tests','customer_reference_standards','customer_declared_conditions','customer_shipping_details',
 'contact_person','contact_phone','contact_email','applicant_address','delivery_date','report_requirements')

def technical_details(data):
    # Every top-level fingerprint field is either customer-editable and shown in
    # the form, or explicitly rendered here. Missing/cleared values remain visible.
    assert set(TECHNICAL_FIELDS)==set(TECHNICAL_LABELS)|set(PUBLIC_EDIT_FIELDS)
    enum={'Yes':'是','No':'否','Required':'需要','Not Required':'不需要','Chinese':'中文','Electronic':'电子版','Paper':'纸质版',
        'Electronic and Paper':'电子和纸质','Customer':'客户','Laboratory':'实验室','Return by Courier':'快递返还','Self Pickup':'自行取回','Retain 30 Days then Dispose':'留存30天后处置'}
    result=[]
    for key,label in TECHNICAL_LABELS.items():
        value=data.get(key)
        value='未填写' if value in (None,'') else enum.get(str(value),str(value))
        result.append(dict(label=label,value=value))
    for row in data.get('samples') or []:
        for key,label in (('customer_sample_code','客户样品编号'),('serial_no','序列号'),('dimensions','尺寸'),('weight_kg','重量(kg)')):
            value=row.get(key)
            result.append(dict(label=str(row.get('sample_code') or '')+' · '+label,value='未填写' if value in (None,'') else str(value)))
    return result


def shared_photos(doc):
    import frappe
    result=[]
    for row in doc.get('photos') or []:
        file=frappe.db.get_value('File',dict(file_url=row.photo,is_private=1,reli_customer_visible=1,attached_to_doctype='Test Request',attached_to_name=doc.name),['name','file_name'],as_dict=True)
        if file:result.append(dict(sampleCode=row.sample_code,fileId=file.name,name=file.file_name))
    return result


def confirmation_blockers(doc):
    result=confirmation_missing(doc.as_dict())
    if len(shared_photos(doc))!=len(doc.get('photos') or []):result.append('shared_sample_photos')
    return sorted(set(result))
