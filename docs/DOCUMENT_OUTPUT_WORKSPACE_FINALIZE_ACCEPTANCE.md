# 文档输出与工作台最终收口验收

日期：2026-10-29。分支：`codex/document-output-workspace-finalize`。本轮无生产部署。

## 基线与复用

先执行 `git fetch origin`。最新 `main` 为 `e5f5c80`，目标分支最初仅领先计划提交 `bd49455`。远端所有分支、提交、PR 及前一窗口记录中均未发现已完成的 Document Output：上一窗口因模型容量错误中断在读取／环境检查阶段。用户随后明确授权在当前分支补齐。

从既有 `36f4e0e` 单独 cherry-pick 商业来源关联，落地提交 `353f3a6`；没有整包引入尚未合并的实验室能力中心 PR #11。没有重复开发另一套报价／订单模型。

## Workspace 前后对照

| 内容 | 本轮前 | 本轮后 |
|---|---|---|
| 状态 | 六张数字卡 | 六张原卡保留 |
| 主流程 | 原生八阶段检测 Kanban | 原看板保留，补充“报价 → 委托 → 收样 → 试验 → 报告 → 完成”说明 |
| 高频检测 | 委托、收样、方案、报告、项目、标准六入口 | 委托、收样、方案、报告、样品五入口 |
| 客户销售 | 基础资料里只有 Customer | 新建客户、新建报价单、报价列表、销售订单；原生 Contact／Address |
| 资源字典 | 项目、任务、设备散放；检测项目／标准占高频位置 | Test Method、Test Standard、Asset、Project、Task 集中于资源字典 |
| 财务 | 无专门入口 | 原生 Sales Invoice、Payment Entry |

只修改既有 `Testing Center`，没有新增第二个检测 Workspace。所有 16 种导航目标经真实数据库检查存在，继续受各原生 DocType 权限控制，Lab 角色没有因此获得财务／销售权限。

浏览器使用临时用户，角色为 Lab Manager、Sales User、Accounts User、Projects User；实际查看六张数字卡、主流程链接、检测／销售／资源／财务分区，点击报价列表进入原生 Quotation，点击销售发票和收款进入原生销售发票／收付款凭证列表。

[Workspace 截图](acceptance/document_output/workspace.png)；[报价弹窗](acceptance/document_output/quotation-dialog.png)、[委托弹窗](acceptance/document_output/request-dialog.png)、[报告弹窗](acceptance/document_output/report-dialog.png)。截图来自隔离站点，侧栏遗留其他轮次的实验室能力中心不属于本 PR。

## 新增字段与入口

Test Request 增加可折叠可选商业来源区及两个 Link：`quotation → Quotation`、`sales_order → Sales Order`，不复制商品行或销售数据。无两种关联也可直接送检。已关联来源必须已提交、客户／公司一致且操作者可读；同时选择时要求订单明细引用所选报价；复制委托不复制商业来源。

Quotation、Test Request、Test Report 使用同一 `doctype_js` 脚本和一个“生成文档”按钮，弹窗包含模板及 PDF／Word／Excel，PDF 默认。三处弹窗均在浏览器真实打开核对；Quotation 默认 PDF 生成成功，返回私有文件下载链接。没有修改原生内建打印菜单、明细表上传下载功能或报告状态机。

## 测试

| 检查 | 结果 |
|---|---|
| 本地完整 `pytest tests -q` | 36 通过 |
| `node --test tests/*.js` | 5 通过 |
| 全量 Frappe `run-tests --app reli_lims` | 43 通过，249.600 秒 |
| 最终文档模块 Frappe 重测 | 3 通过；覆盖真实九格式、私有附件、不自动签发、Guest／无权限用户全部格式拒绝、Workspace／看板结构 |
| Python 编译、`git diff --check` | 通过 |
| wheel 构建 | 通过；模板与共享 JS 已检查打包 |

全量 Frappe 包含两样品、三检测项目、设备／工程师、Ready → Running → Completed → Reviewed、结果／原始文件、报告审核及签发主路径。文档输出最终修复后重跑文档集成模块。

本地测试另覆盖：三种源映射、空字段、中文文件名、白名单拒绝、源／关联方案权限拒绝、原生金额不重算、Excel 公式文本安全、0／1／25 行、真实报价模板扩行样式／签字区／合并范围、PDF HTML 转义、默认 PDF、未保存单据阻止输出、错误后重试。审查发现长 Excel 文本受行高上限截断；已先复现再修复为带提示的完整“续页”，签字区和元数据值跨列合并。5600 多字条款／结论经 Calc 打印为 3／4 页 PDF，末尾“全文结束标记”均存在。客户文本中的双大括号和续页中的公式前缀另有回归测试。

Frappe 回归有既有 `limit_page_length` 弃用提示，以及既有测试 PDF 的 startxref 修复提示；没有失败。PDF 生成测试使用独立中文字体目录，不修改系统字体。

## 九份示例与视觉验收

[示例下载索引](examples/document_output/README.md)；每种源各提供 PDF／DOCX／XLSX，manifest 记录大小和 SHA-256。源为隔离站点创建的虚构单据，文件由正式服务生成后从原生私有 File 取回。

- PDF：原生 wkhtmltopdf 生成，pypdf 可打开；逐页渲染查看中文、表格、结论、草稿标识。
- Word：python-docx 可打开；LibreOffice 渲染检查三份文件。去除默认 Word Title 样式蓝线，保留黑色标题和可编辑表格。
- Excel：openpyxl 可打开；LibreOffice Calc 成功加载并打印三份，检查报价原模板、边框、页设置、合并签字区、委托样品和报告结论。
- 报价模板原文件没有 print area，保留其布局并补齐打印范围；不发布历史客户／联系人／银行数据及固定税率。没有重画无格式 Workbook。

## 明确边界与剩余项

开发和自动回归已完成。用户提供现有 ONLYOFFICE 容器后，已补齐指定 Office 引擎兼容验收：`x2t 10.0.0.169` 成功原生载入并打印三份 XLSX 和三份 DOCX，输入哈希与仓库示例一致；中文、金额、条款和签字区完整。长文本续页选为活动表后完整打印，末尾标记及字符计数通过。报价 XLSX 在 ONLYOFFICE 打印两页，签字区在第 2 页。

[ONLYOFFICE 验收证据](acceptance/document_output/onlyoffice/README.md)含原生输出 PDF、报价截图和哈希清单。此次为后端原生导入／排版引擎验证，没有宣称浏览器编辑器交互或 Microsoft Excel 专项验收。没有为此新增 Drive／ONLYOFFICE 接入或修改运行服务配置。当前仅余 PR 审阅与合并。

无重复 DocType；无 ERPNext/Frappe Core、Bridge、Mercur 或生产修改；不新增其他需求。PR 待审阅及合并。合并后本阶段结束，本分支不再追加新需求。

## 修改文件清单

- `docs/DEVELOPMENT_PLAN.md`
- `docs/DOCUMENT_OUTPUT.md`
- `docs/DOCUMENT_OUTPUT_WORKSPACE_FINALIZE_ACCEPTANCE.md`
- `docs/DOCUMENT_OUTPUT_WORKSPACE_FINALIZE_PLAN.md`
- `docs/REQUEST_COLLABORATION.md`
- `docs/acceptance/document_output/quotation-dialog.png`
- `docs/acceptance/document_output/report-dialog.png`
- `docs/acceptance/document_output/request-dialog.png`
- `docs/acceptance/document_output/workspace.png`
- `docs/examples/document_output/README.md`
- `docs/examples/document_output/manifest.json`
- `docs/examples/document_output/检测委托单-示例.docx`
- `docs/examples/document_output/检测委托单-示例.pdf`
- `docs/examples/document_output/检测委托单-示例.xlsx`
- `docs/examples/document_output/检测报价单-示例.docx`
- `docs/examples/document_output/检测报价单-示例.pdf`
- `docs/examples/document_output/检测报价单-示例.xlsx`
- `docs/examples/document_output/检测报告-示例.docx`
- `docs/examples/document_output/检测报告-示例.pdf`
- `docs/examples/document_output/检测报告-示例.xlsx`
- `pyproject.toml`
- `reli_lims/document_output/__init__.py`
- `reli_lims/document_output/api.py`
- `reli_lims/document_output/mapping/__init__.py`
- `reli_lims/document_output/mapping/commission.py`
- `reli_lims/document_output/mapping/common.py`
- `reli_lims/document_output/mapping/quotation.py`
- `reli_lims/document_output/mapping/test_report.py`
- `reli_lims/document_output/registry.py`
- `reli_lims/document_output/renderers/__init__.py`
- `reli_lims/document_output/renderers/docx_renderer.py`
- `reli_lims/document_output/renderers/pdf_renderer.py`
- `reli_lims/document_output/renderers/xlsx_renderer.py`
- `reli_lims/document_output/service.py`
- `reli_lims/document_output/templates/commission/commission.docx`
- `reli_lims/document_output/templates/commission/commission.html`
- `reli_lims/document_output/templates/commission/commission.xlsx`
- `reli_lims/document_output/templates/quotation/quotation.docx`
- `reli_lims/document_output/templates/quotation/quotation.html`
- `reli_lims/document_output/templates/quotation/quotation.xlsx`
- `reli_lims/document_output/templates/test_report/test_report.docx`
- `reli_lims/document_output/templates/test_report/test_report.html`
- `reli_lims/document_output/templates/test_report/test_report.xlsx`
- `reli_lims/hooks.py`
- `reli_lims/public/js/document_output.js`
- `reli_lims/reli_lims/doctype/test_request/test_request.js`
- `reli_lims/reli_lims/doctype/test_request/test_request.json`
- `reli_lims/reli_lims/doctype/test_request/test_request.py`
- `reli_lims/reli_lims/workspace/testing_center/testing_center.json`
- `reli_lims/request_commercial.py`
- `reli_lims/tests/test_document_output.py`
- `tests/test_chinese_ui.py`
- `tests/test_distribution.py`
- `tests/test_document_output.py`
- `tests/test_document_output_ui.js`
- `tests/test_document_workspace.py`
- `tests/test_request_commercial.py`
- `tools/build_document_templates.py`

## ONLYOFFICE 补验文件

- `docs/acceptance/document_output/onlyoffice/README.md`
- `docs/acceptance/document_output/onlyoffice/long-quotation-appendix-xlsx.pdf`
- `docs/acceptance/document_output/onlyoffice/long-report-appendix-xlsx.pdf`
- `docs/acceptance/document_output/onlyoffice/manifest.json`
- `docs/acceptance/document_output/onlyoffice/quotation-page-1.png`
- `docs/acceptance/document_output/onlyoffice/quotation-page-2.png`
- `docs/acceptance/document_output/onlyoffice/检测委托单-示例-docx.pdf`
- `docs/acceptance/document_output/onlyoffice/检测委托单-示例-xlsx.pdf`
- `docs/acceptance/document_output/onlyoffice/检测报价单-示例-docx.pdf`
- `docs/acceptance/document_output/onlyoffice/检测报价单-示例-xlsx.pdf`
- `docs/acceptance/document_output/onlyoffice/检测报告-示例-docx.pdf`
- `docs/acceptance/document_output/onlyoffice/检测报告-示例-xlsx.pdf`
