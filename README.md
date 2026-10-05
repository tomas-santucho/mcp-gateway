# MCP Gateway

`mcp-gateway` exposes one MCP stdio server that aggregates tools from multiple
reviewed stdio MCP servers. It is designed for Hermes, which can then connect
to a single gateway rather than manage each child process itself.

The gateway currently supports the local Firefly III, Nextcloud Calendar, IMAP
mail, and Typst adapters through the provided example configuration. It does
not contain service URLs, credentials, tokens, passwords, or business data.

## Design

- Upstreams are started as stdio child processes at gateway startup.
- Gateway tools are namespaced as `<server>__<tool>` to prevent collisions;
  for example `firefly__get_accounts` and `calendar__create_event`.
- Tool descriptions, JSON schemas, and tool-call results are passed through.
- A required upstream that cannot initialize prevents a partially working
  gateway from becoming available. Optional upstreams may be omitted with
  `"required": false`.
- Each upstream environment entry must be a reference such as
  `${FIREFLY_TOKEN}`. Literal values are rejected by configuration validation.

The gateway does not authorize or alter downstream calls. Only enable adapters
and tools that Hermes is permitted to use; retain explicit user confirmation
for any calendar write or document-sharing operation.

## Configuration

Copy `config/servers.example.json` outside this repository, update only the
adapter paths and the required server list, then mount it as
`/config/servers.json`. The example deliberately contains variable references,
not values.

Pass actual values only at runtime, for example with an uncommitted
`--env-file`. Keep that file mode `0600` and do not use a shell command that
prints it. The configuration schema is intentionally small:

```json
{
  "servers": [
    {
      "name": "example",
      "command": "python",
      "args": ["/opt/adapters/example/server.py"],
      "env": { "EXAMPLE_TOKEN": "${EXAMPLE_TOKEN}" },
      "required": true
    }
  ]
}
```

## Local development

Requires Python 3.12 or newer.

```bash
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
ruff check .
ruff format --check .
pytest
mypy src
```

To run locally, point `MCP_GATEWAY_CONFIG` to your non-secret configuration and
make its referenced environment variables available in the process:

```bash
MCP_GATEWAY_CONFIG=/secure/path/servers.json mcp-gateway
```

The process speaks MCP over stdin/stdout. Logs go to stderr so it is safe for
stdio clients.

## Docker and Hermes

The `dev` branch workflow publishes multi architecture images to
`ghcr.io/tomas-santucho/mcp-gateway` with `dev` and commit SHA tags. For a local
build on the server:

```bash
docker build --tag mcp-gateway:0.1.1 .
```

The image runs non-root and includes only the runtime libraries needed by the
reviewed Python adapters. It contains no adapter source, configuration, or
secrets. Mount adapters read-only, mount a non-secret configuration file, and
mount only the Typst template/output directories needed by the renderer. Do not
mount the Docker socket.

Example Hermes entry (replace paths with your deployment paths):

```yaml
mcp_servers:
  local_gateway:
    command: docker
    args:
      - run
      - --rm
      - -i
      - --init
      - --env-file
      - /secure/path/gateway.env
      - -v
      - /secure/path/adapters:/opt/adapters:ro
      - -v
      - /secure/path/servers.json:/config/servers.json:ro
      - -v
      - /secure/path/pdf-templates:/home/gateway/hermes/pdf-templates:ro
      - -v
      - /secure/path/generated-pdfs:/home/gateway/hermes/generated-pdfs
      - -e
      - HERMES_HOME=/home/gateway/hermes
      - -e
      - TYPST_BIN=/usr/local/bin/typst
      - ghcr.io/tomas-santucho/mcp-gateway:dev
    timeout: 180
    connect_timeout: 20
```

The adapter configuration must use the matching container paths, such as
`/opt/adapters/firefly-mcp/server.py`. When the original adapters are updated,
review their dependencies, rebuild the gateway image, then validate the gateway
before enabling it for Hermes:

```bash
hermes mcp test local_gateway
```

## Security and operations

- Never commit `.env`, production `servers.json`, generated PDFs, or adapter
  credentials. The supplied `.gitignore` excludes standard secret files.
- Keep runtime env files and Hermes configuration at mode `0600`.
- Run `hermes mcp test local_gateway` after every image, adapter, or
  configuration change. It validates MCP initialization and tool discovery
  without invoking a business tool.
- A compromised credential must be revoked at its provider, replaced in the
  secure runtime env file, and followed by a gateway restart.
- See [CHANGELOG.md](CHANGELOG.md) for release-level changes.
