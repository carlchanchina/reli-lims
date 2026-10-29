import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class WorkspaceFinalTests(unittest.TestCase):
    def test_native_navigation_preserves_six_cards_and_eight_stage_kanban(self):
        workspace = json.loads((ROOT / 'reli_lims/reli_lims/workspace/testing_center/testing_center.json').read_text())
        self.assertEqual(len(workspace['number_cards']), 6)
        targets = {r.get('link_to') for r in workspace['links'] + workspace['shortcuts']}
        self.assertTrue({'Customer', 'Contact', 'Address', 'Quotation', 'Sales Order', 'Sales Invoice',
            'Payment Entry', 'Test Request', 'Sample', 'Test Program', 'Test Report', 'Test Method',
            'Test Standard', 'Asset', 'Project', 'Task'} <= targets)
        self.assertNotIn('Project', {r['link_to'] for r in workspace['shortcuts']})
        content = json.loads(workspace['content'])
        cards = {r['label'] for r in workspace['links'] if r['type'] == 'Card Break'}
        self.assertEqual(cards, {'客户与销售', '检测资源与字典', '财务'})
        self.assertEqual({b['data']['card_name'] for b in content if b['type'] == 'card'}, cards)
        self.assertIn('检测主流程', workspace['content'])
        self.assertEqual(len(list((ROOT / 'reli_lims/reli_lims/workspace').glob('testing*'))), 1)
        for row in workspace['links']:
            if row['type'] == 'Link': self.assertEqual(row['link_type'], 'DocType')

    def test_hooks_attach_one_shared_output_ui_to_three_native_forms(self):
        import runpy
        hooks = runpy.run_path(str(ROOT / 'reli_lims/hooks.py'))
        for dt in ('Quotation', 'Test Request', 'Test Report'):
            self.assertEqual(hooks['doctype_js'][dt], 'public/js/document_output.js')
