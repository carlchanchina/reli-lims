"""Prevent untranslated module metadata and broken dynamic error interpolation."""
import csv
import json
import re
import runpy
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1] / 'reli_lims'


def translations():
    with (ROOT / 'translations/zh.csv').open() as stream:
        return {row[0]: row[1] for row in csv.reader(stream) if row and len(row) >= 2 and row[1] and (len(row) < 3 or not row[2])}


def test_all_owned_doctype_labels_and_select_options_have_chinese():
    table = translations()
    missing = set()
    for path in (ROOT / 'reli_lims/doctype').glob('*/*.json'):
        if path.name.startswith('._'):
            continue
        doc = json.loads(path.read_text())
        terms = [doc.get('name', path.stem.replace('_', ' ').title())]
        for field in doc.get('fields', []):
            terms.extend(field.get(key, '') for key in ('label', 'description'))
            if field.get('fieldtype') == 'Select':
                terms.extend(field.get('options', '').splitlines())
        missing.update(term for term in terms if isinstance(term, str) and re.search('[A-Za-z]', term) and not re.search('[\u4e00-\u9fff]', term) and term not in table)
    assert not missing, sorted(missing)


def test_workbench_links_remain_native_and_are_translated():
    workspace = json.loads((ROOT / 'reli_lims/workspace/testing_center/testing_center.json').read_text())
    table = translations()
    assert workspace['name'] == 'Testing Center'
    assert workspace['roles'] == [{'role': 'Lab Manager'}, {'role': 'Lab Engineer'}, {'role': 'Lab Reviewer'}]
    for shortcut in workspace['shortcuts']:
        assert shortcut['type'] == 'DocType'
        assert not re.search('[A-Za-z]', shortcut['label']) or shortcut['label'] in table
    blocks = json.loads(workspace['content'])
    assert [block['data']['text'] for block in blocks if block['type'] == 'header'] == [
        '<span class="h4">检测工作台</span>', '<span class="h4">主流程看板</span>', '<span class="h4">常用操作</span>']


def test_scope_errors_translate_and_preserve_sample_identifiers(monkeypatch):
    table = translations()
    monkeypatch.setitem(sys.modules, 'frappe', SimpleNamespace(_=lambda message, **kwargs: table.get(message, message)))
    message = runpy.run_path(str(ROOT / 'i18n.py'))['scope_error_message']
    assert message(ValueError('Receive these samples first: S-1, S-2')) == '请先接收以下样品：S-1, S-2'
    assert message(ValueError('Every sample needs a product name.')) == '每个样品都必须填写产品名称。'


def test_generic_translations_do_not_redefine_other_erp_modules():
    table = translations()
    assert table['Company'] == '公司'
    assert table['Condition'] == '条件'
    assert table['Pending'] == '待处理'
    assert table['Engineer'] == '工程师'
    assert table['Asset'] == '资产'
