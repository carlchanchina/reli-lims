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

1. **第一行 KPI**：保留现有 6 卡，补「同步异常」卡（先占位，Sprint 2 接 Bridge）；统一「报告待审核/待审核」命名。
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
