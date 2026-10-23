# Reli LIMS：商家工作台业务服务实施清单

> 更新：2026-10-23。状态：待实施的跨仓库计划，不代表接口已经实现、主分支已合并或生产已经上线。本轮只更新文档。保留现有身份体系、数据库和解析服务，不新增商家登录入口，不修改上游核心。

## 总约定与现有模型

遵循 Bridge 的 `docs/SELLER_WORKBENCH_INTEGRATION.md` 补充契约及原 ReliLab 架构。保留 `docs/V1_CONVERGENCE_PLAN.md` 的收口主线，不另建实验室 SPA。

当前仓库可见 Test Request、Sample、Test Program、Test Report、Test Standard、Laboratory Profile 与 laboratory_api；不再新造同名委托体系。Test Request 确认与生成 Project 的行为先核对现有 controller 和测试，复用唯一创建路径，不由订单同步另建第二个 Project。

## 实施任务

- [ ] 核对现有确认/收样/方案/审核/签发服务和权限；确认 V1 收口验收状态，再增加门户需要的受控 API。
- [ ] 明确订单 scope、seller、buyer organization、执行实验室、ERP company、委托/Project 映射；seller 不直接等于 ERP Company。
- [ ] 委托草稿记录订单来源；确认前校验样品需求、项目、标准、客户同意等必填内容，确认后一次生成/关联 Project。订单到达不伪造实收 Sample，不创建无有效样品和项目的 Test Program。
- [ ] 提供最小业务能力：委托草稿/确认/变更申请、收样、允许的进度动作、履约摘要、已签发报告引用。路径待核实；禁止通用任意 DocType CRUD 成为商家接口。
- [ ] 每个入口验证可信上下文及资源归属，不能只检查调用者有 integration role；所有查询和私有 File 都需组织范围校验。
- [ ] 负责人、工程师、审核、签发权限分离；跨角色授权显式配置。商家负责人不能自行获得实验室专业资格。
- [ ] Documents 提取候选映射到现有 Test Standard/Test Method/Laboratory Profile，先检查现有能力字段；仅在确有缺口时扩展能力关系，保留条款、范围、限制、证据和版本。文档批准不自动证明资质。
- [ ] 复用 Test Program → Item → Result → Reviewed → Report 的执行规则。商家 UI 显示中文业务阶段，内部状态不由客户端随意赋值。
- [ ] 已确认委托修改生成变更记录/版本，影响费用和工期交还交易确认流程；报告修订保留历史，草稿不能公开下载。
- [ ] 输出已发布公共能力投影和私有履约摘要，两者严格分离；Report 和委托不得进入公开 Wiki。

## 验收

- [ ] 并发确认与重放只产生一个对应 Project，目标失败后可恢复。
- [ ] 跨商家、跨客户、跨执行实验室访问被拒绝；文件访问同样隔离。
- [ ] 未实收样不冒充已收样；未审核试验不得签发；无签发角色不得发布报告。
- [ ] 现有多样品/多项目流程和 Frappe Desk 主流程不回归。

本轮仅计划；委托具体签字/客户确认法律流程与已有数据字段在 G0 核实，不假定按钮等于已完成客户确认。

## 第一切片实施记录（2026-10-23）

已实现只读订单履约与管理员明确关联；开发机真实验收十次重放、只读权限及跨商家拒绝通过。自动生成委托、确认及报告下载仍待后续切片。操作与配置见 Bridge 仓库 `docs/SELLER_WORKBENCH_RUNBOOK.md`。商城/ERP 正式部署和商家启用状态以发布记录为准。

### 委托草稿前置修复
真实受限账号验收发现 Test Request.company 的 `default: :Company` 会读取不存在的 Company.company 列。移除该元数据默认值，沿用控制器已有的显式 company / 用户默认 / 全局默认 / 唯一可见公司选择。此修复不改变公司权限，也不新增业务单据。部署需 reload_doc Test Request 并清理元数据缓存。
