"""MaxCompute SQL execution tool."""

import json
import os
from typing import Any

from nanobot.agent.tools.base import Tool


class ExecuteSQLTool(Tool):
    """Tool to execute SQL on MaxCompute (ODPS) and return results as JSON."""

    @property
    def name(self) -> str:
        return "execute_sql"

    @property
    def description(self) -> str:
        return (
            "Execute a SQL query on MaxCompute (ODPS) and return the results as JSON. "
            "Use this after generating SQL to get real query results from the data warehouse."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "sql": {
                    "type": "string",
                    "description": "The SQL query to execute on MaxCompute.",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of rows to return. Defaults to 500.",
                    "minimum": 1,
                    "maximum": 5000,
                },
            },
            "required": ["sql"],
        }

    async def execute(self, sql: str, limit: int = 500) -> str:
        access_id = os.environ.get("ODPS_ACCESS_ID")
        access_key = os.environ.get("ODPS_ACCESS_KEY")
        project = os.environ.get("ODPS_PROJECT")
        endpoint = os.environ.get("ODPS_ENDPOINT")

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
        except ImportError:
            return json.dumps({
                "error": "pyodps is not installed. Run: pip install pyodps"
            }, ensure_ascii=False)

        try:
            o = ODPS(
                access_id=access_id,
                secret_access_key=access_key,
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
                    rows.append(record.to_dict())

            return json.dumps({
                "row_count": len(rows),
                "rows": rows,
            }, ensure_ascii=False, default=str)

        except Exception as e:
            return json.dumps({"error": str(e)}, ensure_ascii=False)

