# Workspace V2 — Sprint 0 审计报告

> 状态：只审计，不改业务模型。依据 `docs/WORKSPACE_V2_PLAN.md` Sprint 0 要求产出。
> 日期：2026-10-24。基准：`main @ e5f5c80`（已同步 origin/main）。

## 审计范围

读取：
- `AGENTS.md`
- `docs/ARCHITECTURE.md`
- `docs/DATA_MODEL.md`（含 V1 收口）
- `docs/ERPNEXT_INTEGRATION.md`
- `docs/SELLER_WORKBENCH_INTEGRATION.md`
- `docs/V1_CONVERGENCE_PLAN.md`
- 当前 `Testing Center` workspace JSON：`reli_lims/reli_lims/workspace/testing_center/testing_center.json`
- 配置代码：`reli_lims/setup_v1.py`、`reli_lims/progress.py`、`reli_lims/seller_workbench.py`、`reli_lims/fixtures/role.json`
- 实施记录：`docs/IMPLEMENTATION_LOG.md`、`docs/CAPABILITIES-AND-BOUNDARIES.md`

本阶段不新增业务 DocType、不改数据模型。

---

## 一、当前 Workspace 结构（检测工作台）

单一二级 Workspace：`Testing Center`，中文标签「检测工作台」，`module=Reli LIMS`，`public=1`。

角色（都看同一页）：`Lab Manager` / `Lab Engineer` / `Lab Reviewer`。

| 区块 | 内容 | 实现方式 |
|---|---|---|
| 第一行 · 关键数字 | 6 张 Number Card：待确认委托 / 待收样 / 试验中 / 待报告 / 报告待审核 / 超期 | 全部基于 `Test Request.business_stage` 过滤；「超期」用 `delivery_date < today` 动态过滤 |
| 主流程看板 | 「检测主流程」Kanban（8 列），链接为静态段落 | 基于 `Test Request.business_stage`，列 = 待确认→待收样→已收样→待试验→试验中→待报告→报告审核→已完成 |
| 常用操作 | 6 个快捷入口：新建检测委托 / 收样 / 试验方案 / 检测报告 / 检测项目 / 检测标准 | Shortcut，「收样」带 `business_stage=待收样` 过滤 |
| 二级资料 | 卡「项目与基础资料」：样品列表 / 项目 / 任务 / 设备 / 客户 / 历史报告 | Link 卡片 |

无 `charts`、`reports`、`quick_lists`、`custom_blocks`（Phase 7 的报表未落地）。

## 二、可复用资产（V2 直接复用）

1. **阶段引擎（最关键）**：`progress.py` 的 `STAGES`（8 阶段）+ `business_stage()` + `refresh_request()` + `overdue()`。这是全仓唯一业务阶段来源，V2 所有数字卡/看板/待办都应继续复用，不新造。
2. **Test Request 派生汇总字段**：`business_stage`、`overdue_status`、`sample_summary`、`test_summary`、`responsible_engineer`、`delivery_date`。是 V2「我的工作/超期/流程卡」的直接数据源。
3. **6 张 Number Card**：已存在且查询有效，V2 第一行 KPI 可直接沿用。
4. **「检测主流程」8 列 Kanban**：已存在，V2 第二行主流程可复用并加每阶段计数。
5. **6 个高频 Shortcut**：已存在，V2「常用操作」直接沿用。
6. **幂等配置模式**：`setup_v1.py` 的 `_upsert()` + `after_migrate()`，新增卡片/看板可沿用，避免重复创建。
7. **角色**：Lab Manager / Lab Engineer / Lab Reviewer 已建；另有 `Mercur Integration`、`Laboratory Directory Reader`（非桌面）供集成用。
8. **Bridge 侧只读能力**：`seller_workbench.py::request_summary()` 已实现私有履约摘要（公司归属校验），可作集成状态的雏形。

## 三、V2 需求 vs 现状（缺失项）

| V2 要求 | 现状 | 差距 |
|---|---|---|
| 顶部 KPI 含「同步异常」 | 6 卡，无同步异常 | ❌ 缺 Bridge/集成异常卡 |
| 「我的待办/我的工作」（按角色） | 无 | ❌ 缺。Engineer 待试验/进行中/待补结果；Reviewer 待复核/待审核；Manager 全局异常 |
| 主流程每阶段显示数量 + 超期 + 可点击 | 只有静态 Kanban 链接 | ❌ 缺每阶段计数与超期数 |
| 常用操作集中 | 已有 6 快捷入口 | ✅ 基本满足 |
| 基础资料下沉 | 已有二级卡 | ✅ 满足 |
| 一级 Business Hub | 无（只有二级检测工作台） | ❌ 缺 |
| Bridge 集成中心（健康/入口，仅管理员） | 无 | ❌ 缺 |
| 文档中心 / 中国化 / 知识库入口（模块缺失时降级隐藏） | 无 | ⚠️ 缺，但 V2 允许降级隐藏，非阻塞 |
| 跨角色差异化视图 + Business/Customer Service + Integration Manager 角色 | 三实验室角色同页 | ❌ 缺角色差异化与新增角色 |
| 点击数字卡进入真实列表 | 已实现并验收 | ✅ 满足 |
| 全中文 UI / 原生 Desk | 已实现 | ✅ 满足 |

## 四、与现有模型冲突检查

**结论：无模型冲突。** 理由：

- V2 计划明确「不重写 Reli LIMS、不换 DocType、不建 SPA」，与本仓 `AGENTS.md` 硬约束一致。
- V2 阶段序列 `待确认→待收样→已收样→待试验→试验中→待报告→报告审核→已完成` 与 `progress.STAGES` 完全一致，可零改动复用阶段引擎。
- V2 全部数字卡/看板均以 `Test Request` + `business_stage` 为源，不需要新增业务 DocType。

**需要注意的对齐点（非冲突，Sprint 内处理）：**

1. **命名一致性**：现有数字卡 label「报告待审核」（filter `business_stage=报告审核`）；V2 叫法「待审核」。需统一卡片 label 与阶段名，避免用户困惑。
2. **Bridge 跨仓依赖**：V2 Sprint 2 的「同步异常/集成健康」数据源在 Bridge / `mercur_erpnext` 仓库（不在本仓）。`AGENTS.md` 与 V2 计划都禁止本仓 `import` 对方业务代码。Sprint 2 需以「薄状态读取或纯入口」实现，不允许反向依赖——这是唯一真正的跨仓约束。
3. **角色差异化可见性**：Number Card 与 Workspace 段落需按角色控制可见；现有 3 个实验室角色同页，需先确认各角色对 `Test Request/Test Program/Test Report` 的实际读权限再配置。
4. **「我的待办」过滤**：需按当前用户（`responsible_engineer` / `owner` / 审核人）做动态过滤，Frappe Number Card 支持 `frappe.session.user` 动态过滤器，可行但需逐一验证。

## 五、对 Sprint 1 的建议（重构检测工作台）

建议 Sprint 1 按以下顺序实施，全部沿用现有阶段引擎与卡片：

1. **第一行 KPI**：保留现有 6 卡，同步异常待 Sprint 2 有真实 Bridge 数据源后再增加，不显示占位数字；统一「报告待审核/待审核」命名。
2. **第二行主流程**：把静态 Kanban 链接升级为 8 个可点阶段块，每块显示数量 + 超期数，点击进对应过滤列表/Kanban。
3. **第三行「我的工作」**：按角色加 3 个子区（Engineer / Reviewer / Manager），用动态过滤器取当前用户数据。
4. **第四行常用操作**：沿用现有 6 Shortcut。
5. **第五行业务资料**：沿用现有「项目与基础资料」卡，下沉。
6. **回归**：保持中文、原生 Desk、无新 DocType；复用 `setup_v1._upsert` 保证幂等。

Sprint 1 完成标准对齐 V2 计划 §3 与验收（无效链接 0、数字与列表一致、角色差异正确）。

---

> 本审计只读未改动业务模型；是否开始 Sprint 1 待确认。

---

## Sprint 1 实施记录（2026-10-24）

重构 `检测工作台` 为业务驾驶舱，全部原生实现（无新 DocType、无前端）。

| 行 | 内容 | 实现 |
|---|---|---|
| 第一行 关键状态 | 7 张 KPI 卡：待确认委托 / 待收样 / **待试验(新)** / 试验中 / 待报告 / 报告待审核 / 超期 | 原生 Number Card，均基于 `Test Request.business_stage` |
| 第二行 主流程看板 | 原生 8 列 Kanban「检测主流程」 | 复用现有 `progress.STAGES`，保持不变 |
| 第三行 我的工作 | **我的待试验 / 我的进行中 / 我的待报告**（按当前用户） | 原生 Number Card，`responsible_engineer = frappe.session.user` 动态过滤 |
| 第四行 常用操作 | 新建检测委托 / 收样 / 试验方案 / 检测报告 / 检测项目 / 检测标准 | 沿用 6 个原生 Shortcut |
| 第五行 业务资料 | 项目与基础资料（样品/项目/任务/设备/客户/历史报告） | 沿用二级卡 |

关键点：
- 个人卡不按角色隐藏，而是按 `responsible_engineer` 数据作用域——每个实验员看到自己负责的委托；Lab Reviewer/Manager 按各自数据看到对应区。这是原生能力（Number Card 无角色字段）下的稳妥实现。
- 待办/超期与列表点击一致性：9/10 卡与直接查询一致；「超期」沿用 V1 生产已验证的动态日期卡。
- 「同步异常」卡与 Bridge 集成卡延后到 Sprint 2（数据源在 Bridge/mercur 仓库，本仓无对应 DocType，Sprint 1 不建无效入口）。

验证：
- 静态：`setup_v1.py` 语法、`testing_center.json` 合法、卡片/快捷/链接引用闭合、DocType 全部有效。
- 运行时（dev bench 192.168.10.204 站点 `carl`）：导入 workspace JSON + `after_migrate` 后，10 张 Number Card 全部创建、workspace 23 块/5 分区、8 列 Kanban 完好、个人卡动态过滤含 `frappe.session.user`。
- 待用户浏览器视觉确认最终渲染。


## 2026-10-25 结构与交互复核

唯一依据为 WORKSPACE_V2_PLAN.md 和当前仓库代码，不引用概念图/UI 图片。

### 已确认可复用

Testing Center 原生 Workspace：7 张全局委托状态卡、3 张委托负责人个人卡；6 个 Shortcut；项目与基础资料区；8 列原生 Kanban。Number Card 使用 Document Type/Count，日期及当前用户为动态过滤；块引用使用 Workspace 行 label，不能改用底层卡片 ID。没有独立 SPA 或新增业务 DocType。

### 当前发现与修正

- 本地分发测试仍要求 6 张卡，实际已为 10 张，导致基线测试失败；已更新为精确标签集、唯一 ID 及原有引用闭合验证。
- 个人卡基于 Test Request.responsible_engineer，只能说明“我负责的委托”，不能声称按 Test Program Item.engineer 统计实验员逐项任务。工作台增加明确口径说明；尚未实现逐项任务计数。
- 原记录“个人数据作用域等同角色分区”的表述不满足计划 §3.3：负责人过滤不等同 Reviewer/Manager 的专属待办，更不是权限隔离。不能将 Sprint 1 标记为完全验收。
- 原建议同步异常占位违反真实数据原则，已移除；未接入不显示正常或 0。

### 剩余缺口（按结构先行顺序）

1. 工程师逐项待执行/待补结果、审核员待复核/待审核、经理待分配/异常等真实入口。Test Program Item 是子表，不能直接当独立列表入口或忽略父文档权限统计；优先用原生 Report 展示父方案关联任务。
2. 标准/方法仍在高频快捷区，应下沉资料区；常用操作应对应收样、方案、结果和报告真实动作。创建/修改操作需核对角色权限，不能只隐藏按钮。
3. 主流程当前只有总看板链接，未逐步骤提供数量及超期。必须与真实过滤列表保持一致，保留内部八阶段模型，不为七个展示步骤重写状态引擎。
4. Number Card 运行时：前记录为 9/10 查询一致，超期卡未计入本次逐卡验证；不能视为所有卡通过。还需在测试站点按当前用户核对动态日期、负责人过滤、点击列表数量及无权限用户访问。
5. Business Hub、Bridge 健康摘要及可选模块降级尚未实现。须先发现已安装 App/DocType/角色和真实同步状态字段；不猜链接、不跨 App import 业务实现、不暴露密钥。
6. 低权限角色验收尚未覆盖，尤其 Business/Customer Service 不能因为看总览就获得原始数据或内部审核意见。

本轮仅修复已确认的静态测试问题和个人卡口径说明。未进行部署、数据库卡片计数核对或低权限浏览器验收，未宣称 V2 完成。后续按上述顺序补功能，不以视觉对齐替代业务验收。

## 2026-10-25 继续实施：流程入口与任务队列

- 主流程增加 8 个原生 Shortcut，保留真实八阶段；每个使用 Test Request.business_stage 和 docstatus != 2，数量与点击由同一原生过滤定义驱动。没有为展示顺序改业务状态。
- 新增原生 Script Report `Laboratory Work Queue`（检测任务队列），不是业务 DocType 或 SPA。工程师/经理可查看自己的待执行、进行中、待补结果；审核员/经理可看 Completed 待复核；经理可看未分配的 Pending/Ready。服务器角色门禁与页面筛选同时存在，客户端不能指定其他 engineer 冒充当前用户。
- 报表先 get_list 获取可读且未取消的父方案，再限定 parent/parenttype/parentfield 查询检测子项；不使用任意全量 SQL。只输出任务导航字段，不输出结果正文或结论。超过500个可读方案要求选择方案，不静默截断。待补结果是 Running 且结果或结论未齐的操作提示，不表示已完成。
- 检测标准/方法移至资料区。原10张 Number Card 保留，个人卡仍明确是委托负责人口径。
- 不伪造同步状态，不增加 Bridge、客户敏感资料或资源冲突占位卡。角色专属入口使用同一原生 Report，由角色控制筛选及服务器执行；尚未声称 Workspace 整块按角色分区已完成。

本地验证：18项 unittest、Python compileall、报表 JS 语法与 diff 检查通过。数字卡逐卡运行时一致性、低权限角色、可选集成仍须继续验收；不能以单元测试替代这些验收。

## 临时角色验收（2026-10-25）

用户无测试账号，因此不创建持久登录账号；在独立验收站点运行 IntegrationTestCase，临时建立单一实验员/审核员/经理用户，关闭欢迎邮件并由事务回滚。

4项真实数据库测试全部通过：Guest 队列拒绝、三角色与五种队列的允许/拒绝矩阵、委托提交和系统/集成权限不扩大、三角色下10张数字卡的原生计数与权限过滤列表一致（30组比较）。动态表达式仅解析已知当前用户/当前日期，不执行任意表达式。本地18项检查仍通过。

边界：任务队列可能为空，本轮验证入口权限和计数查询一致，不证明有真实任务时的跨用户/跨组织隔离；自动测试将动态过滤解析为服务器用户/日期，不等同浏览器点击路径验收。真实低权限登录页面验收仍未完成，不要求用户提供密码。

## 视觉收口（2026-10-25）

用户本轮明确提供参考图并要求保持功能，采用浅蓝底、白色原生卡片、状态强调线、清晰字号和响应式分区。只新增 scoped CSS 与 Workspace 标题说明；卡片查询、链接、角色和执行规则未变，不复制图中示例数字/同步状态，不建立 SPA。Frappe 侧栏保持原生。

样式使用 CSS @scope 与 Testing Center 专有块标识限定，不影响委托/报告表单及其他 Workspace。新增静态资源版本参数防止旧缓存。审查发现56列网格的列间距会在手机溢出，已改为零列间距加块内边距。实际834px窗口确认网格生效、数字30px、无横向溢出；点击收样阶段仍进入真实筛选列表（1条）。18项本地检查通过。未完成所有浏览器/所有窄屏及深色模式的视觉验收，不把 CSS 媒体规则视为全尺寸实测。
