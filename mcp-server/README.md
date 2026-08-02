# mcp-server-life-guardian

A Model Context Protocol server that exposes the **AI 智慧管家** smart-community
service platform to external agents.

An agent can take a resident's sentence, turn it into a dispatchable task, match
local vendors, open a case, and drive it to completion — without touching the
web UI.

## Design

```
外部 Agent ──MCP(streamable-http 或 stdio)──▶ mcp-server-life-guardian
                                                     │ HTTP
                                                     ▼
                                        AI 智慧管家 REST API (FastAPI)
                                                     │
                                        PostgreSQL + Amazon Bedrock
```

The MCP server holds **no business logic**. Every tool is one call to the
platform's own REST API, so the case state machine, the privacy gate and all
validation stay in a single place and this server stays a replaceable adapter.

It also runs as its own image on purpose: the MCP SDK needs a much newer
`starlette` than FastAPI 0.115 permits, and installing both into one interpreter
breaks FastAPI at import time.

Layout follows the reference servers in
[modelcontextprotocol/servers](https://github.com/modelcontextprotocol/servers)
(`pyproject.toml` console script → `__init__.main()` → `server.serve()`). It uses
the SDK's v2 `MCPServer` API rather than the low-level `Server` those servers
use, because v2 removed the `@server.list_tools()` / `@server.call_tool()`
decorators they are written against.

## Tools

| Tool | Reads/Writes | Purpose |
| --- | --- | --- |
| `list_service_categories` | read | Which service domains the platform dispatches |
| `analyze_life_demand` | write | One sentence → structured task + what is still missing |
| `get_task_conditions` | read | Current field values and outstanding fields |
| `update_task_conditions` | write | Write answers back, optionally mark ready to match |
| `match_vendors` | read | Hard-filter by category + area, then AI ranks with reasons |
| `create_case` | write | Dispatch the task to one vendor, produces a case number |
| `get_case` | read | Status, next action, timeline, what the vendor can see |
| `get_case_by_task` | read | The task's latest case, or null |
| `confirm_case` | write, irreversible | Resident confirms the quote → unlocks contact details |
| `complete_case` | write, irreversible | Service delivered, closes case and task |
| `get_resident_dashboard` | read | All of one resident's tasks plus counters |
| `list_vendors` | read | Active vendors and their open-case counts |
| `list_vendor_cases` | read | Vendor-side inbox, redacted until confirmation |
| `vendor_respond_to_case` | write | Accept (with a proposed time) or reject |

### The privacy gate matters

While a case is `waiting_vendor_response` or `vendor_accepted`, the vendor-facing
tools return only the city and district. The full street address, contact name
and phone appear **only** after the resident calls `confirm_case`. That is
enforced by the platform API, not by this adapter, so an agent cannot route
around it.

## Running

### stdio (agent spawns the process)

```bash
pip install -e .
mcp-server-life-guardian --api-base-url http://localhost:8000
```

### Streamable HTTP (remote agents such as Lumine one)

```bash
mcp-server-life-guardian \
  --transport streamable-http \
  --api-base-url http://localhost:8000 \
  --port 8081 \
  --allowed-host localhost:8081 \
  --allowed-host mcp.example.com
```

The endpoint is `http://<host>:8081/mcp`.

`--allowed-host` is not optional in practice. The SDK's DNS-rebinding protection
accepts only requests addressed to localhost by default; behind any other
hostname every request is answered with **HTTP 421** until that hostname is
listed. Pass one `--allowed-host` per name, or set `MCP_ALLOWED_HOSTS` to a
comma-separated list.

### Docker Compose

The repository root ships an `mcp` service:

```bash
docker compose up -d mcp
```

It talks to the backend over the compose network and publishes
`http://localhost:8081/mcp`.

## Configuration

| Flag | Env | Default | Notes |
| --- | --- | --- | --- |
| `--api-base-url` | `LIFE_GUARDIAN_API_BASE_URL` | `http://localhost:8000` | Platform REST API |
| `--transport` | `MCP_TRANSPORT` | `stdio` | `stdio` or `streamable-http` |
| `--host` | `MCP_HOST` | `0.0.0.0` | HTTP bind address |
| `--port` | `MCP_PORT` | `8081` | HTTP port |
| `--timeout` | `MCP_API_TIMEOUT` | `90` | Seconds; demand analysis and ranking are LLM calls |
| `--allowed-host` | `MCP_ALLOWED_HOSTS` | – | Repeatable / comma-separated |
| `--allowed-origin` | `MCP_ALLOWED_ORIGINS` | – | Repeatable / comma-separated |
| `--log-level` | `MCP_LOG_LEVEL` | `INFO` | Logs go to stderr |

## Client configuration

Kiro / Claude Desktop / Cursor, spawning it locally:

```json
{
  "mcpServers": {
    "life-guardian": {
      "command": "mcp-server-life-guardian",
      "args": ["--api-base-url", "http://localhost:8000"]
    }
  }
}
```

Via Docker:

```json
{
  "mcpServers": {
    "life-guardian": {
      "command": "docker",
      "args": [
        "run", "--rm", "-i", "--network", "ai-life-guardian_default",
        "ai-life-guardian-mcp",
        "--api-base-url", "http://backend:8000"
      ]
    }
  }
}
```

A remote agent that speaks Streamable HTTP points at the URL instead:

```json
{
  "mcpServers": {
    "life-guardian": { "url": "http://<host>:8081/mcp" }
  }
}
```

## Security

There is **no authentication** on the platform API or on this MCP server. Anyone
who can reach either can read and advance cases, including calling
`confirm_case`, which discloses a resident's address and phone to a vendor.
Before exposing this beyond a demo network you need, at minimum: auth on the
platform API, an allowlist of who may call the MCP endpoint, and per-user scoping
so a caller cannot act on another resident's tasks.
