# P4 销售订单与检测委托衔接、实验设备

## 实施边界与基线

业务代码归属 `carlchanchina/reli-lims`。独立 worktree 位于 `/Users/carl/.codex/worktrees/reli-p4-orders-equipment/reli-lims`，分支为 `codex/p4-orders-equipment`。

组合基线为 PR #20 `cde7f48`，其历史已包含 PR #18 `25daf65` 与 PR #19 `9f1f7dc`。P4 PR 以 `feat/customer-collaboration` 为依赖基线，便于单独评审本轮变更。

开发站为 `192.168.10.204`、site `carl`。通过 `tools/dev-site-deploy.sh --ref origin/codex/p4-orders-equipment` 串行部署。运行目录由脚本维护 detached HEAD，开发和提交均在独立 worktree 完成。

## 商业链

询价 → ERPNext Quotation → 授权销售人员记录客户接受凭据 → ERPNext Sales Order → 正式提交 → 自动生成 Test Request 草稿 → 原生免登录 Web Form 补充样品与要求 → 客户确认 → 实验室审核 → Lab Manager 正式受理。

授权人员可直接创建 Sales Order，无需报价。来源报价的订单须先记录客户接受结果。客户接受记录包含客户接受人／凭据说明、时间及登记人审计评论。此操作记录客户接受事实，客户技术确认仍由现有 Web Form 流程执行。

## 字段映射

| 对象 | 字段或原生字段 | 用途 |
|---|---|---|
| Item | `custom_reli_business_type` | 检测服务、普通服务、实物商品 |
| Item | `custom_reli_test_project` | 检测服务技术定义 |
| Quotation | `custom_reli_customer_accepted_by/at` | 受权业务操作登记客户接受凭据 |
| Quotation | `custom_reli_delivery_date` | 客户报价承诺交期 |
| Quotation Item | `custom_reli_business_type` | 每行保存商品类型 |
| Sales Order Item | `prevdoc_docname/quotation_item` | ERPNext 原生来源报价／报价行 |
| Sales Order Item | `custom_reli_business_type` | 每行保存商品类型 |
| Sales Order Item | `custom_reli_test_project/test_object/test_standard` | 检测项目、对象与依据 |
| Sales Order Item | `custom_reli_capability/configuration` | 选择能力及结构化技术快照 |
| Sales Order Item | `custom_reli_split_group` | 留空同一草稿，明确填写组名时拆单 |
| Sales Order Item | `custom_reli_request` | 对应委托，提交后由系统写入 |
| Sales Order | `custom_reli_generation_status/error` | 自动生成状态、错误记录及差异提示 |
| Test Request | `sales_order/quotation` | 原生商业来源关联 |
| Test Request | `order_scope_snapshot/order_difference` | 初始订单范围审计快照及差异提示 |
| Test Request Item | `source_sales_order_item/service_item` | 来源订单行与检测服务商品 |
| Test Request Item | `source_quotation/source_quotation_item` | 来源报价及原生报价行 |
| Test Request Item | `requested_quantity` | 服务数量，参与客户确认指纹 |
| Test Request Item | 现有项目／对象／依据／能力／技术快照 | 从订单原值传入 |
| Asset | `asset_name/location` | 复用设备中文名与原生 Location |
| Asset | `custom_reli_laboratory/model/serial_no` | 实验室、型号、设备序列号 |
| Asset | `custom_reli_parameters` | 技术参数与工作范围 |
| Asset | `custom_reli_equipment_status/calibration_until` | 启用、停用、维护与有效期 |
| Asset | `custom_reli_scopes` | 项目与适用能力的子表关系 |
| Test Program Item | 原生 `asset/workstation` | 实际使用的自用设备与工位 |
| Test Program Item | `equipment_snapshot` | 开始试验时的名称、型号、序列号、实验室、位置、状态、校准有效期及时间 |

## 迁移与兼容

现有明确关联 Test Project 的非库存销售 Item 自动标记为检测服务。其他旧 Item 保持空分类，保存商业行时根据主数据明确分类。非库存且无检测项目的旧商品作为普通服务处理。仅非库存属性不会触发检测委托。

在能力选择器中明确选择既有未归类服务商品时，要求 Item 写权限并补齐检测项目与检测服务分类。已明确分类为普通服务或实物商品的 Item 会拒绝用于能力报价。

Test Request 的样品表、样品分配表及行依据不再依赖无条件 Meta 必填来阻止草稿。普通委托仍由现有 `validate_scope` 完整校验。仅有可追溯销售订单来源的草稿允许待补充，正式受理一律校验完整范围、当前客户确认、实验室审核及有效技术主数据。

现有 Asset／Workstation 引用保留。已配置实验室资质的设备在已就绪或开始试验时检查状态和校准有效期，开始后快照冻结。历史未配置实验室资质的 Asset 保持原执行行为，并记录可取得的设备事实。维护设备资料沿用 ERPNext 原有权限。

## 事务与差异处理

Sales Order 提交后的生成过程使用数据库 savepoint。全部拆分组成功后才保留生成结果。异常时回滚本次生成的全部委托与行关联，在订单保存失败状态并关联 Error Log。订单提交事实保留，订单页提供“重试生成检测委托”。

重试锁定原生订单行，校验既有委托覆盖的全部订单行及初始范围。正常重试返回同一委托。委托来源行不可在多个委托重复。订单修订如已有原委托则要求人工处理，防止双重履约。

取消有关联委托的订单会被明确阻止。已提交订单修改、Delivery Note／Sales Invoice 退货或取消，以及每日对账都会检查原始范围差异。订单页刷新也实时计算差异。检测委托原始范围、已确认技术及执行数据保持审计快照，差异须由授权人员处理商业变更和重新确认。

## 客户打印

应用“生成文档”与原生 `Reli Customer Quotation` 都只投影客户商业字段、中文商品／服务名、必要技术条件、数量与价格。已配置技术快照的检测行根据快照白名单生成公开描述。能力 ID、来源文件、供应信息与实验室成本不进入该投影。旧无快照报价保留原客户描述。

原生 Quotation 默认打印格式设置为 `Reli Customer Quotation`。内部 Quotation Item 快照和能力关联字段设置 `print_hide`。源数据与 ERPNext DocType、Item 主键保持兼容。

## 入口与权限

商业接单中心提供原生销售订单入口，“生成委托”指向订单列表。报价表单“创建销售订单”复用 ERPNext 原生 mapper。

实验室能力中心和原生侧栏增加“实验设备”，打开 ERPNext Asset。Test Project 提供“可用实验设备”，支持中文名称、型号、序列号搜索和分页。Asset 子表中项目与能力可跳转，实际设备在 Test Program Item 中选择，试验记录沿用该行。

重试与客户接受操作要求原生销售单据写权限。设备维护和查看遵循 Asset 权限。自动生成的内部权限放开仅限已提交且锁定的订单及其检测服务行。
