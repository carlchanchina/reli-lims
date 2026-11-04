# P1.5 CNAS 数据契约、迁移前审计和 P2 接口

## 已恢复成果与现场基线

| 所有者 | 实测或恢复的成果 |
|---|---|
| CNAS Workbench | Mac mini `~/WorkBuddy/2026-11-04-19-09-32/cnas-workbench`，干净的 `7b274efedb94e6d6250db29423b0b4376ce9609a`。L11464 的 Git 跟踪 CSV 位于 `app/labs/L11464/out_v2/`；另有 `out/`、`source/CNAS认可的检测能力范围.md`、`app/method_codes.csv`、`seed/cnas.db`。保留 `pipeline/wstd.py`、`parse_standards.py` 和 `app/validate_scope.py` 的分工与结果。 |
| Reli LIMS | 本地 `main` 为 `4f5d38e`。旧分支 `codex/laboratory-capability-center` tip `461a9f4` 有两个 DocType、中文工作区、`capability_api.py`、demo seed 与集成测试。旧导入以来源和行号去重，按裸标准号查首条、要求已有方法，缺预览及异常台账。选择性复用，不合并整条旧分支。现有 PR #18 单值 Item 字段仅兼容旧读路径。 |
| Documents | Mac mini `~/projects/wekona_documents`，`06e4e82`。复用 `services/cloud_standard.py`、`standard_aggregation.py`、`services/mapping.py` 和 `worker/standard_chunks.py` 的标准解析、版本及 Draft 映射能力；测试见 `tests/test_cloud_standard.py`、`test_standard_chunks.py`、`test_mapping.py`。能力 Profile 和原始证据由 Documents/Skills 维护。 |
| Knowledge Skills | Workspace 历史审计记载 `ntbln-knowledge-skills` 的 main 为 `948f8ca10ec4405189ab023cbba816ddc876184e`。Mac mini 的 projects / WorkBuddy 目录没有定位到该 checkout，未将历史提交记为已核对的当前版本。 |
| Workspace | `docs/PHASE1_CONVERGENCE.md` B1 定义保留源、标准解析、能力 Profile 和人工审核的跨仓分工；本方案与 `WORKSPACE_V2_PLAN.md` P1.5/P2 对接。 |

2026-11-04 通过 Frappe 元数据和聚合查询确认 `192.168.10.204` 的 `dev-bench/sites/carl` 正在运行 `25daf65`。有 Test Standard 7、Test Method 8、Laboratory Profile 1、Item 18、Item Price 20。Test Program Item 和 Test Request Item 均为子表，各 5 行。没有 Test Item、Laboratory、Laboratory Capability、Capability Source DocType。存在 Laboratory Capability Center Workspace 记录；存在 Item.custom_reli_test_method。业务基线为 Customer 15、Quotation 4、Test Request 5、Test Report 3。这些是站点计数，不能视作 L11464 已导入或已匹配。

对账结果及输入哈希见 [JSON 报告](acceptance/cnas-p1-5-source-preview.json)。开发站快照的保守匹配得到 0 个完整标准版本精确候选、2 个方法同名候选、0 个实验室全称精确候选，现有 7 个启用的非库存销售 Item。名称匹配只供人工检查；零精确候选仍须排查别名及历史编码。所有创建和更新均保持未执行。

## 字段差异与映射

「新增」表示待实现的字段或表名。必填分为候选入库和发布，未知字段可保留在审核台账。

| 原始字段 | 标准字段 | Frappe 目标 | 类型 | 必填 | 来源 | 验证规则 |
|---|---|---|---|---|---|---|
| labs.csv.code / 注册号 | lab_key | Laboratory Profile + 新增实验室外部标识映射 | Link + Data | 导入 | Workbench、实验室核实 | 显式绑定已有 Profile；不能猜 Mercur seller ID |
| lab name/address | lab_name/address | Laboratory Profile.laboratory_name；地址作为源证据 | Data / JSON | 名称需核对 | Workbench / 证书 | 不覆盖现有入驻资料 |
| source type / reg_no | accreditation_type, certificate_no | Capability Source、Laboratory Capability 同名字段 | Select / Data | 发布 | 已审证书 | CNAS 和 CMA 分开验证；不推断 CMA |
| valid_from / valid_to | certificate_validity | Capability Source.issue_date/expiry_date（日期语义一致时）；否则新增有效期起止 | Date | 发布时需有效 | 证书 | 起止时间有效；签发日不可代替生效日 |
| items.item_code | method_key | Test Method 新增 cnas_method_code 或外部 ID 映射 | Data | 导入 | method_codes.csv | 稳定唯一；同名仅供匹配复核 |
| item_name, custom_raw_names | method_name, aliases | Test Method.method_name；别名保留来源 JSON | Data / JSON | 名称必填 | items.csv、merge_map.csv | 禁止覆盖手工名称或推断同名同方法 |
| custom_test_category/subcategory | method_category | Test Method.category；子分类保留来源 JSON | Data / JSON | 否 | items.csv | 分类文本保留原值 |
| standards.standard_no, std_year | standard_code, version | Test Standard.standard_code/version | Data | 导入 | standards.csv | 编号＋完整版本精确匹配；年份不足以代替修订号 |
| standard_name | standard_title | Test Standard.title | Data | 导入 | standards.csv | 空或截断进审核；新增标准默认 Draft |
| standards.local_path, doc_status | standard_evidence | Test Standard.attachment / Documents 已审版本引用 | Attach / Data | 证据按流程 | Documents | 本地路径不是受控 File；保留旧附件 |
| scope.parent, test_object, object_category | method_key, product_scope, object_category | Laboratory Capability.test_method/product_scope；新增 object_category | Link / Small Text / Data | 方法与对象必填 | scope_standards.csv | 对象和分类保留，禁止模糊扩大认可范围 |
| scope.standard / standard_name | standard_key | Laboratory Capability.test_standard | Link | 导入 | scope_standards.csv | 匹配完整标准版本，无法唯一匹配进待审 |
| 项目名、独立参数 | test_catalog_item, parameter | 新增项目目录与参数子表；能力链接到目录项 | Link / Table | 有可证实项目时 | Documents 已审提取 | CSV 把项目归入方法，没有独立参数列；不复用业务单据子表作主数据 |
| clause | clause | Laboratory Capability 新增 clause | Small Text | 按原件 | scope_standards.csv | 保留多级编号和版本，不把年份尾部误作条款 |
| limit_note | limitation | Laboratory Capability.limitation；capability_scope 保存可读范围 | Small Text | 有限制时必填 | scope_standards.csv | 保留条件、数值单位、不认可范围 |
| effective_date | scope_effective_date | Laboratory Capability 新增 scope_effective_date | Date | 有来源时 | scope_standards.csv | 不写进 Test Standard.effective_date；格式及范围核验 |
| parent + idx、物理原始行 | export_key, source_row | Capability Source 新增行级台账；Laboratory Capability.source_row | Data / Int | 导出键必填；原始行发布必填 | CSV、Documents | idx 只在 parent 内有效，不等于原始行 |
| 原 PDF、页码和块定位 | evidence_file, page, block_id | Capability Source 新增私有 File 引用；行台账新增 page/block_id | Link / Int / Data | 发布 | Documents 审核版本 | PDF 哈希、1 起始页码和原块定位；历史 CSV 缺失 |
| 文档 ID / 版本 / 批次 | source_id, source_version, batch_hash | Capability Source.documents_source_id/documents_version；新增 batch_hash | Data | 入库 | Documents / 源文件摘要 | 来源版本不可变；同输入同摘要；保存 CSV 原值和归一化修复日志 |
| 校验问题、解析审核结果 | parse_status, review_status | 行台账新增 parse_status/issues；Laboratory Capability.status；Capability Source.documents_review_status | Select / JSON | 必填 | validator、Documents、审核员 | 拦截、警告、重复分别记录；文档批准、能力发布、商品审核独立 |
| 商品、实验室、项目、方法及标准 | service_eligibility | 新增 Item 与 Laboratory Capability 关联，旧 custom_reli_test_method 保留 | Link / Table | 报价 | 业务人员 | 多对多；活动、可销售、非库存；所有报价候选须已审核发布 |
| 单价、币种、价目表、日期 | approved_rate | Item Price + 按实验室的服务价绑定 | Link / Currency / Date | 正式报价 | 销售审批 | 同 Item/实验室/币种/UOM/日期只取明确的有效价格；缺价待定 |

## 导入预览与数据保护

1. 固定源提交和哈希。运行 `python3 tools/preview_cnas_seed.py <cnas-workbench>`，输出 JSON 和证据缺口。源对账不读取站点，站点基线另查。后续写入器必须先输出逐行 create/reuse/conflict/review 和当前站点快照哈希。
2. 在开发站备份数据库和附件。选择性移植旧分支的 DocType、权限和生命周期；新增字段保持可空，记录版本，不重命名或删除旧字段。先做可回退的结构迁移，再核对标准、方法、项目与参数、能力、来源，最后人工审核。既有主数据只在明确批准的差异中更新。
3. 使用不可变 source ID/version/hash 与逐行台账；存储原始记录和所有修复，重复行链接到保留行。跨批次用实验室、项目/方法、标准版本、检测对象、条款、限制与有效期比较。同一业务键出现证据或内容冲突时进入待审，禁止覆盖。应用唯一约束及批次锁，快照改变要求重新预览。预检失败不开始写入，应用失败回滚整个事务。
4. 数据撤回只撤销本批自建、未发布且无引用的记录，已有主数据保留；已用能力走停用和审计。全站恢复需要配对代码与备份，并在确认后使用，避免覆盖后续业务操作。
5. 此快照尚缺经核实的 L11464 对应 Profile、认可范围 PDF/页码/原始行和独立参数数据。CSV 中出现的 `GB /T 15763.2-2025` 需与归一化标准键对照，不因别名新建第二条标准。650 条是对账一致的候选，保留待确认；7 条阻断进入审核台账，20 条警告附原因，3 条重复保留证据关联。资料缺失必须保留显式状态，禁止赋予发布资格。

## P2 自主报价及开发验收

从客户和检测服务 Item 出发，按产品、参数、方法、完整标准版本、实验室、认可限制和日期选择已发布能力。保存报价行的 Item、能力 ID、匹配快照、定价来源、UOM、币种和金额。没有匹配或有效批准价时进入人工复核，不提交正式报价。能力批准后仍须独立审核商品关系与价格。客户确认通过现有入口关联委托申请，用报价及行 ID 保证重复确认不重复建委托，并走现有 Test Request 权限和履约状态机。

仅在开发站验收：核对源与现场计数，预览与应用一致，重复应用零新增，异常可重试，发布检查拒绝未审记录。以有价、缺价、超范围三个案例验证双向追溯及报价草稿，并验证确认重试只建一次委托、旧客户/报价/委托/报告可读可用。记录权限拒绝、备份恢复演练和差异，未执行的项目单独标注。

### 阶段一开发站运行记录

2026-11-04 在 `frappe-pilot / dev-bench / carl` 备份数据库和附件后完成结构迁移。使用原 Workbench 的既有输出，导入 `CAPSRC-00499`，新增 118 个方法候选、207 个标准候选和 650 条待确认能力。7 条阻断、3 条重复和完整原始 CSV 行都保存在来源快照中。开发档案使用明确的测试商家标识。历史来源不能用作正式发布证据。重跑返回 0 新增；同一能力分别通过五个查询维度命中。开发站共 652 条未发布能力（含 2 条既有记录），客户、报价、委托和报告计数仍为 15、4、5、3。当前试验条件以能力上的 JSON 字段定义，未从历史证据推测工程参数。
