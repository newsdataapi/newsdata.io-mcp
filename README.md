<div align="center">

![Newsdata.io logo](https://raw.githubusercontent.com/newsdataapi/newsdata.io-mcp/main/newsdata-logo.png)

# Newsdata.io MCP Server

[![PyPI Version](https://img.shields.io/pypi/v/newsdata-mcp?logo=pypi&color=3775a9)](https://pypi.org/project/newsdata-mcp/)
[![PyPI Downloads](https://img.shields.io/pypi/dm/newsdata-mcp?color=3775a9)](https://pypi.org/project/newsdata-mcp/)
[![CI](https://img.shields.io/github/actions/workflow/status/newsdataapi/newsdata.io-mcp/ci.yml?branch=main&logo=github&label=CI)](https://github.com/newsdataapi/newsdata.io-mcp/actions/workflows/ci.yml)
[![Python](https://img.shields.io/pypi/pyversions/newsdata-mcp?logo=python&logoColor=white)](https://pypi.org/project/newsdata-mcp/)
[![License](https://img.shields.io/badge/license-MIT-blue)](https://github.com/newsdataapi/newsdata.io-mcp/blob/main/LICENSE)
[![OpenAPI](https://img.shields.io/badge/OpenAPI-3.1-85EA2D)](https://newsdata.io/openapi.json)

</div>

The official MCP server for the [Newsdata.io](https://newsdata.io) News API. It exposes real-time, historical, crypto, and market news — plus source discovery and aggregate counts — as tools for **Claude Desktop**, **Claude Code**, **Cursor**, **Zed**, **Cline**, **VS Code Copilot**, **Windsurf**, **ChatGPT Desktop**, and any other MCP-compatible AI assistant. Ask questions in natural language; the assistant calls the right tool and returns formatted news.

## Example prompts

```
What's breaking in US politics today? Summarize the top 5 stories.
```
```
Find positive-sentiment crypto news about Bitcoin from the last 24 hours.
```
```
How many articles mentioned "interest rates" each day in January 2025?
```
```
Pull all market news on AAPL and NVDA, then list the headlines with publication dates.
```
```
Which English-language news sources cover both technology and business in the US?
```

The assistant maps these requests to the appropriate tool (`get_latest_news`, `get_crypto_news`, `get_news_counts`, `get_market_news`, `get_news_sources`, etc.) — no manual API calls needed.

---

## Installation

The server is published on PyPI as [`newsdata-mcp`](https://pypi.org/project/newsdata-mcp/). The recommended path is to let your MCP client launch it via [`uvx`](https://docs.astral.sh/uv/guides/tools/) — no clone, no `uv sync`, no virtualenv to manage. The package is downloaded and cached on first launch.

```bash
# verify uvx + the server work end-to-end (optional)
uvx newsdata-mcp --version
```

Then add the server to your MCP client (see [Editor & Client Integrations](#editor--client-integrations) below). Every client config uses the same launch command:

```json
"command": "uvx",
"args": ["newsdata-mcp"]
```

For a local development checkout, see [Development](#development) below.

### Configure environment

Set `NEWSDATA_API_KEY` in your client config's `env` block (per the per-client examples below). Get an API key at [newsdata.io](https://newsdata.io) — the free tier is generous enough to evaluate. When running the server outside an MCP client (development, Docker, `streamable-http`), use a `.env` file:

```bash
cp .env.example .env
# then edit .env
```

| Variable | Default | Notes |
|---|---|---|
| `NEWSDATA_API_KEY` | _(required)_ | Newsdata.io credential. Missing key returns an error envelope on every call. |
| `REQUEST_TIMEOUT` | `30` | Per-request timeout in seconds. |
| `NEWSDATA_BASE_URL` | `https://newsdata.io/api/1` | Override for staging or a local mock. |
| `NEWSDATA_MAX_RETRIES` | `5` | Maximum attempts for transient failures (network, 5xx, 429). |
| `NEWSDATA_RETRY_BACKOFF` | `2.0` | Base for exponential backoff (`base * 2^(attempt-1)`). Seconds. |
| `NEWSDATA_RETRY_BACKOFF_MAX` | `60.0` | Cap on a single retry sleep, seconds. |
| `NEWSDATA_INTEGRATION_KEY` | _(unset)_ | Used only by `pytest -m integration`. Without it, live-API tests skip. |

All values are read at module import time; restart the server after changing them.

---

## Editor & Client Integrations

The simplest way is to add the server to your MCP client's JSON config. Each client picks up the config on restart. All examples use `uvx`, which downloads + caches the published package — no local clone required.

### Claude Code

Either edit `~/.claude/mcp.json` (global) or `.claude/mcp.json` (per-project):

```json
{
  "mcpServers": {
    "newsdata-mcp": {
      "command": "uvx",
      "args": ["newsdata-mcp"],
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
      "command": "uvx",
      "args": ["newsdata-mcp"],
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
NEWSDATA_API_KEY=your_key uvx newsdata-mcp \
  --transport streamable-http --host 127.0.0.1 --port 8000
```

Then in **ChatGPT → Settings → Connectors → Add custom connector**, register `http://127.0.0.1:8000/mcp` as the connector endpoint.

---

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

Full API reference: [https://newsdata.io/documentation](https://newsdata.io/documentation). Machine-readable contract: [OpenAPI 3.1 spec](https://newsdata.io/openapi.json).

---

## Docker

For HTTP-mode deployments (e.g. behind a reverse proxy, or backing the ChatGPT Desktop connector):

```bash
docker build -t newsdata-mcp .
docker run --rm -p 8000:8000 -e NEWSDATA_API_KEY=your_newsdata_api_key newsdata-mcp
```

The image is a multistage build on `python:3.12-slim` and runs as a non-root user — see the [Dockerfile](Dockerfile) for details.

---

## Development

```bash
git clone https://github.com/newsdataapi/newsdata.io-mcp.git
cd newsdata.io-mcp
uv sync --all-groups                                       # install runtime + dev deps

uv run pytest                                              # unit tests only (default)
NEWSDATA_INTEGRATION_KEY=<key> uv run pytest -m integration  # live-API tests
uv run pytest --cov=newsdata_mcp --cov-report=term-missing  # with coverage
uv run ruff check src/ tests/
uv run mypy
```

CI (`.github/workflows/ci.yml`) runs the same four commands on every push/PR to `main`.

### Releasing

1. Bump `__version__` in `src/newsdata_mcp/__init__.py`.
2. Commit and tag: `git tag vX.Y.Z && git push --tags`.
3. `.github/workflows/release.yml` builds the sdist + wheel, publishes to PyPI via Trusted Publishing (no token), and creates a GitHub Release with auto-generated notes.

One-time PyPI setup: configure a Trusted Publisher on the `newsdata-mcp` project pointing at `newsdataapi/newsdata.io-mcp`, workflow `release.yml`, environment `pypi`.

---

## Related libraries

Official Newsdata.io clients for direct REST access (no MCP layer):

| Language / Runtime | Repo |
|---|---|
| Python | [newsdataapi/python-client](https://github.com/newsdataapi/python-client) ([PyPI](https://pypi.org/project/newsdataapi/)) |
| Node.js | [newsdataapi/newsdata-nodejs-client](https://github.com/newsdataapi/newsdata-nodejs-client) ([npm](https://www.npmjs.com/package/newsdata-nodejs-client)) |
| React (hooks) | [newsdataapi/newsdata-reactjs-client](https://github.com/newsdataapi/newsdata-reactjs-client) ([npm](https://www.npmjs.com/package/newsdataapi)) |
| PHP | [newsdataapi/php-client](https://github.com/newsdataapi/php-client) ([Packagist](https://packagist.org/packages/newsdataio/newsdataapi)) |
| Java | [newsdataapi/newsdata-java-sdk](https://github.com/newsdataapi/newsdata-java-sdk) ([Maven Central](https://central.sonatype.com/artifact/io.newsdata/newsdataapi)) |
| .NET | [newsdataapi/newsdata-dotnet-sdk](https://github.com/newsdataapi/newsdata-dotnet-sdk) ([NuGet](https://www.nuget.org/packages/Newsdata.Api/)) |
| Go | [newsdataapi/newsdata-go-client](https://github.com/newsdataapi/newsdata-go-client) ([pkg.go.dev](https://pkg.go.dev/github.com/newsdataapi/newsdata-go-client)) |
| Dart / Flutter | [newsdataapi/newsdata-flutter-client](https://github.com/newsdataapi/newsdata-flutter-client) ([pub.dev](https://pub.dev/packages/newsdataapi)) |

Also see [free news datasets](https://github.com/newsdataapi/newsdata.io-free-datasets) for ML / NLP work.

## License

MIT. See the [LICENSE](LICENSE) file.
