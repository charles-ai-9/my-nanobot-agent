---
name: generate_sql
description: 生成符合 MaxCompute（ODPS）规范的标准化 SQL，基于本地 JSON 知识库的真实表名与字段名。
always: true
metadata: {"nanobot":{"always":true}}
---

# SQL 生成规范（MaxCompute / ODPS）

收到 SQL 或数据查询需求时，静默读取以下两个文件，然后直接输出结果，不输出任何中间过程：

1. 读取 `/Users/charles/Desktop/data_warehouse_mgr/table_catalog.json`，匹配相关表，获取 `table_name`
2. 读取 `/Users/charles/Desktop/data_warehouse_mgr/table_details/<table_name>.json`，获取 `fields[].field_name` 和 `fields[].business_rule`

**生成规则：**
- 表名和字段名必须与文件中完全一致，不得假设或自造
- 表名已包含 project（如 `p_mgr_id_mart.pinjam.xxx`），不需要 `USE` 语句
- 必须包含 `_partition_value BETWEEN 'YYYYMMDD' AND 'YYYYMMDD'` 分区过滤
- 今日日期从 Runtime Context 中读取，"最近N天"动态计算对应的 YYYYMMDD 范围
- `business_rule` 含"非空" → `IS NOT NULL`；含"大于0" → `> 0`
- 禁止：`WITH`、`LIMIT`、`CURDATE()`、`INTERVAL`、`GETDATE()`

**输出格式（严格遵守）：**

第一行固定输出：根据你的描述，帮你完成如下 SQL 供参考：
第二行起用三个反引号加 sql 标记开头、三个反引号结尾，将完整 SQL 包裹输出。

比如,输出模板参考如下：

模板开始位置：
根据你的描述，帮你完成如下 SQL 供参考：

```sql
SELECT
    user_id,
    order_id,
    pay_amount
FROM
    p_mgr_id_mart.pinjam.dwd_order_detail
WHERE
    _partition_value BETWEEN '20260201' AND '20260303'
    AND pay_amount > 0
    AND user_id IS NOT NULL;"
```
模板结束位置

**严格禁止：**
- 禁止输出任何 JSON 内容
- 禁止输出工具调用过程或中间步骤
- 禁止输出除引导语和 SQL 代码块以外的任何文字
