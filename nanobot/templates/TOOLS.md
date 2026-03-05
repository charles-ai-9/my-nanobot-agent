# Tool Usage Notes

Tool signatures are provided automatically via function calling.
This file documents non-obvious constraints and usage patterns.

## execute_sql — MaxCompute SQL Execution

- Use this tool whenever the user asks to run, execute, or query SQL on MaxCompute/ODPS.
- Do NOT explain how to run SQL manually — always call this tool directly.
- The tool handles the connection automatically via environment variables.
- Supports a `limit` parameter (default 500, max 5000) to control returned rows.
- Always use this tool proactively when SQL execution is requested.

## exec — Safety Limits

- Commands have a configurable timeout (default 60s)
- Dangerous commands are blocked (rm -rf, format, dd, shutdown, etc.)
- Output is truncated at 10,000 characters
- `restrictToWorkspace` config can limit file access to the workspace

## cron — Scheduled Reminders

- Please refer to cron skill for usage.
