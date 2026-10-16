# 检测委托单 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 Frappe Desk 提供检测委托入口，确认后创建唯一 ERPNext 项目，收样后生成实际样品及实验计划，并展示原生项目和任务。

**Architecture:** 原生可提交 Test Request 和四个平级子表记录客户委托范围。小型控制器校验及显式服务负责事务性生成，沿用 Sample/Test Program/Test Report，原始委托和实际执行以来源链接追溯。

**Tech Stack:** ERPNext/Frappe 16、Python、DocType JSON、Desk JavaScript、Frappe IntegrationTestCase、unittest、Node test。

**Spec:** `docs/superpowers/specs/2026-10-17-test-request-design.md`（用户已于 2026-10-17 确认）。

## Global Constraints

- 委托单创建时即填写产品名称、型号、数量、体积／外形尺寸和照片。
- 确认委托单时只自动创建一个 ERPNext Project。实际收样后沿用委托资料生成 Sample，再生成 Test Program。
- Project、Task、Customer、File 均复用 ERPNext/Frappe，不引入独立前端或复制财务模块。
- 方法与标准继续独立选择，不绑定成永久 1:1。
- 确认后的委托范围冻结。V1 不提供已确认委托的取消／改版流程。
- V1 每行一次生成一个 Sample，不实现同一行分批到货累计。
- 不以 ignore_permissions 绕过，不自动添加 ERPNext 角色。
- 数据库写入测试在隔离测试站运行，不能直接在 carl 运行全套测试。

## Review Focus

- API 伪造来源和只读项目链接：服务端拒绝篡改，Task 1/2/3/4 均覆盖来源校验。
- 断线重试及并发重复点击：只返回同一个项目／样品／计划；Task 2/3/4 测试不同数据库连接竞争及回滚。
- 无图片、同样品多图片和跨单文件：前两者可用、后者拒绝；Task 1/3 检查私有 File 和复制关联权限。
- 非整数／非有限／零负数量及空白编号：不能生成无效实际样品；Task 1/3 覆盖输入边界。
- 原有未关联委托的样品和计划：继续保存执行；Task 4/6 回归现有 acceptance 路径。

## 文件与接口约定

新建 DocType：`reli_lims/reli_lims/doctype/{test_request,test_request_sample,test_request_photo,test_request_item,test_request_item_sample}/`。按 Frappe 原生 DocType 创建流程生成文件，不手工 mkdir DocType 文件夹。

- `test_request.py`：validate、before_submit、on_submit、before_cancel；所有委托范围校验。
- `reli_lims/services/test_request.py`：`create_project(request) -> str`、`receive_samples(request_name: str, receipts: list[dict]) -> list[str]`、`make_test_program(request_name: str) -> str`。
- `reli_lims/services/request_files.py`：`validate_photos(request) -> None`、`copy_sample_photos(request, sample_code: str, sample) -> None`。
- `test_request.js`：动态编号选择、收样对话框、生成计划按钮、导航。仅服务 receive_samples/make_test_program 为登录用户 whitelisted，禁止 Guest。
- `Sample`：新增 `test_request` Link、`request_sample_row` Data(unique)、`dimensions` Small Text。
- `Test Program`：新增 `test_request` Link(unique，可空)。手工旧记录以上来源字段保持空值。
- `Test Report`：新增只读 `test_request` Link，由关联计划派生；用于查看来源和报告要求，不复制要求字段。
- 收样 payload：`[{"sample_code":"S1","quantity":1,"received_date":"2026-10-17","received_by":"user@example.test","condition":"Intact","difference_reason":""}]`。
- 子表字段：样品 `sample_code,customer_sample_code,product_name,model,quantity,dimensions,notes`；照片 `sample_code,photo,caption`；检测项 `item_code,test_method,standard,test_condition`；关系 `item_code,sample_code`。

## Task 1: 委托数据结构与草稿校验

**Files:** 新建五个 DocType、`reli_lims/services/request_files.py`、`reli_lims/tests/test_test_request.py`；修改 `tests/test_distribution.py`、`reli_lims/translations/zh.csv`。

**Interfaces:** 消费现有 Customer/Company/Test Method/Test Standard/File；输出合法 Test Request 草稿供后续提交和生成使用。

- [ ] 添加元数据和业务失败测试，断言：五个类型已安装、父类型可提交、子表平级；两样品三项目及多图有效；名称空白、数量 <=0/NaN/Infinity、重复编号、未知关系、缺少项目适用样品、无效报告份数／日期失败。共享 IntegrationTestCase fixture 创建唯一 Company、Customer、三个方法标准，创建最小有效委托：

```python
request = frappe.get_doc(dict(doctype='Test Request', title='DEMO Request',
    customer=self.customer.name, company=self.company.name,
    request_date=today(), delivery_date=add_days(today(), 7), report_copies=1,
    samples=[dict(sample_code='S1', product_name='Chamber', quantity=1,
                  model='A', dimensions='200 x 100 x 50 mm')],
    items=[dict(item_code='LT', test_method=self.method.name, standard=self.standard.name)],
    sample_assignments=[dict(item_code='LT', sample_code='S1')]))
```

- [ ] 本地运行 `python3 -m unittest discover -s tests -p 'test_*.py'`；隔离站运行 `bench --site <acceptance-site> run-tests --app reli_lims --module reli_lims.tests.test_test_request`。实际命令中的 acceptance-site 必须由运行时确认的隔离站名称替换，禁止 carl。Expected: 新类型缺失／标签断言 RED；环境连接失败不能记为 RED。
- [ ] 通过原生 DocType 创建流程生成五个类型；添加必填字段、角色矩阵和提交权限，仅 Manager submit，无 cancel/amend 权限。通过 `math.isfinite(float(value))` 验证数量；编号使用 strip 后唯一集，关系使用 pair set 检查重复和成员资格。报告份数必须正整数；交付日期不得早于委托日期。
- [ ] 照片校验要求 `File(file_url=photo,is_private=1,attached_to_doctype='Test Request',attached_to_name=request.name)` 存在；要求该 File 的 read 权限且文件类型为图片。测试公共文件、跨单文件、外部 URL 被拒绝；无照片合法。Expected: 新测试及原本地套件 GREEN。
- [ ] Commit: `feat: add test request masters and scope validation`。

## Task 2: 确认并事务性创建项目

**Files:** `test_request.py`、`reli_lims/services/test_request.py`、`test_test_request.py`。

**Interfaces:** 消费 Task 1 草稿，输出只读 `project,confirmed_by,confirmed_on`；`create_project(request)` 只在提交生命周期中调用。

- [ ] 测试保存草稿不建 Project，提交创建一个 Project，客户／公司／expected_end_date 正确，只建项目不建 Sample/Task/Program；工程师 submit 拒绝；缺 Project create 权限拒绝；伪造 project／确认人字段拒绝。Expected: 新行为 RED。
- [ ] before_submit 要求 Lab Manager 并锁定来源委托行，重载数据库已有链接；不得信任客户端 project。`create_project` 使用正常 `frappe.get_doc(...).insert()`，project_name 为委托编号加标题、customer/company/expected_end_date 从委托读取。on_submit 回写关联和确认信息，不显式 commit。提交后的只读链接字段允许内部写入，但拒绝来自普通 update 的篡改。before_cancel 一律拒绝本期确认单取消。
- [ ] 测试 Project 插入之后人为异常的整个提交事务回滚；重试只产生一个 Project。并发测试使用两个独立连接对同一个已提交基线草稿执行提交：一个成功，另一个返回已有项目或明确并发异常；最终 SQL COUNT 恰好 1，所有异常必须断言类型，连接 finally rollback/destroy。测试隔离 fixture 在独立站建立并清理，不在业务站提交测试数据。Expected: 所有拒绝路径无孤立项目。
- [ ] 运行委托 integration 模块和现有 app integration suite，Expected: GREEN；Commit: `feat: create ERPNext project on request confirmation`。

## Task 3: 收样和多照片沿用

**Files:** Sample JSON/controller、`test_request.py`、`services/test_request.py`、`services/request_files.py`、`test_test_request.py`。

**Interfaces:** 消费已确认委托和 receipts payload；输出 Sample 名称列表，保存 `test_request,request_sample_row,dimensions`。

- [ ] 测试草稿不能收样、未知行拒绝、重复 payload 行拒绝、日期／接收人／有限正数量校验、数量不同但说明为空拒绝。测试正常收样沿用名称型号尺寸、委托项目及多张照片，缺 Sample create/File create 权限不得越权。Expected: 服务缺失 RED。
- [ ] 服务先校验登录、角色、来源读权限、目标创建权限；锁定委托行，检查 docstatus==1；只从已确认委托读取业务范围。为每个 receipt 创建 Sample，使用真实接收数量/日期/接收人，source row 使用委托样品子行 name，重复请求查询该唯一键并验证仍属同一项目后返回已有记录。
- [ ] 实际数量不同则将差异原因记入 Sample.notes；重复请求若实际数量等参数不同，明确冲突，不能静默覆盖已有收样。普通 Sample 更新中源字段不可重指向其他委托行，project 必须与来源匹配。
- [ ] `copy_sample_photos` 为相同私有文件内容建立目标 Sample 的 File 关联，保留来源附件，使用原生 File API 和正常权限；禁止公开文件或其他来源文件。新建过程中错误必须整体回滚。
- [ ] 测试重复与双连接并发收样只有一个 Sample、故障回滚无孤立 File 记录、原样品附件仍存在，匿名不能下载。运行 app integration suite，Expected: GREEN；Commit: `feat: receive request samples with private photo provenance`。

## Task 4: 生成实验计划并贯通报告来源

**Files:** Test Program JSON/controller、Test Report JSON/controller、`services/test_request.py`、`test_test_request.py`、`test_execution.py`。

**Interfaces:** 消费 confirmed request 和来源 Sample；`make_test_program(request_name)` 返回唯一计划名；报告 `test_request` 从实际计划派生。

- [ ] 测试未确认／未收齐拒绝并列出缺失样品编号；两样品三项目的六条关系准确，方法标准条件独立复制，items Pending，program Draft，planned_end 为委托交付日期。测试重复调用保留原有人工修改、并发只一个计划。Expected: 新服务 RED。
- [ ] 服务验证来源读权限、计划 create 权限；来源行锁保护；读取 `Sample.request_sample_row` 映射并核对项目和委托，不仅信任客户端 Link。创建 samples/items/sample_assignments 三个平级子表；使用每个委托项目 item_code 映射，不自动创设备／人员／Task。由唯一 test_request 来源字段兜底重复生成。
- [ ] Test Program/Report validate 在来源存在时校验项目和来源一致、来源字段不可篡改；报告来源由计划派生，旧计划来源为空时报告来源也为空。保持既有执行和报告冻结规则。
- [ ] 在 integration 测试里从生成计划走 Ready/Running/Completed/Reviewed，再走报告签发；旧无委托 acceptance 测试同样通过。Expected: app suite GREEN；Commit: `feat: generate test programs from received requests`。

## Task 5: Desk 操作和项目任务入口

**Files:** `test_request.js`、`tests/test_test_request_desk.js`、Testing Center workspace JSON、相关原生导航配置、`tests/test_distribution.py`、`reli_lims/translations/zh.csv`。

**Interfaces:** 消费上述服务接口及返回名称；输出 native Desk 按钮与原生 Project/Task 页面入口。

- [ ] Node 测试先模拟 `frappe.ui.form.on`、frm 和对话框接口，断言草稿没有收样按钮、确认后显示、取消对话框不发请求、成功后导航到返回单据；编号 Autocomplete label 转义但 value 保持原值；receipt 只含选中行且每行接收字段独立。Expected: JS 文件缺失 RED。
- [ ] 实现动态 sample_code/item_code 选项和图片归属选择；编号已有关联时删除先提示而不是静默删除关系。收样对话框默认沿用预计数量并允许实际差异；调用服务期间禁用重复按钮，失败显示服务错误，成功刷新来源链接。
- [ ] 工作台和现有原生 Sidebar 导航加入 Test Request/Project/Task；更新分发测试所需快捷集合，不修改 ERPNext 权限。报告中提供来源 Link，打开即可查看报告要求。
- [ ] 翻译委托、收样、报告要求、尺寸和项目任务标签，保留 scoped Issued 翻译。运行 `node --test tests/*.js` 和本地 unittest，Expected: GREEN；Commit: `feat: expose laboratory intake projects and tasks in Desk`。

## Task 6: 安装回归、验收与交付

**Files:** `docs/ARCHITECTURE.md`、`docs/DATA_MODEL.md`、`docs/ERPNEXT_INTEGRATION.md`、`docs/DEVELOPMENT_PLAN.md`、`docs/DESK_DEMO.md`、`docs/DESK_ACCEPTANCE_LOG.md`。

**Interfaces:** 消费完整链路；输出可重复的操作说明、版本提交和验收证据。

- [ ] 隔离站安装/迁移 app，运行所有 app integration tests（含权限与文件）、新本地 unittest/Node tests；记录真实命令、测试数和异常。若隔离站仍无法连接，完成不依赖数据库的工作但不宣称 integration 通过，不以 carl 代替全套测试。
- [ ] 更新模型和操作说明：一单一项目、确认冻结、每行一次收样、多图、全部收齐才生成计划、已有业务路径兼容；同步 spec 审批状态与所有设计裁决记录。
- [ ] 新鲜上下文整体代码审查，重点检查并发锁、普通用户服务权限、来源篡改和跨单私有文件。修复重要发现时先复现失败再修正，完整测试重新绿色。
- [ ] 部署前记录 carl 当前版本并备份站点；仅部署本 app、定向迁移和必要缓存。浏览器用明确 DEMO 标识数据验证两样品多图→确认一个项目→收样→三项计划→审核→签发；项目和任务页可进入。不提交财务记录、不重置凭据、不自动扩展角色。
- [ ] 保存截图、所有生成记录编号及匿名文件拒绝证据，区分单账号验收与跨角色验证。提交并推送现有开发分支；main 合并按既有明确授权与实际测试状态执行，不将未通过验收的改动默认为可合并。

## 计划自检

设计各节对应 Tasks 1–6；四张平级子表、来源字段、收样 payload 和服务签名一致。照片复制、并发、差异说明、已确认冻结、项目权限失败和旧记录兼容均有测试归属。无新财务流程、独立前端、自动任务复制或隐式角色授权。当前阶段仅文档，尚未实施代码；执行前需用户审阅本计划，沿用已指定 executing-plans 方式。
