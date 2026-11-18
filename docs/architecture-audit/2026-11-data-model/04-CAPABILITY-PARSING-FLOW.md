# 04 · 能力表解析与归并流程

## 4.1 现有链路（代码可证的部分）

```
[门户上传] apps/web/src/routes/api/testing/upload.ts
      │  (Bridge: portal_runtime.dispatch  action = capability.source.upload | capability.source.get)
      ▼
[Frappe] Capability Upload  ← 幂等壳：request_key / content_hash / dedupe_key / previous_request / reused_request / revision
      │  解析：cnas-workbench（独立解析服务，返回 parser_version、status=parsed|needs_ocr）
      ▼
[Frappe] Capability Source   ← structured_json(必填) + source_type + documents_source_id(幂等) + documents_review_status + import_status
      │  capability_api.import_capability_source(source_name)
      ▼
[Frappe] Laboratory Capability 逐行落库（cnas_scope_key = sha256(laboratory+item_code+standard_no+test_object+clause+limit_note+effective_date)）
      │  patches/p16_test_project_dictionary.py 按归并键归入 Test Project
      ▼
[Frappe] Test Project (normalized_name + aliases) ← 人工归类/审核
      │  capability_review.review / publish
      ▼
[已发布能力]  → capability_api.get_bridge_eligibility → Bridge 校验
      │
      ▼
[商业] capability_quotation.service_item() → Item → Quotation Item（含 config 快照）
```

## 4.2 解析服务的边界（证据半充分）

- ntbln 侧只声明"描述解析服务返回的结构，不新增业务对象"（`apps/web/src/lib/testing/testing-model.ts:4`），并带 `parser_version`、`mineru_enabled` 字段（同文件 228-231）。
- Frappe 侧拿到的是**已结构化的 JSON**（`Capability Source.structured_json` 必填），导入函数不解析 PDF/Excel 本身。
- **本报告未审计 cnas-workbench 仓库源码**，故"PDF/Excel 如何切行、OCR 兜底、条款识别算法"属于证据不足，仅能确认接口契约（`status: parsed|needs_ocr`、`parserDocument(s)`）。

## 4.3 600 条能力如何归并（现有机制的真实行为）

归并发生在三个层次：

1. **行级去重**：`cnas_scope_key` 对（实验室, 产品/项目代码, 标准号, 检测对象, 条款, 限制, 生效日期）做哈希，重复行不重复插入。
2. **字典归并**：`Test Project.normalized_name = project_key(project_name)`；`test_project.py:43` 生成键，`51-69` 检查同名与别名冲突并 throw；`aliases` 容纳"高温试验/高温测试"这类同义写法的**人工声明**。
3. **字典补丁**：`patches/p16_test_project_dictionary.py` 按 `normalized_name` 批量把能力挂到项目（`p16_test_project_dictionary.py:254` 用 `{"normalized_name": project_key(project_name)}` 查已有项目）。

开发站实测：660 条能力 → 120 个项目，单项目最多 55 条能力、51 条标准、30 个对象；44 个对象、216 个标准作为共享字典。**这说明归并本身是成立的，代价是"项目 = 名称族"的语义，而不是"项目 = 可售规格"。**

## 4.4 归并不会丢掉什么、会丢掉什么

**不会丢**（保留在 `Laboratory Capability` 行上）：原始产品范围 `product_scope`、条款 `clause`、限制 `limitation`、生效日期、来源行号 `source_row`、来源批次 `source`、认可类型与证书号、`condition_schema`。

**会丢/会糊**：
1. **实验室维度**：项目子表 `Test Project Standard/Object` 没有 laboratory 字段。两家实验室共用一个项目时，子表变成两家并集——"A 实验室只做其中 3 个对象"这个事实在项目层消失。
2. **同义但未登记别名**：`project_key` 只做字符串归一（去空格/大小写/标点），"高温试验"与"高温环境试验"若未进 `aliases`，会分裂成两个项目 → 两个商品 → 报价体系分裂。
3. **一个商品只能记一条来源能力**：`Item.custom_reli_service_capability` 是单值且 read_only，第一次生成时写入，多能力合并后无法回溯全部来源。

## 4.5 发布与对外的闸门

- 单条/批量：`capability_review.publish(names, note, include_demo)`；演示能力需 `include_demo` 才可发布（`is_dev_preview` 在报价中被绕过的情形，`capability_quotation.py:118`）。
- 对外读取：`capability_api.get_bridge_eligibility(capability_ids)` 按角色切到 `mercur_capability_reader_user` 执行，返回资格快照。
- 走向市场：`mercur_erpnext_bridge.capability_publication.publish(command)`，必须先有 `mercur_capability_publication_bindings` 中的审批绑定（含 `scope_snapshot`、`pricing_mode`、`approval_reference`），否则 422。
- 商城侧：`my-marketplace/packages/api/src/lib/capability-publication.ts` 与 `workflows/erp-item-publication.ts` 承接；目录入口 `ingest_signed_catalog`（签名目录）。

## 4.6 结论（对"600 条能否合理归并"的直接回答）

**能归并，且不丢原始条款——但"合理"依赖三件人工事**：① 每个同义写法必须进 `aliases`；② 多实验室必须各自维护能力行，不能只维护项目子表；③ 商品与能力的映射必须显式化（现在靠懒创建 + 单值溯源）。缺这三件，660 条会变成 120 个"看起来统一、实际口径不一"的项目。
