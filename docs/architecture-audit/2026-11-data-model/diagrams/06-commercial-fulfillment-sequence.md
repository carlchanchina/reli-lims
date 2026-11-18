# 图 6 · Quotation → Sales Order → Test Request → Test Program → Test Report

```mermaid
sequenceDiagram
  autonumber
  actor S as 销售/商业接单中心
  participant Q as Quotation
  participant SO as Sales Order
  participant TR as Test Request
  participant TP as Test Program
  participant RP as Test Report
  participant C as Customer

  S->>Q: capability_quotation.prepare_lines(selections)
  Q->>Q: build_configuration → custom_reli_configuration(JSON)
  Q->>Q: validate: capability_id 一致 / 已发布 / rate >= 0
  Note over Q: 三列字典（project/object/standard）由 live capability 覆写
  S->>C: 发送报价（document_output / portal quotation.accept）
  C-->>Q: Quotation Portal Acceptance
  Q->>SO: ERPNext 原生 map（保留 custom_reli_business_type）
  SO->>TR: sales_order_testing.prepare_lines（只取有 capability+configuration 的行）
  Note over SO,TR: lock_quotation_lines / validate_order_capacity → CAPACITY_CONFLICT
  TR->>TR: capability_request.prepare_items → technical_configuration
  TR->>TR: 客户共填 Web Form（customer_share，Test Request Share Event 审计）
  TR->>TP: services/test_request.make_test_program
  TP->>TP: Test Program Item（equipment_snapshot / technical_configuration）
  TP->>RP: Test Report（version / status Draft→Review→Approved→Issued）
  RP-->>C: portal_runtime.dispatch test-report.pdf
```

证据边界：`Quotation → Sales Order` 使用 ERPNext 原生映射（非 reli_lims 代码），reli_lims 只提供字段与校验；`make_test_program` 实现在 `reli_lims/services/test_request.py:85`。
