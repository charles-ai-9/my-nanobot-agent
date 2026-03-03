---
name: generate_sql
description: 生成符合 MaxCompute（ODPS）规范的标准化 SQL，基于本地 JSON 知识库的真实表名与字段名。
always: true
metadata: {"nanobot":{"always":true}}
---

# SQL 生成规范（MaxCompute / ODPS）

收到 SQL 或数据查询需求时，必须先读取以下两个文件获取真实的表名和字段名，再生成 SQL：

- `/Users/charles/Desktop/data_warehouse_mgr/table_catalog.json`
- `/Users/charles/Desktop/data_warehouse_mgr/table_details/<table_name>.json`

**生成规则：**
- 表名和字段名必须与文件中完全一致，不得假设或自造
- 表名已包含 project（如 `p_mgr_id_mart.pinjam.xxx`），不需要 `USE` 语句
- 必须包含 `_partition_value BETWEEN 'YYYYMMDD' AND 'YYYYMMDD'` 分区过滤
- 今日日期从 Runtime Context 中读取，"最近N天"动态计算对应的 YYYYMMDD 范围
- `business_rule` 含"非空" → `IS NOT NULL`；含"大于0" → `> 0`
- 禁止：`WITH`、`LIMIT`、`CURDATE()`、`INTERVAL`、`GETDATE()`
- 只输出可执行的 SQL，不加任何注释、说明文字或包装
