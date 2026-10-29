"""Server-owned file template allowlist; client input is never a file path."""
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Template:
    key: str
    title: str
    columns: tuple[str, ...]
    row_start: int = 9
    reserved_rows: int = 1
    formats: tuple[str, ...] = ('pdf', 'docx', 'xlsx')

    @property
    def directory(self) -> Path:
        return Path(__file__).parent / 'templates' / self.key


TEMPLATES = {
    'Quotation': Template('quotation', '检测报价单', ('序号', '检测项目', '单位', '单价', '数量', '金额'), 15, 2),
    'Test Request': Template('commission', '检测委托单', ('序号', '检测项目', '执行标准', '适用样品', '测试条件')),
    'Test Report': Template('test_report', '检测报告', ('序号', '检测项目', '执行标准', '适用样品', '结果', '结论')),
}
MIME_TYPES = {'pdf': 'application/pdf',
              'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
              'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'}


def get_template(doctype: str, template: str | None = None) -> Template:
    spec = TEMPLATES.get(doctype)
    if not spec or template not in (None, '', spec.key, spec.title):
        raise ValueError('不支持的文档类型或模板。')
    return spec
