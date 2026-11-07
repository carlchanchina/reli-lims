# Copyright (c) 2026, ReliLab and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class TestRequestShareEvent(Document):
	"""审计记录只能由受控服务写入，任何界面都不允许修改或删除。"""

	def validate(self):
		previous = self.get_doc_before_save()
		if previous:
			frappe.throw('客户填写记录为审计轨迹，不允许修改。')

	def on_trash(self):
		frappe.throw('客户填写记录为审计轨迹，不允许删除。')
