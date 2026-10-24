# ReliLab / Wekona Workspace V2 开发计划

> 目标：在现有 Frappe / ERPNext / Reli LIMS 基础上，把默认“模块菜单页”升级为业务驾驶舱；保持各业务模块独立，通过统一 Workspace 与 Bridge 组合，不新建独立 SPA。

## 1. 设计结论

本次不重写 Reli LIMS，不替换现有 DocType，不另建 React/Next/Vue 管理后台。

采用两级 Workspace：

1. **一级：统一业务工作台（Business Hub）**
   - 面向管理员、业务负责人、客服/运营。
   - 只负责总览、跨模块待办、入口和集成状态。
   - 组合现有模块，不复制其业务数据。

2. **二级：检测工作台（Testing Center）**
   - 面向实验室经理、实验员、审核员。
   - 专注检测履约流程：委托 → 收样 → 方案 → 试验 → 报告 → 审核 → 完成。

各模块仍保持独立：

- Reli LIMS：检测中心
- wekona_documents：文档中心
- Bridge / mercur_erpnext：集成中心
- ERPNext Customer / Contact / Project：客户与项目主数据
- wekona_china：中国化、本地工商/税务/字段扩展
- WeKnora：标准、知识、文档知识化

原则：**统一入口，不统一数据模型；统一体验，不把模块揉成一个大 App。**

---

## 2. 一级 Workspace：统一业务工作台

建议名称：

- 内部名：`Business Hub`
- 中文名：`一体化业务工作台`

### 2.1 顶部 KPI

第一屏只显示业务状态，不显示技术 DocType：

- 待确认委托
- 待收样
- 试验中
- 待报告
- 待审核
- 同步异常

点击数字必须进入带筛选条件的真实列表。

### 2.2 我的待办

按登录用户角色显示：

- 待确认委托
- 待收样
- 待执行试验
- 待补录结果
- 待审核报告
- 文档待审核
- Bridge 同步失败（仅管理员）
- 客户资料待补齐（业务/管理员）

### 2.3 核心模块入口

使用卡片，而不是平铺 DocType：

#### 检测中心

说明：从委托到报告的实验室履约。

快捷入口：
- 新建检测委托
- 收样
- 试验任务
- 报告

#### 文档中心

说明：PDF/Office/扫描件解析、人工审核、结构化、发布与归档。

快捷入口：
- 文档收件箱
- 待审核
- 结构化输出
- 发布 / 归档

注意：本仓库不实现文档业务本身，只提供入口、状态聚合或跨模块链接；文档业务属于 `wekona_documents`。

#### Bridge 集成中心

说明：连接网站、Mercur、ERPNext、Reli LIMS、WeKnora 等系统。

快捷入口：
- 集成连接
- 同步任务
- 同步日志
- 失败重试

Bridge 负责：
- 身份与主体映射
- Customer / Contact 映射
- Seller / Laboratory Profile 映射
- Order / Service / Test Request 映射
- 状态同步
- 报告 / 附件回传
- Webhook / API
- 幂等、重试、审计日志

Bridge 不负责：
- 检测业务规则
- 文档解析规则
- ERPNext 会计核心
- 中国税务业务规则

#### 客户中心

说明：统一使用 ERPNext Customer / Contact / Project 作为客户与项目主数据。

快捷入口：
- 客户
- 联系人
- 项目
- 商机 / 报价（存在时）

不得在 Reli LIMS 再复制一套 Customer 主表。

#### 中国化

说明：由 `wekona_china` 提供中国企业字段、工商补齐、统一社会信用代码、本地发票/税务与本地化配置。

本工作台只显示：
- 企业资料待补齐
- 工商同步状态
- 发票/税务入口（模块存在时）
- 中国化设置

不得把中国化字段硬编码进 Reli LIMS 核心 DocType。

#### 知识与标准

说明：Reli LIMS 中的标准/方法主数据 + WeKnora 知识检索。

快捷入口：
- 检测标准
- 检测方法
- 知识库
- 文档知识化

---

## 3. 二级 Workspace：检测工作台 V2

现有 `Testing Center` 保留，但重新布局。

### 3.1 第一行：状态数字卡

- 待确认委托
- 待收样
- 待试验
- 试验中
- 待报告
- 报告待审核
- 超期 / 异常

### 3.2 第二行：检测主流程

固定业务顺序：

`委托 → 收样 → 方案 → 试验 → 报告 → 审核 → 完成`

每一步显示：
- 当前数量
- 超期数量（如有）
- 点击进入对应过滤列表 / Kanban

### 3.3 第三行：我的工作

按角色差异化：

Lab Engineer：
- 我的待试验
- 我的进行中试验
- 待补结果

Lab Reviewer：
- 待复核结果
- 待审核报告

Lab Manager：
- 全局异常
- 超期
- 资源冲突
- 待分配任务

### 3.4 第四行：常用操作

- 新建检测委托
- 扫码 / 登记收样
- 新建试验方案
- 录入结果
- 生成报告

### 3.5 第五行：业务资料

收进折叠卡片或二级区域：

- 样品
- 项目
- 客户
- 设备
- 标准
- 方法
- 历史报告

这些不是首页视觉中心。

### 3.6 Bridge 状态

检测工作台只显示简版状态：

- Mercur：正常 / 异常
- ERPNext：正常 / 异常
- 网站 / Portal：正常 / 异常
- WeKnora：正常 / 异常

只有管理员看到“查看集成中心”。实验员不显示技术集成配置。

---

## 4. 权限与角色

### Lab Engineer

看到：
- 检测工作台
- 自己负责的试验
- 样品 / 方案 / 结果必要信息

不看到：
- Bridge 配置
- 同步密钥
- 中国税务设置
- 全量客户敏感信息

### Lab Reviewer

看到：
- 检测工作台
- 待审核结果 / 报告

### Lab Manager

看到：
- 检测全局
- 任务分配
- 设备 / 标准 / 方法
- 集成健康状态摘要

### System Manager / Integration Manager

额外看到：
- Bridge 集成中心
- 同步任务
- 错误日志
- 重试
- Webhook / API 配置

### Business / Customer Service

看到：
- 一体化业务工作台
- 客户 / 项目
- 委托进度
- 文档状态

不看到：
- 实验原始数据
- Bridge 密钥
- 审核内部意见

---

## 5. Codex 实施顺序

### Sprint 0 — 只审计，不改业务模型

Codex 必须先读取：

- `AGENTS.md`
- `docs/ARCHITECTURE.md`
- `docs/DATA_MODEL.md`
- `docs/ERPNEXT_INTEGRATION.md`
- `docs/SELLER_WORKBENCH_INTEGRATION.md`
- `docs/V1_CONVERGENCE_PLAN.md`
- 当前 `Testing Center` workspace JSON

输出：
- 当前 Workspace 结构
- 可复用 Number Card / Shortcut / Report / Kanban
- 缺失项
- 本计划与现有模型是否冲突

此阶段不得新增业务 DocType。

### Sprint 1 — 重构 Testing Center

修改现有 `Testing Center`，不要另起检测后台。

完成：
1. 重新布局 Number Cards。
2. 主流程改为委托 → 收样 → 方案 → 试验 → 报告 → 审核 → 完成。
3. 所有数字卡可点击并带真实过滤条件。
4. 增加“我的工作”。
5. 常用操作集中。
6. 基础资料下沉。
7. 保持中文 UI。

验收：
- 无效链接为 0。
- 无不存在 DocType 的入口。
- 每个状态数字与对应列表数量一致。
- Lab Engineer / Reviewer / Manager 看到符合权限的内容。

### Sprint 2 — Bridge 摘要

只做“健康状态与入口”，不在 Reli LIMS 中重写 Bridge。

完成：
- Bridge 状态卡 / 快捷入口。
- Mercur Integration 当前能力接入。
- 同步失败数量。
- 管理员可跳到 Bridge 详细页或对应 App Workspace。

验收：
- 实验员不可看到集成密钥和配置。
- Bridge 故障不阻塞 Testing Center 页面加载。

### Sprint 3 — 创建 Business Hub

前提：Frappe 允许当前 App 提供统一 Workspace；若跨 App Workspace 更适合放在壳 App / Wekona 主 App，则只在本仓输出规范和 fixture，不制造反向依赖。

Business Hub 聚合：
- Reli LIMS 状态
- 文档中心入口 / 状态
- Bridge 状态
- ERPNext Customer / Project
- 中国化模块入口
- WeKnora / 标准知识入口

关键原则：
- 允许链接到其他 App。
- 不允许 Reli LIMS import `wekona_documents` 或 `wekona_china` 的 Python 业务代码形成强耦合。
- 缺少某个可选 App 时，Workspace 应降级隐藏对应入口，而不是安装失败。

### Sprint 4 — UI 收口

目标：看起来像业务系统，不像 DocType 索引页。

要求：
- 标题、说明、分区命名全部中文。
- 首屏只保留状态、流程、待办。
- 卡片标题简短。
- 不使用大量灰色默认快捷块堆叠。
- 统一 icon。
- 使用 Frappe 原生 Workspace / Number Card / Shortcut / Chart / Kanban 能力优先。
- 只有原生能力明显不足时，才增加小型 custom block。
- 禁止为了视觉效果建立独立 SPA。

### Sprint 5 — 测试

新增/更新测试：

- workspace JSON 可加载
- 所有 shortcut 指向存在的 DocType / Page / Report
- Number Card 过滤条件合法
- 中文标题完整
- 角色权限正确
- 可选集成模块缺失时不报错
- Bridge 入口仅授权角色可见

---

## 6. 不做事项

本阶段禁止：

- 重写 Reli LIMS 核心流程
- 新建第二套客户主数据
- 新建独立 React/Next/Vue 管理后台
- 把文档解析代码搬入 Reli LIMS
- 把中国税务逻辑搬入 Reli LIMS
- 在 Workspace 中暴露 API Token / Secret
- 为了卡片数量新增无业务意义的 DocType

---

## 7. V2 完成标准

完成后用户进入系统时，应当可以在 10 秒内回答：

1. 今天有多少委托要处理？
2. 哪些样品还没收？
3. 哪些试验正在进行？
4. 哪些报告等待生成或审核？
5. 我个人今天要做什么？
6. 是否存在同步异常？
7. 客户 / 项目 / 文档 / 中国化 / Bridge 从哪里进入？

若仍需要先理解 DocType 名称才能找到业务入口，则本次 Workspace V2 视为未完成。
