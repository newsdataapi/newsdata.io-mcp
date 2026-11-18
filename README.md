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

The official MCP server for the [Newsdata.io](https://newsdata.io) News API. It exposes real-time, historical, crypto, and market news — plus source discovery and aggregate counts — as tools for **Claude Desktop**, **Claude Code**, **Cursor**, **Zed**, **Cline**, **VS Code Copilot**, **Windsurf**, **ChatGPT**, and any other MCP-compatible AI assistant. Ask questions in natural language; the assistant calls the right tool and returns formatted news.

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
```
Watch for new articles about earthquakes for the next minute and tell me what comes in.
```

The assistant maps these requests to the appropriate tool (`get_news`, `get_crypto_news`, `get_news_counts`, `get_market_news`, `get_news_sources`, `register_realtime_query` + `stream_news`, etc.) — no manual API calls needed.

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
| `NEWSDATA_BASE_URL` | `https://newsdata.io/api/2` | Override for staging or a local mock. Keep the version segment at the end. |
| `NEWSDATA_MAX_RETRIES` | `5` | Maximum attempts for transient failures (network, 5xx, 429). |
| `NEWSDATA_RETRY_BACKOFF` | `2.0` | Base for exponential backoff (`base * 2^(attempt-1)`). Seconds. |
| `NEWSDATA_RETRY_BACKOFF_MAX` | `60.0` | Cap on a single retry sleep, seconds. When the API asks for a longer wait (`Retry-After`), the error is returned at once instead of waiting. |
| `NEWSDATA_WS_API_URL` | `https://newsdata.io/api/1` | API root of the real-time registration endpoints (`register_realtime_query`, `list_realtime_queries`, `delete_realtime_query`). |
| `NEWSDATA_WS_URL` | `wss://ws.newsdata.io/ws/event` | Real-time endpoint used by `stream_news`. |
| `NEWSDATA_WS_MAX_WAIT` | `120` | Ceiling on `stream_news`'s `wait_seconds`, in seconds. |
| `NEWSDATA_INTEGRATION_KEY` | _(unset)_ | Used only by `pytest -m integration`. Without it, live-API tests skip. |

All values are read at module import time; restart the server after changing them.

---

## Editor & Client Integrations

The simplest way is to add the server to your MCP client's JSON config. Each client picks up the config on restart. All examples use `uvx`, which downloads + caches the published package — no local clone required.

### Claude Code

Add the server with the `claude` CLI. `--scope user` makes it available in all your projects; leave it out to add it to the current project only:

```bash
claude mcp add --env NEWSDATA_API_KEY=your_newsdata_api_key --transport stdio --scope user newsdata-mcp -- uvx newsdata-mcp
```

Or put this block in `.mcp.json` at the project root. That file is meant to be shared with the project, so don't commit a real key in it:

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

### ChatGPT

Run the server in HTTP mode locally:

```bash
NEWSDATA_API_KEY=your_key uvx newsdata-mcp \
  --transport streamable-http --host 127.0.0.1 --port 8000
```

A server on your own machine is not public, so connect it through OpenAI's [Secure MCP Tunnel](https://developers.openai.com/api/docs/guides/secure-mcp-tunnels), pointing `tunnel-client` at `http://127.0.0.1:8000/mcp`. Then, in ChatGPT on the web, open **Plugins**, select **+ → Add custom MCP server**, choose **Tunnel** under **Connection**, and select **No authentication**.

---

## Available Tools

| Tool | Endpoint | Description |
|---|---|---|
| `get_news` | `/api/2/news` | News articles: the last 30 days by default, or any date range in the plan's history |
| `get_crypto_news` | `/api/2/crypto` | Cryptocurrency news, filterable by `coin` |
| `get_market_news` | `/api/2/market` | Stock-market and financial news, filterable by `market_id` |
| `get_news_sources` | `/api/2/sources` | Up to 100 news sources by country, category, language, URL or rank |
| `get_news_counts` | `/api/2/count/news` | How many news articles match: a total plus counts per `month` / `day` / `hour` |
| `get_crypto_counts` | `/api/2/count/crypto` | The same for crypto news |
| `get_market_counts` | `/api/2/count/market` | The same for market news |
| `register_realtime_query` | `/api/1/websocket/register` | Register a standing real-time query, returns a `registration_id` |
| `list_realtime_queries` | `/api/1/websocket/fetch` | List the account's registered real-time queries |
| `delete_realtime_query` | `/api/1/websocket/delete` | Delete a registered real-time query |
| `stream_news` | `wss://ws.newsdata.io/ws/event` | Collect real-time articles for a registered query ([below](#real-time-news-websocket)) |

The seven news, source and count tools are read-only and idempotent. `register_realtime_query` and `delete_realtime_query` are annotated as mutating (the latter destructive), since they create and remove server-side state.

---

## Real-time news (WebSocket)

Real time is a **two-step flow**: register a standing query once, then collect
from it as often as you like.

```text
register_realtime_query(
  q="bitcoin",
  language="en"
)
→ registration_id: 9b2d1e8a7c4f4b6e9d3a5c7e1f2a4b6c
```

```text
stream_news(
  registration_id="9b2d1e8a7c4f4b6e9d3a5c7e1f2a4b6c",
  max_articles=10,
  wait_seconds=30
)
```

`register_realtime_query` takes the familiar filter parameters (`q`, `country`,
`language`, `category`, …) and needs at least one of them. There are **no date
or paging filters** — a registered query matches news as it is published.
Registering identical filters twice answers `Error (HTTP 409, Conflict)` with
the existing `registration_id`; `list_realtime_queries` shows every registration.

A few of its parameters are named differently from the news tools: `domain`
(source ids such as `bbc`), `domainurl` and `exclude_domain` (website addresses
such as `bbc.com`), `priority_domain`, `full_content`, `removeduplicate` and
`excludefield`.

Streamed articles come **without their full text** by default. Pass
`content=true` to `stream_news` to include it.

### Why `stream_news` is bounded

MCP tools are request/response, so an open-ended stream cannot be a tool.
`stream_news` listens on a live connection and returns as soon as **either**
`max_articles` have arrived **or** `wait_seconds` elapses — whichever comes
first. It always returns within `wait_seconds`.

Every reply states why it stopped, so the model can act on it:

| `stopped_because` | Meaning |
|---|---|
| `max_articles` | Hit the cap — there may be more waiting |
| `timeout` | The window elapsed; a `0` count means the feed was simply quiet |
| `connection_closed` | The server ended the feed; returns whatever was collected |
| `error` | The service ended the stream (for example, credits ran out); the articles that arrived are returned with the reason |

Call it again to keep listening — the registration stays alive between calls.
Only articles published **while a call is listening** are delivered; use
`get_news` for past news. An empty result is normal for a narrow query and does
**not** mean anything failed.

Bounds: `max_articles` is clamped to 1–50, `wait_seconds` to 1–`NEWSDATA_WS_MAX_WAIT`
(120 by default).

A refused connection (bad key, unknown `registration_id`, no credits left, more
than 5 devices on one `registration_id`) returns an `Error` with the service's
message and is not retried.

> **Cost.** Each delivered article consumes **1 API credit per connected
> device**. Articles arrive in batches and every article of a batch is charged,
> so keep the query narrow.

---

## Example Tool Calls

```text
get_news(
  q="(pizza OR burger) AND healthy",
  country=["us", "gb"],
  language="en"
)
```

```text
get_news(
  q="ukraine war",
  from_date="2026-06-01",
  to_date="2026-06-30",
  sort="relevancy"
)
```

```text
get_news(
  category="business",
  source_priority="top",
  timeframe=24
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
  market_id=["aapl-us-vy", "msft-us-vy"],
  language="en"
)
```

```text
get_news_sources(
  country="in",
  language="en",
  source_priority="top"
)
```

```text
get_news_counts(
  q="bitcoin",
  from_date="2026-01-01",
  to_date="2026-09-30",
  interval="month"
)
```

```text
get_news(
  q="elections",
  sentiment="positive",
  sentiment_score=70
)
```

Notes on parameter shapes:
- Multi-value filters accept a comma-separated string (`"us,gb"`) or a list (`["us", "gb"]`).
- Flags (`image`, `video`, `content`, `remove_duplicate`) accept `true`/`false` or `1`/`0`.
- `timeframe` accepts a number of hours (`24`, up to `720`) or minutes with an `m` suffix (`"90m"`, up to `"43200m"`). It cannot be combined with `from_date` / `to_date`.
- `from_date` / `to_date` are UTC, as `YYYY-MM-DD` or `YYYY-MM-DD HH:MM:SS`.
- `interval` (count tools only) accepts `month`, `day` (default) or `hour`.
- `sentiment_score` is a minimum confidence from 1 to 100 and requires `sentiment` — e.g. `sentiment="positive", sentiment_score=70`.
- `market_id` is a listing id such as `aapl-us-vy`, not a bare ticker. Pass a ticker or a company name and the error lists the matching ids.
- `page` takes the `next_page` value of the previous result; repeat every other argument unchanged.

---

## Notes

- Without `from_date`, `to_date` or `timeframe`, the article and count tools cover the last 30 days.
- The article tools return 10 articles per call unless `size` is passed (up to 50 on paid plans), without the full article text. Fetch an article by `id` or `url`, or pass `content=true`, to get the full text (paid plans).
- Credits: `get_news`, `get_crypto_news` and `get_market_news` cost 1 credit per call, or 5 on paid plans when the date range starts more than 30 days ago. `get_news_sources` costs 1. Each count call costs 50.
- Plans: the Free plan has a 12-hour delay, at most 10 articles per call, no full text or AI summary, no `timeframe` and no count tools. `region` and `organization` need the Corporate plan. A field the plan does not include is named in a `not_in_your_plan:` line at the top of the result.
- `get_news_sources` returns at most 100 sources, best-ranked first, with no paging.
- Real-time coverage needs a plan with WebSocket access. Real-time articles are billed per delivered article, per connected device.
- Every tool returns plain text. Errors come back as `Error (HTTP 422, UnsupportedFilter): …` with the API's own message and, when the API suggests them, the valid values close to the rejected one.

Full API reference: [https://newsdata.io/documentation](https://newsdata.io/documentation). Machine-readable contract: [OpenAPI 3.1 spec](https://newsdata.io/openapi.json).

---

## Docker

For HTTP-mode deployments:

```bash
docker build -t newsdata-mcp .
docker run --rm -p 8000:8000 -e NEWSDATA_API_KEY=your_newsdata_api_key newsdata-mcp
```

Clients must address the server as `localhost` or `127.0.0.1`, for example `http://localhost:8000/mcp` through the port mapping above, or through a proxy that sends that host name. Requests for any other host name are refused with HTTP 421.

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
