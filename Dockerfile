# Multistage build: resolve and install with uv against the lockfile in
# the builder, then copy the resulting venv into a minimal runtime stage.

# ---------- Builder ----------
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

# uv is a small Rust binary; pip-install it once in the builder.
RUN pip install --no-cache-dir uv

WORKDIR /app

# Install dependencies first (without the project itself) so this layer
# stays cached when only application source changes. LICENSE is needed
# at build time because pyproject.toml declares `license = { file = ... }`.
COPY pyproject.toml uv.lock README.md LICENSE /app/
RUN uv sync --frozen --no-install-project --no-dev

# Now copy source and install the project itself into the same venv.
COPY src /app/src
RUN uv sync --frozen --no-dev

# ---------- Runtime ----------
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    REQUEST_TIMEOUT=30 \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# Copy the populated venv + project source from the builder. LICENSE
# is already inside /app from the builder stage.
COPY --from=builder /app /app

# Run as a non-root user.
RUN useradd --create-home --uid 1000 app \
    && chown -R app:app /app
USER app

EXPOSE 8000

# TCP-level liveness probe; only meaningful for streamable-http transport.
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s \
    CMD python -c "import socket; s=socket.socket(); s.settimeout(2); s.connect(('localhost',8000)); s.close()" || exit 1

LABEL org.opencontainers.image.title="newsdata-mcp" \
      org.opencontainers.image.description="MCP server for NewsData.io" \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.source="https://github.com/newsdataapi/newsdata.io-mcp"

ENTRYPOINT ["newsdata-mcp"]
CMD ["--transport", "streamable-http", "--host", "0.0.0.0", "--port", "8000"]
