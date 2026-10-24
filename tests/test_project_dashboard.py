import importlib
import sys
import types
import unittest
from unittest.mock import patch


class ProjectDashboardTest(unittest.TestCase):
    def test_preserves_native_groups_and_avoids_duplicate_links(self):
        f = types.ModuleType('frappe')
        f._ = lambda value: value
        with patch.dict(sys.modules, {'frappe': f}):
            sys.modules.pop('reli_lims.project_dashboard', None)
            module = importlib.import_module('reli_lims.project_dashboard')
            original = {'fieldname': 'project', 'heatmap': True,
                        'transactions': [{'label': 'Project', 'items': ['Task', 'Sample']}],
                        'non_standard_fieldnames': {'Task': 'project'}}
            result = module.get_data(original)
            self.assertEqual(result['transactions'][0], original['transactions'][0])
            self.assertEqual(result['transactions'][-1]['items'],
                             ['Test Request', 'Test Program', 'Test Report'])
            self.assertTrue(result['heatmap'])
            self.assertEqual(module.get_data(result), result)
            self.assertEqual(len(original['transactions']), 1)
            for doctype in ('Test Request', 'Sample', 'Test Program', 'Test Report'):
                self.assertEqual(result['non_standard_fieldnames'][doctype], 'project')
            sys.modules.pop('reli_lims.project_dashboard', None)
