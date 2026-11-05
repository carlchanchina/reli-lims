# P1.6.1 旧字典收口与双向业务关联验收

验收日期：2026-11-05。环境仅为 Carl 开发站 `192.168.10.204`、site `carl`、`dev-bench`。未访问、未部署 Carl-1。延续 PR #19，保持 Draft；未合并。

## 根因与修复

1. `Item.custom_reli_detection_project` 仍是 `options=Detection Project` 的真实 Link 自定义字段。即使隐藏和只读，Frappe 加载表单时仍解析目标 Meta，因目标 DocType 已退休而报错。清理 Patch 先验证旧 Item/能力关联已对应到正式项目，再删除无效字段及数据库列；没有通过隐藏字段规避错误。
2. `Laboratory Capability.detection_project` 残留为数据库孤列，已移除。历史 `tabDetection Project` 的 124 行审计数据保留，正式业务主数据仍为现有 `Test Project`。
3. 关系面板的全局资源 Hook 使用了错误的 `public/js/...` URL；修正后又发现旧脚本调用 Desk 中不存在的 `frappe.ready`，导致关系渲染器未注册。改用 Frappe 哈希资源 `business_relations.bundle.js`，移除该调用，构建后的最终资源为 `business_relations.bundle.OVXBRK45.js`。
4. “选项”来自安装的 Suite 应用 `suite/locale/zh.po` 对 `Item` / `Items` 的翻译。Reli LIMS 增加中文翻译并在 Desk 初始化时覆盖同源标签，处理库存/销售侧栏的链接及商品分组；不改 ERPNext 核心 DocType 名称、Item 编码或 Suite 源码。

## 实际字段前后对比

| 对象/字段 | 修复前 | 修复后 |
| --- | --- | --- |
| `Item.custom_reli_detection_project` | Link → 不存在的 `Detection Project`，隐藏、只读仍报错 | Custom Field、Meta 及数据库列均不存在 |
| `Item.custom_reli_test_project` | Link → `Test Project`，业务关联已迁移 | 保留，显示项目中文名称，关联面板可点击进入项目 |
| `Item.custom_reli_test_method` | Link → `Test Method` | 保留，标签为“原检测项目（兼容）” |
| `Item.custom_reli_service_capability` | Link → `Laboratory Capability` | 保留，只读来源，不丢失能力 ID |
| `Item.custom_reli_business_relations` | 无 | HTML，只读查询项目及对象、依据、能力、商品数量 |
| `Laboratory Capability.detection_project` | 旧数据库孤列 | 删除，正式 `test_project` 保留 |
| `Test Object.relations_html` | 缺少完整反向浏览 | 实时查询项目、依据、能力、实验室及商品；中文搜索、三维筛选、分页和跳转 |
| `Test Project.relations_html` | 缺少完整能力/商品浏览 | 能力和服务商品列表；原对象和依据子表保留原生 Link |
| `Test Standard.relations_html` | 缺少反向项目浏览 | 项目、能力、实验室及服务商品反向浏览 |
| `tabDetection Project` | 124 行历史记录 | 仍为 124 行；无业务 DocType、业务入口或可编辑 Link |

关联来自 `Test Project Object`、`Test Project Standard`、`Laboratory Capability` 和 Item 的正式项目 Link；不复制关联数据，不增加字典模型。`Test Method` 仍有兼容履约引用，继续保留。

## 旧引用清理与扫描

清理器 `p161_legacy_dictionary_cleanup` 检查旧 Item/能力指向的历史项目是否已经映射，未映射则中止；删除指向旧 DocType 的 Custom Field、Property Setter、Workspace Link/Shortcut，移除已验证的两个旧数据库列。增加 `after_migrate` 收口入口，让已记录过中间版本 Patch 的站点也能完成清理。

最终 Carl 扫描 `Detection Project` / `detection_project`：DocField、Custom Field、Property Setter、Workspace 内容及链接、Workspace Link、Workspace Shortcut、Client Script、Server Script、Report、Print Format、Notification、List Filter 均为 **0 条残留引用**。仓库运行时 JSON/JS 不再引用旧字典；历史名称仅留在迁移、回归断言和审计文档中。

历史单据检查：Quotation Item 共 6 行，其中 2 行有可映射能力；Test Request Item 共 7 行，其中 2 行有可映射能力/方法；Test Program Item 共 5 行，无可映射到正式项目的旧方法记录。这三类中，可映射但缺少正式项目的行数和无效正式项目 Link 均为 0。没有将无正式映射的兼容履约记录删除或强行改写。

## 数据保全

| 数据 | 验收结果 |
| --- | ---: |
| Test Project | 118（已归类 118，待分类 0） |
| Test Object | 42 |
| Test Standard | 214 |
| Laboratory Capability | 652（650 条 CNAS + 2 条既有演示） |
| Test Method | 126，保留兼容 |
| Test Project Object | 396 |
| Test Project Standard | 638 |
| 已关联项目的非库存 Item | 5 |
| 历史 Detection Project 表 | 124 |

CNAS 来源 `CAPSRC-00499` 仍关联 650 条能力；项目、对象、标准、来源行缺失数均为 0。原始结构化 JSON 为 833,923 字节，SHA-256 仍为 `fa716f04c0fc867f7a37d6c0716face1cc5195eb6e5c776c760c2af797531fd7`，与 P1.6 验收一致。未重解析、未重复导入。

## Carl Desk 实际验收

| 验收项 | 实际结果与证据 |
| --- | --- |
| 原报错商品打开、修改、保存 | `RELI-SVC-73ECD62B773BB0A5` 成功。Desk 将名称临时改为“疲劳载荷试验（开发站保存验收）”保存，再恢复“疲劳载荷试验”保存；两条 Version 审计记录保留。[截图](p16-1/01-item-saved.png) |
| 五个关联项目的商品均可打开 | 疲劳载荷试验、玻璃粘接强度试验、随机振动试验、低温试验、静强度试验均实际打开；关联面板加载完成后无旧 DocType 报错或“选项”。[截图目录](p16-1/) |
| 商品保存兼容 | 五个现有商品均通过原生 `doc.save()` 验证；验收事务回滚。原报错商品另有上述真实 Desk 保存 |
| 项目 ↔ 商品 | 从商品“疲劳载荷试验”按钮到 `TPR-01391`，再从项目商品列表回原生 Item，双向实际点击成功。[项目关系](p16-1/02-project-relations.png) |
| 项目 ↔ 对象 | 项目原生对象 Link 到 `OBJ-01426 车辆部件`，对象项目列表返回 `TPR-01391` 成功。[对象项目](p16-1/03-object-projects.png) |
| 对象筛选 | 中文搜索“疲劳”仅剩匹配项目；项目=疲劳载荷、依据=UIC 566:1990、实验室=苏州旭博，能力收敛为 `CAP-00501`。[筛选截图](p16-1/04-object-filtered-capability.png) |
| 项目 ↔ 能力 | 项目/对象能力按钮进入 `CAP-00501`；能力原生项目 Link 返回 `TPR-01391`，成功。[能力来源](p16-1/05-capability-source.png) |
| 项目 ↔ 依据 | 项目 UIC 566 按钮进入 `STD-00491`；依据反向项目列表回 `TPR-01391` 成功。对象依据页签也可进入同一依据。[依据反向列表](p16-1/06-standard-reverse.png) |
| 实验室跳转 | 关系列表实验室名称可进入 `sel_dev_cnas_L11464`，详情显示 650 条能力、118 个项目及 5 个服务商品。[实验室](p16-1/11-laboratory.png) |
| 分页 | `OBJ-01406 机车车辆用电力变流器` 共 70 条能力，点击下一页后为第 2/7 页。[分页截图](p16-1/07-object-page-two.png) |
| 既有报价 | `SAL-QTN-2026-00005` 正常打开；两行中文项目、依据、实验室与条件快照保留，疲劳载荷保持时间仍为 15 分钟。[报价](p16-1/08-quotation.png) |
| 既有委托 | `REQ-01150` 正常打开，技术页两行中文项目、对象、依据及样品关联保留。[委托](p16-1/10-request-technical-details.png) |
| 报价/委托编辑兼容 | 两份既有草稿均通过原生 `doc.save()`；未放宽确认或提交校验，事务回滚，不提交单据 |
| 旧字典业务入口 | 最终 Meta 和脚本扫描为 0；截图侧栏不再出现 Detection Project；Test Method 兼容入口保留 |
| 中文显示 | Item 标题以中文商品名为主，编码作为侧栏辅助；库存与销售侧栏、面包屑均使用“服务商品”，报价最终截图无“选项” |

## 回归及迁移

- Carl 全量回归：**59 项集成测试 + 1 项独立测试全部通过**；9 项业务关系测试包含旧 Link 清除、服务商品保存、反向查询、资源 Hook 和重复清理。
- 测试代码版本 `8bc4929`；最终 `e22d219` 仅补齐原生侧栏中文选择器及移除已替换旧 JS，`node --check` 通过并在 Desk 验证。
- 最终 Carl 构建成功；最终版本连续两次 `migrate` 成功，含 `after_migrate` 清理。之后再次核对上述业务数量和 CNAS 来源哈希不变。
- [完整回归日志](p16-1/regression.log)。测试开关已恢复为关闭。浏览器仍有开发站既有 socket.io 连接错误，不影响本轮表单加载、关联查询和保存；无关系脚本异常。

代码提交：`23e44a6`、`a0e8f8f`、`fb7dca4`、`ed2a463`、`f7b98cb`、`aa9f73b`、`8bc4929`、`e22d219`。本报告和截图随其后的文档提交交付。
