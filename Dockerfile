FROM ghcr.io/typst/typst:0.15.1 AS typst

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    MCP_GATEWAY_CONFIG=/config/servers.json

WORKDIR /app

RUN groupadd --gid 10001 gateway \
    && useradd --uid 10001 --gid gateway --create-home --shell /usr/sbin/nologin gateway

COPY --from=typst /bin/typst /usr/local/bin/typst

COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir .

USER gateway

ENTRYPOINT ["mcp-gateway"]
