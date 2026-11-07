from .common import context
from ..registry import TEMPLATES


def build_context(doc, program):
    fields = [('客户', doc.get('customer')), ('项目', doc.get('project')),
              ('试验方案', doc.get('test_program')), ('检测委托', doc.get('test_request')),
              ('版本', doc.get('version')), ('签发日期', doc.get('issued_date')),
              ('编制人', doc.get('engineer')), ('审核人', doc.get('reviewer')),
              ('总体结论', doc.get('overall_conclusion'))]
    pairs = program.get('sample_assignments') or []
    sample_labels = {row.get('sample'): row.get('sample_label') or row.get('sample')
                     for row in program.get('samples') or []}
    rows = [[i, r.get('test_project_label') or r.get('test_method_label') or r.get('test_method'),
             r.get('standard_label') or r.get('standard'),
             ', '.join(sample_labels.get(p.get('sample'), p.get('sample') or '')
                       for p in pairs if p.get('item_code') == r.get('item_code')),
             r.get('result'), r.get('conclusion')]
            for i, r in enumerate(program.get('items') or [], 1)]
    conditions = [[r.get('test_project_label') or r.get('test_method_label') or r.get('test_method'),
                   r.get('standard_label') or r.get('standard'), r.get('test_condition'),
                   r.get('actual_start'), r.get('actual_end')]
                  for r in program.get('items') or []]
    sections = [dict(title='试验条件与记录',
                     columns=['检测项目', '检测依据（标准/方法）', '试验条件', '实际开始', '实际结束'],
                     rows=conditions)]
    return context('检测报告', doc, fields, TEMPLATES['Test Report'].columns, rows, sections=sections,
                   notice='已签发报告输出副本（最终签发文件以原报告附件为准）' if doc.get('status') == 'Issued'
                   else '草稿／未签发，不作为正式签发报告')
