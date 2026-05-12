# NewsData MCP Server

An MCP server for [NewsData.io](https://newsdata.io/documentation) that exposes real-time, historical, crypto, market, source-discovery, and aggregate-count tools to any MCP-compatible client.

## Available Tools

| Tool | Endpoint | Description |
|---|---|---|
| `get_latest_news` | `/api/1/latest` | Recent and breaking news (last 48h) |
| `get_archive_news` | `/api/1/archive` | Historical news, filterable by `from_date` / `to_date` |
| `get_crypto_news` | `/api/1/crypto` | Crypto and blockchain-focused coverage |
| `get_market_news` | `/api/1/market` | Stock, financial, and market-related news |
| `get_news_sources` | `/api/1/sources` | Source discovery by country, category, or language |
| `get_news_counts` | `/api/1/count` | Aggregate article counts over a date range (`hour` / `day` buckets or single `all` total) |
| `get_crypto_counts` | `/api/1/crypto/count` | Aggregate crypto article counts over a date range |
| `get_market_counts` | `/api/1/market/count` | Aggregate market article counts over a date range |

All tools are read-only and idempotent; the MCP-protocol annotations let compatible clients (Claude Code, MCP Inspector, etc.) cache and parallelize calls.

---

## Installation

```bash
git clone https://github.com/newsdataapi/newsdata.io-mcp.git
cd newsdata.io-mcp
uv sync
```

### Configure environment

Copy `.env.example` to `.env` and fill in your API key:

```bash
cp .env.example .env
# then edit .env
```

| Variable | Default | Notes |
|---|---|---|
| `NEWSDATA_API_KEY` | _(required)_ | NewsData.io credential. Missing key returns an error envelope on every call. |
| `REQUEST_TIMEOUT` | `30` | Per-request timeout in seconds. |
| `NEWSDATA_BASE_URL` | `https://newsdata.io/api/1` | Override for staging or a local mock. |
| `NEWSDATA_MAX_RETRIES` | `5` | Maximum attempts for transient failures (network, 5xx, 429). |
| `NEWSDATA_RETRY_BACKOFF` | `2.0` | Base for exponential backoff (`base * 2^(attempt-1)`). Seconds. |
| `NEWSDATA_RETRY_BACKOFF_MAX` | `60.0` | Cap on a single retry sleep, seconds. |
| `NEWSDATA_INTEGRATION_KEY` | _(unset)_ | Used only by `pytest -m integration`. Without it, live-API tests skip. |

All values are read at module import time; restart the server after changing them.

---

## Running the Server

### stdio transport (for desktop / CLI clients)

```bash
uv run newsdata-mcp --transport stdio
```

### Streamable HTTP transport

```bash
uv run newsdata-mcp --transport streamable-http --host 0.0.0.0 --port 8000
```

### Module syntax (alternative)

```bash
python -m newsdata_mcp.server --transport stdio
python -m newsdata_mcp.server --transport streamable-http --host 0.0.0.0 --port 8000
```

### Version

```bash
uv run newsdata-mcp --version
```

---

## Docker

```bash
docker build -t newsdata-mcp .
docker run --rm -p 8000:8000 -e NEWSDATA_API_KEY=your_newsdata_api_key newsdata-mcp
```

Run in stdio mode:

```bash
docker run --rm -i -e NEWSDATA_API_KEY=your_newsdata_api_key newsdata-mcp --transport stdio
```

Pass a `.env` file:

```bash
docker run --rm -p 8000:8000 --env-file .env newsdata-mcp
```

The image is a multistage build: dependencies are installed from `uv.lock` in a `python:3.12-slim` builder, then the resulting venv plus `LICENSE` is copied into a fresh `python:3.12-slim` runtime. The container runs as a non-root `app` user.

---

## Editor & Client Integrations

The simplest way is to add the server to your MCP client's JSON config. Each client picks up the config on restart. Substitute `/path/to/newsdata.io-mcp` for your local clone path.

### Claude Code

Either edit `~/.claude/mcp.json` (global) or `.claude/mcp.json` (per-project):

```json
{
  "mcpServers": {
    "newsdata-mcp": {
      "command": "uv",
      "args": ["run", "newsdata-mcp", "--transport", "stdio"],
      "cwd": "/path/to/newsdata.io-mcp",
      "env": {
        "NEWSDATA_API_KEY": "your_newsdata_api_key"
      }
    }
  }
}
```

Then restart Claude Code.

### Claude Desktop

Edit `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or `%APPDATA%\Claude\claude_desktop_config.json` (Windows) — same JSON block as above. Restart Claude Desktop.

### Cursor

Create or edit `.cursor/mcp.json` in your project root (or `~/.cursor/mcp.json` globally) — same JSON block. Restart Cursor; the server appears under **Cursor Settings → MCP**.

### VS Code (GitHub Copilot)

Create `.vscode/mcp.json` in your workspace (or add an `mcp` key to user settings):

```json
{
  "servers": {
    "newsdata-mcp": {
      "type": "stdio",
      "command": "uv",
      "args": ["run", "newsdata-mcp", "--transport", "stdio"],
      "cwd": "/path/to/newsdata.io-mcp",
      "env": {
        "NEWSDATA_API_KEY": "your_newsdata_api_key"
      }
    }
  }
}
```

Reload VS Code. Picked up by Copilot Chat in agent mode.

### Windsurf

Edit `~/.codeium/windsurf/mcp_config.json` — same JSON block as the Claude Code example. Restart Windsurf.

### ChatGPT Desktop (OpenAI)

Run the server in HTTP mode locally:

```bash
uv run newsdata-mcp --transport streamable-http --host 127.0.0.1 --port 8000
```

Then in **ChatGPT → Settings → Connectors → Add custom connector**, register `http://127.0.0.1:8000/mcp` as the connector endpoint.

---

## Example Tool Calls

```text
get_latest_news(
  q="((pizza OR burger) AND healthy)",
  country=["us", "gb"],
  language="en",
  size=10
)
```

```text
get_archive_news(
  q="ukraine war",
  from_date="2025-01-01",
  to_date="2025-01-31",
  language="en"
)
```

```text
get_crypto_news(
  coin=["btc", "eth"],
  sentiment="positive"
)
```

```text
get_market_news(
  symbol=["AAPL", "NVDA"],
  country="us"
)
```

```text
get_news_sources(
  language="en",
  priority_domain="top"
)
```

```text
get_news_counts(
  from_date="2024-01-01",
  to_date="2024-01-31",
  q="bitcoin",
  interval="day"
)
```

```text
get_market_counts(
  from_date="2024-01-01",
  to_date="2024-03-31",
  symbol=["AAPL", "NVDA"],
  interval="hour"
)
```

```text
get_latest_news(
  q="elections",
  sentiment="positive",
  sentiment_score=70
)
```

Notes on parameter shapes:
- CSV-style filters accept either a Python list (preferred) or a comma-separated string.
- Boolean flags accept `True`/`False` or `1`/`0`.
- `timeframe` accepts an integer for hours (e.g. `24`) or a string with `m` suffix for minutes (e.g. `90m`).
- `interval` (count tools only) accepts `hour`, `day`, or `all` (`all` returns a single aggregate count instead of buckets).
- `sentiment_score` is a 0–100 minimum confidence percentage and requires `sentiment` to also be set — e.g. `sentiment="positive", sentiment_score=70` returns only articles whose positive-sentiment score is at least 70.

---

## Notes

- Latest, crypto, and market endpoints return recent coverage — typically up to 48 hours.
- Free plan results are delayed relative to paid plans.
- Result `size` is capped by plan tier: commonly 10 results on free, up to 50 on paid plans.
- The count endpoints return aggregate buckets (one per `interval` slot) rather than article content.
- Every tool returns plain text (the MCP-protocol return type). Errors come back as `Error (HTTP 4xx): …` with the status code and a friendly message; HTTP 429 errors include a `retry after Ns` hint when the upstream `Retry-After` header was parseable.

Full API reference: [https://newsdata.io/documentation](https://newsdata.io/documentation).

---

## Development

```bash
uv sync --all-groups                                       # install dev deps
uv run pytest                                              # unit tests only (default)
NEWSDATA_INTEGRATION_KEY=<key> uv run pytest -m integration  # live-API tests
uv run pytest --cov=newsdata_mcp --cov-report=term-missing  # with coverage
uv run ruff check src/ tests/
uv run mypy
```

CI (`.github/workflows/ci.yml`) runs the same four commands on every push/PR to `main`.

## License

MIT. See the [LICENSE](LICENSE) file.
