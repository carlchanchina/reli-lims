# 审计证据表

约定：`文件:行号` 取自**开发站 main 代码**（`dev-bench`，`reli-lims@35c15e6`、`mercur_erpnext_bridge@b94d326`、`ntbln@8e02484`、`my-marketplace@ebd66ba` 的 `origin/main` 归档副本）。无法定位到行号的结论只写函数名，并标注"证据等级"。

## E1 · 版本与部署

| 结论 | 证据 |
|---|---|
| 四仓本地均落后 origin/main | `git rev-list --left-right --count origin/main...HEAD`：reli-lims 56/0、ntbln 69/0、mercur_erpnext 25/0、my-marketplace 57/5 |
| 生产 reli_lims = 35c15e6 | 生产 `apps/reli_lims` `git log -1` = `35c15e6`（main，origin/main） |
| 生产 mercur 目录无 .git | `apps/mercur_erpnext_bridge` 无 `.git` 目录（开发站有，`b94d326`） |
| wekona_china 无自有 DocType | 遍历 `wekona_china/wekona_china/doctype` 无输出 |

## E2 · 数据模型（27 个 DocType）

| 结论 | 证据 |
|---|---|
| reli_lims 共 27 个 DocType 定义 | 遍历 `reli_lims/reli_lims/doctype/*/*.json`，`grep -c '^## '` = 27（不含 ERPNext 原生） |
| `Test Project` 只有标准/对象两个子表，无商品字段 | `test_project.json` 字段表：`standards`(Table→Test Project Standard)、`objects`(Table→Test Project Object)、`relations_html`(HTML) |
| `Test Project Standard/Object` 无 laboratory 字段 | 两个 child doctype 的字段定义仅 parent+`test_standard`/`basis_type`、`test_object`/`category` |
| `Item` 的检测字段 | `capability_catalog.ensure_custom_fields()`：`custom_reli_test_method`（原检测项目（兼容））、`custom_reli_service_capability`（能力目录生成来源，read_only）、`custom_reli_test_project`（检测项目）、`custom_reli_business_relations`（HTML） |
| `Test Method` 自带 project/standard/asset | `test_method.json`：`test_project`、`default_standard`、`default_workstation`、`default_asset`、`default_condition` |
| 能力事实字段 | `laboratory_capability.json`：`test_project`/`test_object`/`test_standard`/`capability_scope`(reqd)/`product_scope`/`limitation`/`clause`/`scope_effective_date`/`condition_schema`/`cnas_scope_key`/`merchant_offer_id`/`wiki_page_id` |
| 商品与项目无中间表 | 全仓 `grep -rni "service offering\|service specification"` → 0 命中 |

## E3 · 能力归并与解析

| 结论 | 证据 |
|---|---|
| 归并键定义 | `reli_lims/reli_lims/doctype/test_project/test_project.py:43` `self.normalized_name = project_key(self.project_name)`；`:51-69` 别名/同名冲突 throw |
| 批量归并补丁 | `reli_lims/patches/p16_test_project_dictionary.py:56-57` 取项目 `normalized_name`；`:254` 按 `project_key(project_name)` 查项目 |
| 导入幂等键 | `reli_lims/cnas_dev_import.py` `_apply()`：`documents_source_id=f"L11464:{digest}"`、`cnas_scope_key=sha256(identity)`、`Test Standard` 按 `standard_code+version` 唯一、重复 throw |
| 导入入口 | `reli_lims/capability_api.py:27` `import_capability_source(source_name)` |
| 上传壳 | `capability Upload` 字段：`request_key`/`content_hash`/`dedupe_key`/`previous_request`/`reused_request`/`revision`/`parser_version` |
| 解析在外部服务 | `ntbln/apps/web/src/lib/testing/testing-model.ts:4`（"只描述解析服务（cnas-workbench）返回的结构，不新增业务对象"）；`:228-231` `parser_version` / `mineru_enabled` |
| 660→120 的实际数据 | 开发站 SQL：`Laboratory Capability` 660、`Test Project` 120（`classification_status=已归类` 120）、单项目最多 55 能力/51 标准/30 对象 |
| 商品实况 | 开发站：`custom_reli_business_type=检测服务` 的 Item 9 条，全部 1:1 对应不同项目，`having count>1` 为空 |

## E4 · 报价与价格

| 结论 | 证据 |
|---|---|
| 商品懒创建 | `reli_lims/capability_quotation.py:14-59` `service_item()`：`:22-27` 按项目查已有 Item；`:29` `RELI-SVC-<sha256(project)[:16]>`；`:50-51` 项目不一致 throw |
| 报价行生成 | 同文件 `:62-82` `prepare_lines()`（1-30 条，`build_configuration` + `service_item` + 行字段） |
| 快照构建 | `reli_lims/capability_selection.py` `build_configuration()`：返回 `{schema_version, capability_id, conditions, snapshot}`，`snapshot` 由 `FIELDS` + `labels()` + `source/source_row/condition_schema` 组成 |
| 条件校验 | 同函数：未知键、number 有限性、select 选项、text ≤2000、必填 |
| 三列被 live 覆写 | `capability_quotation.py:111-115`（`row.custom_reli_test_project/test_object/test_standard` 从 `capability` 现值重写） |
| 价格不参与计算 | 同文件 `:120-124`：仅校验已发布 + `rate >= 0`；全仓无价格计算函数 |
| 描述由条件拼装 | 同文件 `:85-91` `description(config)` |
| 可履约行筛选 | `reli_lims/quotation_origin.py:183-209` `is_testing_line` / `fulfillable_lines`（要求 `custom_reli_business_type=检测服务` 且 capability、configuration 非空） |
| 容量互斥 | `quotation_origin.py:255-307` `lock_quotation_lines` / `validate_order_capacity` / `validate_line_capacity` → `CAPACITY_CONFLICT` |
| 委托预填 | `reli_lims/capability_request.py:27` `prepare_items(selections)`、`:39` `quotation_items`、`:159` `execution_items` |
| 订单→委托 | `reli_lims/sales_order_testing.py:272` `prepare_lines`、`:348` `accept_quotation` |
| 方案生成 | `reli_lims/services/test_request.py:85` `make_test_program` |

## E5 · 中心与页面

| 结论 | 证据 |
|---|---|
| 四个工作区 | `reli_lims/reli_lims/workspace/{testing_center,testing_fulfillment_center,laboratory_capability_center,commercial_intake_center}/*.json` 的 `title` 与 `links` |
| 能力中心"服务商品"指向裸 Item | `laboratory_capability_center.json` → `{"label": "服务商品", "link_to": "Item"}` |
| 能力中心页面动作 | `reli_lims/page/reli_capability_hub/reli_capability_hub.js:43,45-46`（实验室管理、服务商品关联 route_options `is_stock_item=0, is_sales_item=1`） |
| 角色 fixture | `reli_lims/hooks.py:10-12` |
| 事件挂载 | `reli_lims/hooks.py:31-35`（progress）、`:45-47`（File）、`:54-58`（Quotation/Test Request/Item 的 js 与 validate） |

## E6 · 门户与 Bridge

| 结论 | 证据 |
|---|---|
| 门户动作白名单 | `mercur_erpnext_bridge/portal_runtime.py:215-300`（`me`、`capability.source.upload|get`、`command.get`、`commerce.inquiry.create`、`quotation.sales-order.create`、`capability.publication.check`、`test-report.list|pdf`、`test-request.progress|get|save|confirm|file.upload|file.get`、`quotation.test-request.create`、`quotation.list|get|pdf|accept`、`inquiry.quotation.request|create`、`inquiry.create|get`、`suite.provision|membership.sync`、`cabinet.*`、`buyer.provision|exceptions`、`party.candidates|link|unlink`、`onboarding*`） |
| 能力发布闸门 | `mercur_erpnext_bridge/capability_publication.py:20-40`：绑定字段集校验，缺项 `COMMERCIAL_APPROVAL_REQUIRED` 422 |
| 资格校验走独立用户 | 同文件 `_eligibility()`：`frappe.conf["mercur_capability_reader_user"]`，禁 Guest/Administrator |
| 商品发布 | `mercur_erpnext_bridge/item_publication.py:109` `publish_item`、`:188` `get_published_service` |
| 商城对接 ERP | `my-marketplace/packages/api/src/lib/erp-catalog.ts:52` → `mercur_erpnext_bridge.api.ingest_signed_catalog`；`lib/reli-lims-laboratory.ts:67` → `mercur_erpnext_bridge.laboratory.{method}` |
| 门户商业调用 | `ntbln/apps/web/src/lib/{commerce/commerce.server.ts, portal/portal.service.server.ts, portal/quotation-bridge.server.ts, suite/suite-bridge.server.ts, organization-verification/party-bridge.server.ts, buyer-provisioning/inquiry-bridge.server.ts}` 等 10 处 |
| 商城框架 | `my-marketplace/packages/api/package.json` 依赖 `@medusajs/framework`、`@mercurjs/core`、`@mercurjs/types`；`docker-compose.yml` 服务 postgres/redis/api |

## E7 · 证据不足项（不改写为事实）

1. **cnas-workbench 解析算法**：仓库不在本次四仓范围内，PDF/Excel 切行、OCR 触发、条款抽取的实现无法核实，只能依据 ntbln 类型定义与 `status: parsed|needs_ocr` 契约。
2. **Quotation → Sales Order 的原生映射细节**：来自 ERPNext 原生行为，未在 reli_lims 代码中实现，具体字段映射未逐项核对。
3. **生产数据分布**：本报告用生产数据只做"演示数据存在"这类事实陈述（7 个 CRM Organization 均未映射），所有模型判断以代码与开发站数据为准。
4. **`merchant_offer_id` / `wiki_page_id` 的写入方**：能力表里有字段，但未在本次检索中找到明确写入代码路径（可能由 Bridge 或外部系统写）。
