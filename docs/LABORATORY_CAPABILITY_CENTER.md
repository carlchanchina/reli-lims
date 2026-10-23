# V1.1 实验室能力中心

## 架构边界

- `carlchanchina/wekona_documents`：文档理解、OCR/LLM、PDF/Excel 解析及人工审核。
- `reli-lims`：已审核结构化能力的导入、人工确认、发布及检测能力业务真相。
- Wiki：知识展示。Mercur：交易投影；本版本不自动写入这两个系统。

复用 Laboratory Profile、Test Method、Test Standard；不新建实验室/方法/标准的平行主数据，不绑定方法与标准为永久一对一。不修改检测委托、Project、Sample、Test Program、Test Report 主流程。

## 来源合同与信任边界

由受信任 Lab Manager/System Manager 从 Documents 已审核版本录入 Capability Source，记录 documents_source_id、documents_version 和源文件引用。V1.1 是管理员受控交接，**尚未实现向远程 Documents 验证审批签名或实时查询审批状态的连接器**；本地 Approved 字段不是远程审批证明。禁止把商家或 Guest 提交的 JSON 直接标记 Approved。上线前由操作人员核对源仓库的实际审核记录。

structured_json 必须为对象且包含非空 items 数组。每行包含 test_method（现有名称或 ID）、standard_code/test_standard（现有代码或 ID）、唯一 source_row（缺省行号）、capability_scope，可选 product_scope、limitation、accreditation_type、certificate_no、remarks。不读取原始文件、不解析文档。未知主数据返回 skipped，需管理员匹配已有主数据后重试。

同一来源导入加数据库行锁，以 laboratory/source/source_row 幂等复用能力。documents_source_id 全局唯一；V1.1 不覆盖既有来源的版本。新审批版本应使用新的版本化来源 ID，保留旧记录。来源状态撤销同步尚未实现，运营人员必须先取消发布受影响能力。

## 操作与权限

中文 Desk 工作台“实验室能力中心”提供实验室资料、能力来源、待确认能力、已发布能力和现有检测项目/标准入口。

1. 管理员录入审核后的来源并点击“导入能力”。
2. 管理员或 Lab Reviewer 核对能力后点击“确认能力”。
3. Lab Manager/System Manager 点击“发布能力”；同角色可“取消发布”。
4. 已确认/已发布业务内容受保护；修改前取消发布，再将状态退回待确认。

所有写 API 仅接受 POST，使用 Frappe 会话、权限及事务；不手工 commit。Guest 没有 DocType 读写权限。公共只读 get_public_capability(name)、list_public_capabilities(laboratory=None) 仅输出已发布记录的白名单字段，列表最多 100 条，不返回源 JSON、证据文件、内部备注或交易映射 ID。

## 测试 Demo

在隔离测试站点执行 `bench --site <test-site> execute reli_lims.demo_capabilities.seed_demo_capabilities`。

创建/复用 1 个“苏州可靠性检测实验室”（sel_demo_reliability_lab）、2 条待确认且未认证能力：低温试验 GB/T 2423.1-2008、随机振动试验 GB/T 2423.56-2023。证书编号为空，来源标注“仅测试数据，不代表真实资质或认可”。不会自动发布，不构成真实实验室入驻审核或资质证明。脚本幂等，不自动提交事务。

## 验证

本地：`python3 -m unittest discover -s tests`；`python3 -m compileall -q reli_lims`；`git diff --check`。

Frappe 集成：先在独立 Frappe 16/ERPNext 16 测试站点安装本分支并 migrate，再执行 `bench --site <test-site> run-tests --module reli_lims.tests.test_capability_center_integration`。本次开发环境无已配置 apps/sites/Procfile，Python 无 frappe 包，因此数据库集成、migrate 和 Desk 浏览器验收未执行；不能将 stub 单元测试视作集成通过。

### 开发服务器验收补充（2026-10-23）

已在 192.168.10.204 的 Pilot dev-bench、独立站点 reli-acceptance-20261020.localhost 完成 migrate（退出码 0）及 4 项真实 Frappe 集成测试（全部通过）。测试改放功能测试目录，避免 DocType 自动生成依赖测试记录。部署前已备份现有应用到 /home/frappe/reli-lims-before-capability-v11.tgz，仅加入能力中心文件，保留服务器原有主流程开发改动。上文无环境限制为首次本地检查记录，已由本次远程集成验证补充；Desk 浏览器验收仍单列。
