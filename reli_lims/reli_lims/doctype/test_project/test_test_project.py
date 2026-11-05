import frappe
from frappe.tests import IntegrationTestCase


class IntegrationTestTestProject(IntegrationTestCase):
    def test_condition_template_is_validated_and_preserved(self):
        project = frappe.get_doc(
            doctype="Test Project",
            project_name="温度循环模板测试项目",
            condition_template='[{"key":"cycles","label":"循环次数","type":"number","required":true}]',
        ).insert()
        self.assertIn("cycles", project.condition_template)
