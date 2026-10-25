import importlib
import sys
import types
import unittest
from unittest.mock import Mock, patch

MODULE = 'reli_lims.reli_lims.report.laboratory_work_queue.laboratory_work_queue'


class WorkQueueTest(unittest.TestCase):
    def setUp(self):
        f = types.ModuleType('frappe')
        f._ = lambda text: text
        f._dict = lambda value: AttrDict(value)
        f.PermissionError = PermissionError
        f.throw = lambda message, error=ValueError: (_ for _ in ()).throw(error(message))
        f.get_roles = lambda: ['Lab Engineer']
        f.session = types.SimpleNamespace(user='engineer@example.test')
        f.get_list = Mock(return_value=['P1'])
        f.get_all = Mock(return_value=[dict(parent='P1', engineer=f.session.user, status='Running', result='', conclusion='')])
        self.f = f
        self.patch = patch.dict(sys.modules, {'frappe': f})
        self.patch.start()
        self.addCleanup(self.patch.stop)
        sys.modules.pop(MODULE, None)
        self.api = importlib.import_module(MODULE)
        self.addCleanup(sys.modules.pop, MODULE, None)

    def test_server_role_gate_blocks_review_and_assignment(self):
        for view in ('待复核结果', '待分配任务', 'unknown'):
            with self.assertRaises(PermissionError): self.api.execute({'view': view})
        self.f.get_all.assert_not_called()

    def test_visible_parents_scope_children_and_client_identity_ignored(self):
        columns, data = self.api.execute({'view': '我的进行中', 'engineer': 'other'})
        self.assertEqual(len(data), 1)
        self.assertEqual(self.f.get_all.call_args.kwargs['filters'],
                         {'parent': ['in', ['P1']], 'parenttype': 'Test Program', 'parentfield': 'items'})
        self.assertNotIn('result', data[0])
        self.assertNotIn('conclusion', data[0])

    def test_no_visible_parents_returns_no_tasks(self):
        self.f.get_list.return_value = []
        self.assertEqual(self.api.execute({'view': '我的进行中'})[1], [])
        self.f.get_all.assert_not_called()

    def test_engineer_sees_only_own_matching_rows(self):
        rows = [dict(engineer='me', status='Ready'), dict(engineer='other', status='Ready'),
                dict(engineer='me', status='Reviewed')]
        self.assertEqual(self.api.select_rows(rows, '我的待执行', 'me'), rows[:1])

    def test_reviewer_and_manager_queue_semantics(self):
        rows = [dict(status='Completed', engineer='me'), dict(status='Pending', engineer=None)]
        self.assertEqual(self.api.select_rows(rows, '待复核结果', 'reviewer'), rows[:1])
        self.assertEqual(self.api.select_rows(rows, '待分配任务', 'manager'), rows[1:])

    def test_parent_limit_never_silently_truncates_counts(self):
        self.f.get_list.return_value = ['P'] * 501
        with self.assertRaises(ValueError): self.api.execute()
        self.f.get_all.assert_not_called()


class AttrDict(dict):
    def __getattr__(self, key): return self.get(key)
