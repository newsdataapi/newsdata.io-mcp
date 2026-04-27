# NewsData MCP Server

An MCP server for [NewsData.io](https://newsdata.io/documentation) that exposes real-time and historical news tools to any MCP-compatible client.

## Available Tools

| Tool | Endpoint | Description |
|---|---|---|
| `get_latest_news` | `/api/1/latest` | Recent and breaking news (last 48h) |
| `get_archive_news` | `/api/1/archive` | Historical news with `from_date`/`to_date` |
| `get_crypto_news` | `/api/1/crypto` | Crypto and blockchain-focused coverage |
| `get_market_news` | `/api/1/market` | Stock, financial, and market-related news |
| `get_news_sources` | `/api/1/sources` | Source discovery by country, category, or language |

---

## Installation

### Clone the Repository

```bash
git clone https://github.com/newsdataapi/newsdata.io-mcp.git
cd newsdata.io-mcp
uv sync
```

### Configure Environment

Create a `.env` file in the project root:

```env
NEWSDATA_API_KEY=your_newsdata_api_key
REQUEST_TIMEOUT=30
```

- `NEWSDATA_API_KEY` — **Required.**
- `REQUEST_TIMEOUT` — Optional. Defaults to `30` seconds.

---

## Running the Server

### stdio transport (for desktop/CLI clients)

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

---

## Docker

Build the image:

```bash
docker build -t newsdata-mcp .
```

Run in streamable HTTP mode:

```bash
docker run --rm -p 8000:8000 \
  -e NEWSDATA_API_KEY=your_newsdata_api_key \
  newsdata-mcp
```

Run in stdio mode:

```bash
docker run --rm -i \
  -e NEWSDATA_API_KEY=your_newsdata_api_key \
  newsdata-mcp --transport stdio
```

Pass a `.env` file or override specific values:

```bash
docker run --rm -p 8000:8000 \
  --env-file .env \
  -e REQUEST_TIMEOUT=45 \
  newsdata-mcp
```

> The Docker image pre-sets `REQUEST_TIMEOUT=30` and installs dependencies from `pyproject.toml` via `pip install .`.

---

## Editor & Client Integrations

### Claude Code

Add the server using the CLI:

```bash
claude mcp add newsdata-mcp -- uv --directory /path/to/newsdata.io-mcp run newsdata-mcp --transport stdio
```

Or add it manually to your Claude Code MCP config file (`~/.claude/mcp.json` globally, or `.claude/mcp.json` per project):

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

Restart Claude Code, then ask it to use the NewsData tools directly in chat.

---

### Claude Desktop

Edit `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or `%APPDATA%\Claude\claude_desktop_config.json` (Windows):

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

Restart Claude Desktop. The NewsData tools will appear in the tools menu.

---

### Cursor

Create or edit `.cursor/mcp.json` in your project root (or `~/.cursor/mcp.json` globally):

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

Restart Cursor. The server will appear under **Cursor Settings → MCP**.

---

### VS Code (GitHub Copilot)

Create `.vscode/mcp.json` in your workspace (or add to User Settings as `mcp` key):

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

Reload VS Code. The server will be picked up by GitHub Copilot Chat when agent mode is active (`@workspace` or Copilot Edits).

---

### Windsurf

Edit `~/.codeium/windsurf/mcp_config.json`:

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

Restart Windsurf. The tools will be available to Cascade in agentic mode.

---

### ChatGPT Desktop (OpenAI)

Open **ChatGPT → Settings → Connectors → Add custom connector** and supply the server URL (requires HTTP transport):

```bash
uv run newsdata-mcp --transport streamable-http --host 127.0.0.1 --port 8000
```

Then register `http://127.0.0.1:8000/mcp` as the connector endpoint in the ChatGPT desktop app settings.

---

## Example Tool Calls

```text
get_latest_news(
  q="((pizza OR burger) AND healthy)",
  country="us",
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
  coin="btc,eth",
  sentiment="positive"
)
```

```text
get_market_news(
  symbol="AAPL,NVDA",
  country="us"
)
```

```text
get_news_sources(
  language="en",
  priority_domain="top"
)
```

---

## Notes

- Latest, crypto, and market endpoints return recent coverage — typically up to 48 hours.
- Free plan results are delayed relative to paid plans.
- Result size is capped by plan tier: commonly 10 results on free, up to 50 on paid plans.

Full API reference: [https://newsdata.io/documentation](https://newsdata.io/documentation)