import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class WorkspaceFinalTests(unittest.TestCase):
    def test_native_navigation_preserves_six_cards_and_eight_stage_kanban(self):
        workspace = json.loads((ROOT / 'reli_lims/reli_lims/workspace/testing_fulfillment_center/testing_fulfillment_center.json').read_text())
        self.assertEqual(len(workspace['number_cards']), 6)
        targets = {row.get('link_to') for row in workspace['shortcuts']}
        self.assertEqual(targets, {'Test Request', 'Sample', 'Test Program', 'reli-test-records', 'Test Report'})
        self.assertIn('检测主流程', workspace['content'])
        capability = json.loads((ROOT / 'reli_lims/reli_lims/workspace/laboratory_capability_center/laboratory_capability_center.json').read_text())
        self.assertEqual({row.get('link_to') for row in capability['links'] if row['type'] == 'Link'},
                         {'Test Project', 'Test Object', 'Test Standard', 'Laboratory Profile',
                          'Capability Source', 'Laboratory Capability', 'Item'})

    def test_hooks_attach_one_shared_output_ui_to_three_native_forms(self):
        import runpy
        hooks = runpy.run_path(str(ROOT / 'reli_lims/hooks.py'))
        for dt in ('Quotation', 'Test Request', 'Test Report'):
            scripts = hooks['doctype_js'][dt]
            scripts = [scripts] if isinstance(scripts, str) else scripts
            self.assertEqual(scripts.count('public/js/document_output.js'), 1)
