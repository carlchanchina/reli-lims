# CNAS 能力表幂等键契约（`Laboratory Capability.cnas_scope_key`）

一条 CNAS 能力行可能从两条路径进入 LIMS：

| 路径 | 生产者 | 写入方式 |
| --- | --- | --- |
| 历史批量导入 | `tools/export_cnas_dev_batch.py` → `reli_lims/cnas_dev_import.py` | Frappe 文档插入，`frappe.db.exists` 去重 |
| Workbench 解析写回 | `cnas-workbench server/testing_bridge.py` | REST 批量插入，先查 ERP 已有键再跳过 |

两条路径都靠同一列 `cnas_scope_key` 判重。**只要两侧算出的键有 1 字节差异，
同一行就会被写两遍**——不是覆盖，是新增重复能力行。

## 1. 规范形式

```
sha256(json.dumps([
    laboratory, item_code, standard_no, test_object,
    clause, limit_note, effective_date,
]).encode())
```

固定约束（改动即破坏契约）：

1. **字段顺序固定**，不得重排、不得追加。
2. **归一规则**：`str(value) if value else ""`。`None`、`""`、`0`、`False` 一律变 `""`。
3. **标准号回退**：`standard_no` 为空时取 `standard`。
4. **序列化**：沿用 `json.dumps` 默认值（`ensure_ascii=True`、`", "` / `": "` 分隔符），
   `str.encode()` 默认 UTF-8。中文被转义成 `\uXXXX`，两端字节一致。
5. **不做** `strip()` / `lower()` / Unicode NFKC 归一：值按原文哈希。任何"顺手清洗"
   都会让两侧分叉。

## 2. 唯一实现与对端来源

- LIMS 侧唯一实现：`reli_lims/cnas_scope.py`（纯函数，不 import frappe）。
- 对端实现：`carlchanchina/cnas-workbench` `server/testing_bridge.py::scope_key`。
- 向量文件 `tests/fixtures/cnas_scope_key_vectors.json` 的 `expected_scope_key`
  由对端代码**实际计算**生成，`source` 段记录 ref / commit / 文件 sha256。

## 3. 验证

```bash
# 15 条向量的契约测试（无需 bench）
python3 tests/test_cnas_scope_key_parity.py -v

# 导入器幂等（内存假 frappe，不连库）
python3 tests/test_cnas_dev_import_scope_key.py -v

# 跨仓库实时平价：git show 取对端实现，不动对端工作树
python3 tools/check_cnas_scope_key_parity.py
```

## 4. 既有键是否会变

只有"旧实现会写出 `json null` 或非字符串"的行会变键：`None` 字段、经
`standard` 回退的行、整型日期。七个字段都是非空字符串的行，键**逐字节不变**
（向量文件 `legacy_unchanged` 已逐条断言）。

因此本修复是**预防性**的，不做数据迁移；如需排查历史重复行，用只读脚本：

```bash
python3 tools/report_cnas_scope_duplicates.py --site carl \
    --scope-module /path/to/cnas_scope.py --out /tmp/report.json
```

## 5. 已知残余风险

- 对端 `build_capability_rows` 在调用 `scope_key` 前对 `laboratory` 做过
  `.strip()`，本侧直接使用文档名。Frappe 文档名不允许首尾空格，实际输入一致；
  若将来放开该限制，需同时收敛。
- `cnas_scope_key` 在库里不是唯一索引，去重依赖写入方先查后写；并发双写仍可能
  插重（与本次哈希修复无关）。
