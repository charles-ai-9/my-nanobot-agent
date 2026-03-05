"""MaxCompute SQL execution tool."""

import json
import os
from typing import Any

from nanobot.agent.tools.base import Tool

_MAX_RESULT_CHARS = 20000


class ExecuteSQLTool(Tool):
    """Tool to execute SQL on MaxCompute (ODPS) and return results as JSON."""

    @property
    def name(self) -> str:
        return "execute_sql"

    @property
    def description(self) -> str:
        return (
            "Execute a SQL query on MaxCompute (ODPS) and return the results as JSON. "
            "Use this after generating SQL to get real query results from the data warehouse. "
            "For large result sets, use LIMIT in the SQL or set the limit parameter."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "sql": {
                    "type": "string",
                    "description": "The SQL query to execute on MaxCompute. Always include LIMIT in the SQL for large tables.",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of rows to return. Defaults to 50.",
                    "minimum": 1,
                    "maximum": 500,
                },
            },
            "required": ["sql"],
        }

    async def execute(self, sql: str, limit: int = 50) -> str:
        access_id = os.environ.get("ODPS_ACCESS_ID")
        access_key = os.environ.get("ODPS_ACCESS_KEY")
        project = os.environ.get("ODPS_PROJECT")
        endpoint = os.environ.get("ODPS_ENDPOINT")
        sts_token = os.environ.get("ODPS_STS_TOKEN")

        missing = [k for k, v in {
            "ODPS_ACCESS_ID": access_id,
            "ODPS_ACCESS_KEY": access_key,
            "ODPS_PROJECT": project,
            "ODPS_ENDPOINT": endpoint,
        }.items() if not v]
        if missing:
            return json.dumps({
                "error": f"Missing required environment variables: {', '.join(missing)}"
            }, ensure_ascii=False)

        try:
            from odps import ODPS
            from odps.accounts import AliyunAccount, StsAccount
        except ImportError:
            return json.dumps({
                "error": "pyodps is not installed. Run: pip install pyodps"
            }, ensure_ascii=False)

        try:
            if sts_token:
                account = StsAccount(access_id, access_key, sts_token)
            else:
                account = AliyunAccount(access_id, access_key)

            o = ODPS(
                account=account,
                project=project,
                endpoint=endpoint,
            )

            instance = o.execute_sql(sql)
            instance.wait_for_success()

            with instance.open_reader() as reader:
                rows = []
                for i, record in enumerate(reader):
                    if i >= limit:
                        break
                    row = {col.name: val for col, val in zip(record._columns, record.values)}
                    rows.append(row)

            result = json.dumps({
                "row_count": len(rows),
                "rows": rows,
            }, ensure_ascii=False, default=str)

            if len(result) > _MAX_RESULT_CHARS:
                truncated = result[:_MAX_RESULT_CHARS]
                return truncated + f'\n[截断：结果过大，已截断至 {_MAX_RESULT_CHARS} 字符，建议在 SQL 中加 LIMIT 或减少查询列数]"'

            return result

        except Exception as e:
            return json.dumps({"error": str(e)}, ensure_ascii=False)

