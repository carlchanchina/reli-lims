from .common import context
from ..registry import TEMPLATES


def build_context(doc):
    fields = [('委托单位', doc.get('customer')), ('公司', doc.get('company')),
              ('委托日期', doc.get('request_date')), ('要求完成日期', doc.get('delivery_date')),
              ('联系人', doc.get('contact_person')), ('联系电话', doc.get('contact_phone')),
              ('报价单', doc.get('quotation')), ('销售订单', doc.get('sales_order'))]
    samples = [[r.get('sample_code'), r.get('product_name'), r.get('model'), r.get('serial_no'), r.get('quantity')]
               for r in doc.get('samples') or []]
    rows = [[i, r.get('test_method_label') or r.get('test_method'), r.get('standard_label') or r.get('standard'), r.get('applicable_sample_codes'), r.get('test_condition')]
            for i, r in enumerate(doc.get('items') or [], 1)]
    sections = [dict(title='委托样品', columns=['编号', '产品名称', '型号', '序列号', '数量'], rows=samples)]
    requirements = [('结果判定', doc.get('result_judgment')), ('判定依据', doc.get('judgment_basis')),
                    ('分包意向', doc.get('subcontract_consent')), ('样品返还', doc.get('sample_return')),
                    ('样品处置说明', doc.get('sample_handling_notes')), ('报告要求', doc.get('report_requirements'))]
    sections.append(dict(title='客户特殊要求', columns=['事项', '要求'], rows=requirements))
    return context('检测委托单', doc, fields, TEMPLATES['Test Request'].columns, rows,
                   notice='草稿' if doc.get('docstatus', 0) == 0 else '委托单输出副本', sections=sections)
