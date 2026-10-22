# Reli LIMS

Lean laboratory execution module for ERPNext / Frappe.

## Product Positioning

Reli LIMS is not a standalone LIMS suite and does not duplicate ERPNext CRM, Project, Asset, Sales, Accounting, HR, or Quality capabilities.

It focuses on the laboratory execution flow after a commercial order has been won:

`ERPNext Project -> Sample -> Test Program -> Test Program Item -> Result / Quality Inspection -> Test Report`

## Core Principles

1. ERPNext is the operational backbone.
2. No separate admin SPA for V1; use Frappe Desk and Workspace.
3. One Test Program can contain one or many Samples.
4. One Test Program contains many Test Program Items.
5. Each Test Program Item selects exactly one execution standard.
6. A Test Method can be reusable across multiple standards.
7. Asset, Employee/User, Project, Customer and Quality Inspection are reused from ERPNext.
8. Keep V1 deliberately small.

## Core DocTypes

- Sample
- Test Standard
- Test Method
- Test Program
- Test Program Sample (child)
- Test Program Item (child)
- Test Report

## V1 Non-Goals

- Customer portal UI
- Certification recommendation
- Target-market logic
- CRM replacement
- Accounting replacement
- Independent equipment master
- Independent project/task system
- Independent quality system

## Recommended Environment

- Frappe / ERPNext 16.x
- Python 3.11+
- MariaDB / Redis as required by Frappe

See `docs/` for architecture, data model, ERPNext integration and development plan.

## Install and verify

In an existing ERPNext 16 bench, replace `lab-test.localhost` with a dedicated
test site that already has ERPNext installed:

```sh
bench get-app https://github.com/carlchanchina/reli-lims.git --branch main
bench --site lab-test.localhost install-app reli_lims
bench --site lab-test.localhost migrate
bench --site lab-test.localhost run-tests --app reli_lims
```

The branch must be available on the remote before using `get-app`; for local
verification, pass this checkout's absolute path instead of the URL.

Assign Lab Manager, Lab Engineer or Lab Reviewer to a test user, then open
Testing Center in Desk. Testing Center exposes Samples, Test Programs, Test Standards, Test Methods,
Test Reports and ERPNext Assets.
Roles do not grant additional ERPNext Asset access; existing ERPNext permissions
still apply. Core masters, programs and reports use their own sequential document numbers.

Offline distribution checks (do not verify Frappe installation):

```sh
python3 -m unittest discover -s tests -v
python3 -m pip wheel --no-deps --wheel-dir /tmp/reli-lims-dist .
```

### Current validation environment

The Phase 1 skeleton has been installed and migrated on `wekona-test.localhost`
at `192.168.10.204`, in Pilot's `/home/frappe/pilot/benches/dev-bench`.
Installation and laboratory workflow integration tests run on this site.
Desk workspace configuration loads successfully; browser rendering has not yet
been visually inspected.

Pilot deployments without a `bench` executable can invoke the same site
commands from the bench's `sites` directory using the bench environment's
Python module `frappe.utils.bench_helper frappe`. Do not install a second
bench manager just to run these commands. The local feature branch has not
been pushed; the validation server received commit `a3a9a36` directly.

### Core masters

Sample, Test Standard and Test Method are now available in Testing Center.
Lab Manager maintains standards and methods; Lab Engineer can register/edit
samples; Lab Reviewer can read all three. Existing ERPNext roles must separately
grant access to Projects, Customers and Assets as appropriate.
Sample derives customer from Project on every save and requires positive
quantity. Standards have distinct document numbers and code/version/title;
method defaults are optional and reusable across standards. Files use Frappe's
standard attachments and Attach fields.

### Laboratory execution

Test Program supports many samples and many items. Each item selects one method
and one actual standard. Sample Assignments is a flat child relation keyed by
an immutable item code, avoiding nested child tables. Execution follows
Pending → Ready → Running → Completed → Reviewed; results and conclusions are
required for completion, and review requires Lab Reviewer or Lab Manager.

Reports follow Draft → Review → Approved → Issued. Lab Reviewer or Lab Manager approves; Lab Manager issues, and issue requires all items Reviewed plus
an attached private PDF. Approved business fields and issued report/program
content are locked; issued/revised reports cannot be deleted. Create a new report
version rather than changing issued content.

See [Desk demo](docs/DESK_DEMO.md) for the complete two-sample/three-item path.
PDF layout generation, analytical reports, dashboard metrics and portal APIs
remain outside this acceptance-path increment.


## V1 检测工作台

主线：检测委托单确认并关联 ERPNext Project → 实物收样 → 试验方案 → 检测项目执行与复核 → 检测报告审核及私有 PDF 签发。

工作台展示待确认委托、待收样、试验中、待报告、报告待审核、超期六张数字卡片。通过“打开检测主流程看板”进入 Frappe 原生八阶段 Kanban；阶段由真实业务记录自动计算，请进入单据执行收样、试验或审核操作。

日常入口仅保留新建检测委托、收样、试验方案、检测报告、检测项目、检测标准。项目、任务、设备和客户从二级分类访问，继续复用 ERPNext 权限。

升级前备份数据库和附件，更新应用并执行指定站点的 migrate、资源 build、clear-cache 和标准服务重载。迁移保留旧字段和内部英文标识，合并旧报告状态并记录审计评论；重复 migrate 不应重复创建本应用的卡片或看板。数据库回退需要同时恢复升级前代码与数据库备份。

测试必须运行在独立验收站点，不能在正式业务站点写入模拟结果。详情见 [V1 收口开发计划](docs/V1_CONVERGENCE_PLAN.md) 和 [实施日志](docs/IMPLEMENTATION_LOG.md)。
