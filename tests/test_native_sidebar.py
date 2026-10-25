import json
from pathlib import Path
import runpy
import unittest

ROOT = Path(__file__).resolve().parents[1]


class NativeSidebarTest(unittest.TestCase):
    def test_sidebar_groups_preserve_real_targets(self):
        data = json.loads((ROOT / 'reli_lims/reli_lims/sidebar/reli_lims/reli_lims.json').read_text())
        self.assertEqual(data['doctype'], 'Sidebar')
        self.assertEqual(data['module'], 'Reli LIMS')
        self.assertEqual([r['label'] for r in data['items'] if r['type'] == 'Section Break'],
                         ['工作台入口', '检测履约', '任务与基础资料'])
        for row in data['items']:
            if row['type'] != 'Link':
                continue
            self.assertEqual(row['child'], 1)
            name = row['link_to'].lower().replace(' ', '_')
            if row['link_type'] == 'Workspace':
                path = ROOT / f'reli_lims/reli_lims/workspace/{name}/{name}.json'
            elif row['link_type'] == 'Report':
                path = ROOT / f'reli_lims/reli_lims/report/{name}/{name}.json'
            elif row['link_to'] in {'Project', 'Task', 'Asset', 'Customer'}:
                continue  # ERPNext required dependency
            else:
                path = ROOT / f'reli_lims/reli_lims/doctype/{name}/{name}.json'
            self.assertTrue(path.exists(), row['link_to'])

    def test_official_style_has_no_custom_css_registration(self):
        hooks = runpy.run_path(str(ROOT / 'reli_lims/hooks.py'))
        self.assertNotIn('app_include_css', hooks)
