# Reli LIMS 文档输出与检测工作台最终收口计划

> 分支：`codex/document-output-workspace-finalize`
>
> 目标：在不改 ERPNext/Frappe Core、不新增重复业务 DocType 的前提下，完成检测工作台入口整理，并把 Quotation / Test Request / Test Report 的文档输出统一收口。

## 0. 开始前约束

1. 先 `git fetch origin`，确认本分支基于最新 `main`。
2. 如果前一个 Codex 窗口的 Document Output 改动尚未合并到 `main`，先不要重复实现；应先完成上一轮的提交、测试、PR 和合并，再把本分支 rebase/merge 到最新 `main` 后继续。
3. 不修改 ERPNext/Frappe Core。
4. 不修改 `mercur_erpnext` Bridge。
5. 不新增 Reli Customer / Reli Quotation / Reli Sales Order / Reli Invoice / Reli Payment 等重复 DocType。
6. 不接 Drive/ONLYOFFICE 自动化，不直接部署生产。

## 1. 本轮只做两件事

### A. 检测工作台整理

直接修改现有：

`reli_lims/reli_lims/workspace/testing_center/testing_center.json`

不要新建第二个 Workspace。

保留现有六张数字卡片、八阶段 Kanban、Test Request / Test Program / Test Report 主流程，不推翻 V1。

将 Workspace 整理为以下分区：

### 客户与销售

复用 ERPNext 原生 DocType：

- Customer → 客户
- Contact → 联系人
- Address → 地址
- Quotation → 报价单
- Sales Order → 销售订单

高频 Shortcut 建议只保留：

- 新建客户
- 新建报价单
- 报价单列表
- 销售订单

### 检测业务

复用现有 Reli LIMS：

- Test Request → 检测委托
- Sample → 样品
- Test Program → 试验方案
- Test Report → 检测报告

主流程表达：

`报价 → 委托 → 收样 → 试验 → 报告 → 完成`

其中 Quotation 仍是 ERPNext 原生；Test Request 仍是 Reli LIMS 原生，二者不要合并成同一个 DocType。

如果当前没有关联字段，可给 Test Request 增加可选 Link：

- `quotation` → Quotation
- `sales_order` → Sales Order（可选）

必须支持直接送检，不强制 Sales Order：

- `Quotation → Sales Order → Test Request`
- `Customer → Test Request`

### 检测资源与字典

- Test Method → 检测项目
- Test Standard → 检测标准
- Asset → 设备
- Project → 项目
- Task → 任务

Project / Task 降低首页优先级，不要占高频 Shortcut。

### 财务

只提供 ERPNext 原生入口：

- Sales Invoice → 销售发票
- Payment Entry → 收款

不要在 Reli LIMS 重写财务逻辑。

## 2. Document Output 统一收口

Document Output 必须是跨 DocType 的输出能力，而不是某一个单据专用导出。

第一批固定支持：

### ERPNext Quotation

生成：

- PDF（默认）
- DOCX
- XLSX

XLSX 第一份真实模板使用现有报价单：

`晟楠报价单-隔振器-振动试验-报价-1.xlsx`

不要重新画无格式 Workbook；必须基于模板保留字体、边框、合并单元格、打印区域、签字区等。

### Reli LIMS Test Request

生成“检测委托单”：

- PDF（默认）
- DOCX
- XLSX

### Reli LIMS Test Report

生成“检测报告”：

- PDF（默认）
- DOCX
- XLSX

## 3. 页面入口统一

Quotation、Test Request、Test Report 页面统一使用一个按钮：

`生成文档`

弹窗：

- 模板
- 格式：PDF / Word / Excel
- PDF 默认

不要同时保留一堆重复按钮，例如“导出 Excel / 导出 Word / 下载 PDF / 打印报告”。

## 4. 技术边界

统一流程：

`源 DocType → Mapping/Context → Template → Renderer → 文件`

Renderer 建议：

- PDF：优先复用 Frappe Print Format / Jinja / PDF 能力
- DOCX：模板化生成，优先保留模板原格式
- XLSX：`openpyxl` 基于模板填充，支持动态行和样式复制

业务数据查询、权限、字段拼装放 Mapping/Service；Renderer 不写检测业务逻辑。

Document Output 必须检查当前用户对源文档的读取权限；无读取权限不得生成文件。

## 5. Workspace 最终目标

检测工作台首页保持简洁：

1. 状态数字卡片
2. 主流程 Kanban
3. 高频检测操作
4. 客户与销售
5. 检测资源与字典
6. 财务入口

避免同一 DocType 在 Shortcut、Card、Link 中无意义重复。

## 6. 本轮明确不做

- 不新增重复客户/报价/订单/财务 DocType
- 不重做 V1 委托单结构
- 不重做报告状态机
- 不重写 Project/Task
- 不改 Bridge
- 不接 Mercur
- 不接 Drive 自动上传
- 不接 ONLYOFFICE API
- 不做模板在线设计器
- 不做 AI 自动模板
- 不直接部署生产

## 7. 验收标准

### Workspace

能从检测工作台访问：

- Customer
- Contact
- Address
- Quotation
- Sales Order
- Test Request
- Sample
- Test Program
- Test Report
- Test Method
- Test Standard
- Asset
- Sales Invoice
- Payment Entry

且全部引用现有 DocType。

### 文档输出

Quotation、Test Request、Test Report 均有统一“生成文档”入口。

三类文档均支持：

- PDF
- DOCX
- XLSX

PDF 默认。

Quotation XLSX 使用真实报价模板并验证 Excel / ONLYOFFICE 可正常打开。

### 数据关系

支持 Test Request 可选关联 Quotation / Sales Order，不复制形成第二套销售数据。

### 权限

所有原生 ERPNext DocType 继续使用 ERPNext/Frappe 原生权限；Document Output 不绕过读取权限。

## 8. 测试与交付

至少完成：

- Workspace 配置回归
- Mapping 单元测试
- XLSX Renderer 测试
- DOCX Renderer 基础测试
- PDF Renderer 基础测试
- XLSX 动态明细扩行
- 中文文件名
- 空字段
- 权限拒绝测试

完成后输出：

1. 修改文件列表
2. Workspace 前后结构对比
3. 新增字段列表
4. Quotation / Test Request / Test Report 三处生成入口说明
5. PDF / DOCX / XLSX 示例生成结果
6. 测试结果
7. 是否存在任何重复 DocType（预期：没有）
8. 尚未完成项

## 9. 收口规则

完成本轮后：

1. 更新实施日志/本计划的完成状态。
2. 提交全部改动。
3. Push 当前分支。
4. 开 PR 到 `main`。
5. PR 只描述本轮 Workspace + Document Output 收尾，不混入其他项目。
6. 测试通过后合并，至此 Reli LIMS 当前这一阶段结束，不继续在同一分支追加新需求。

## 10. 本轮实施状态（2026-10-29）

用户已明确授权：前一轮 Document Output 未落地时，允许在本分支补齐后继续收口。已完成缺失模块，没有重复搬入不存在的实现。

- [x] fetch、最新 main／分支／上一轮 PR 和提交核查；安全复用可选商业来源提交。
- [x] 整理现有 Testing Center；保留六卡、八阶段及检测主线，接入原生销售／财务。
- [x] Test Request 可选 Quotation／Sales Order、读取权限及客户／公司／来源完整性校验。
- [x] 三类单据统一“生成文档”，三格式、默认 PDF。
- [x] Quotation XLSX 使用指定真实模板，保留格式、动态扩行及签字区。
- [x] 权限、Mapping、三 Renderer、动态行、中文／空字段、长文本续页测试。
- [x] 隔离站点完整 Frappe 回归、真实浏览器 Workspace／表单验收、九份示例与视觉检查。
- [x] 更新开发计划、模块文档与验收记录。
- [ ] Excel／ONLYOFFICE 原生应用打开验收：当前环境缺少这两种应用；openpyxl／LibreOffice Calc 打开及打印已通过，合并前需补验。
- [ ] PR 审阅与合并；合并后本阶段正式结束，不在本分支追加新需求。

详见 [验收记录](DOCUMENT_OUTPUT_WORKSPACE_FINALIZE_ACCEPTANCE.md)、[模块说明](DOCUMENT_OUTPUT.md)、[九份示例](examples/document_output/README.md)。提交／Push／PR 状态以本分支 Git 和 GitHub 为准。
