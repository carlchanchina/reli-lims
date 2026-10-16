# Desk acceptance and role permissions

Spec: AGENTS.md, docs/DATA_MODEL.md, docs/DESK_DEMO.md, user approval of steps 1–3.

## Task 1: Browser acceptance and persistent demonstration

Open the actual test site, create clearly marked demonstration records through Desk and execute two samples/three experiments through issue. Keep record identifiers and screenshots. Do not reset existing credentials or use the operational carl site.
Expected: browser workflow completes, retained demo records identified.

## Task 2: Role and private file permissions

Add integration tests covering manager/engineer/reviewer DocType access, prohibited review/approval/issue, ERPNext link access with explicitly assigned ERPNext roles, and private File access. Run on test site only.
Expected: positive and negative role checks pass.

## Task 3: Desk form corrections

Write failing Node tests for deletion guards before implementing. Block deletion of samples/items with existing assignments with targeted messages; prevent removing started items; explain valid state sequence. Preserve existing server validation and HTML escaping.
Expected: all Node tests and Python distribution tests pass; browser verification after backend restored.

Review focus: client guards must not replace server permissions; no silent deletion, no unrelated ERPNext permission changes.
