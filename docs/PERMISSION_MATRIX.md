# RELI LIMS 权限矩阵与最小授权说明

适用范围：Carl 开发站 `carl`，提交 `a20d800`。角色均为本应用自定义角色，除特别说明外不修改 ERPNext 原生角色。

## 1. 能力相关（本次变更重点）

| 角色 | 检测能力 | 审核通过/退回 | 发布/停用 | 项目 / 标准 / 方法 |
| --- | --- | --- | --- | --- |
| Lab Engineer | 只读，且按所属实验室限域 | 否 | 否 | 只读 |
| Lab Reviewer | 读写（可补充审核意见） | 是 | 否 | 只读 |
| Lab Manager | 读写/新建 | 是 | 是 | 读写/新建 |
| Sales User / Sales Manager | 只读（用于能力报价） | 否 | 否 | 项目/标准只读 |
| System Manager | 全部 | 是 | 是 | 全部 |

- 「按所属实验室限域」用 Frappe 原生 User Permission 实现：给工程师建一条
  `allow=Laboratory Profile`（`applicable_for=Laboratory Capability`）即可；
  没配 User Permission 时按原生规则看到全部，配了就只看该实验室。
  实测：工程师在 `sel_dev_cnas_L11464` 下可读 651 条，读取另一实验室 `CAP-00077` 被拒。
- 审核/发布在服务端二次校验角色（`reli_lims/capability_review.py`），不依赖前端隐藏按钮；
  工程师调用 `review/publish` 均抛 `PermissionError`（验收脚本已断言）。

## 2. 委托与执行

| 角色 | 委托单 | 样品 | 试验方案 | 试验报告 | 付款/报告客户 |
| --- | --- | --- | --- | --- | --- |
| Lab Manager | 增删改提审 | 增删改 | 增删改 | 增删改 | 仅存在性校验 |
| Lab Engineer | 增/改（不能提交） | 增/改 | 增/改 | 增/改 | 同上 |
| Lab Reviewer | 只读 | 只读 | 增/改 | 增/改 | 同上 |

## 3. 商业单据（为什么不给 Sales User）

ERPNext 的 `Sales User` 覆盖 **60 个单据**（报价、销售订单、客户、商品、库存预留……），
给实验室内勤会造成明显的越权。但 Frappe 的「自定义权限」是**整体覆盖**而非追加：
一旦为某个 DocType 写入 `Custom DocPerm`，该单据的原生权限集会被完全替换
（实测：给 `Quotation` 加一条自定义只读后，`get_valid_perms` 只剩测试角色）。
因此这里不采用「加一条只读」的常规做法，改为代码级有界投影：

| 需求 | 实现 | 暴露字段 |
| --- | --- | --- |
| 委托选择客户 | `commercial_access.customer_query` | 编号、客户名称 |
| 委托选择报价 | `commercial_access.quotation_query` | 编号、日期、客户 |
| 委托选择销售订单 | `commercial_access.sales_order_query` | 编号、日期、客户 |
| 报价来源校验 | `quotation_facts` / `sales_order_facts` | 状态、客户、公司 |
| 报价行转委托行 | `quotation_detail` / `quotation_line` | 行号、数量、能力、技术快照 |

不返回价格、税额、折扣、其它客户单据。调用方必须持实验室角色，且报价/订单必须
属于所选客户与公司、状态为已提交。

`Test Request.validate` 的客户/公司校验从「需要 Customer 读权限」改为「必须真实存在」，
因为实验室角色本来就没有 Customer 的 DocPerm，而客户名称已经写在委托单上。

## 4. 系统副作用

| 动作 | 位置 | 授权方式 |
| --- | --- | --- |
| 受理时创建履约 `Project` | `services/test_request.py:create_project` | 先校验 `Lab Manager/System Manager` 角色 + 委托可读，再以 `ignore_permissions` 内部创建（项目不是操作人在编辑的业务单据） |
| 履约时读取 `Project` | `services/test_request.py:_confirmed_request` | 只校验项目存在性；项目读写由 `Projects User` 提供 |

因此：**正式受理不需要 `Sales User`**；`Projects User` 是履约项目读写的必要角色
（ERPNext 没有只读项目角色，`Projects User` 只覆盖 17 个单据）。

## 5. 授权口径

- 新增角色的岗位组合：内勤/负责人 `Lab Manager + Projects User`；
  工程师 `Lab Engineer + Projects User`；商务 `Sales User`（另加能力只读）。
- 不再给实验室角色叠加 `Sales User`：验收脚本会断言 `demo-lab-manager@example.com`
  与 `demo-lab-engineer@example.com` 的角色集合里没有 `Sales User`。
- 任何新增 DocPerm 都必须先确认不会整体覆盖原生权限；确需覆盖时，先复制现有
  `DocPerm` 全部行再追加，并在 PR 说明中列出被覆盖的角色。
