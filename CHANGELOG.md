# Changelog

All notable changes to this project are documented here.

## 0.1.0 — 2026-10-05

### Added

- A Python 3.12 MCP gateway that starts configured stdio MCP child processes,
  initializes them before reporting readiness, and exposes a single MCP stdio
  endpoint for Hermes.
- Namespaced downstream tool names (`<server>__<tool>`) so finance, calendar,
  mail, and document-generation tools cannot collide when aggregated.
- Exact downstream tool schemas, descriptions, and call results are forwarded;
  the gateway does not reinterpret tool arguments or business data.
- A strict JSON configuration format that permits only `${ENVIRONMENT_VARIABLE}`
  references for upstream environment entries, preventing credentials from being
  embedded in versioned configuration.
- Required/optional upstream behavior: required failures stop startup; optional
  failures are excluded without exposing partial tool definitions.
- A non-root Docker image and Compose example for stdio use by Hermes, with
  reviewed adapter/config bind mounts and no Docker socket access.
- Security-oriented operational documentation, example configuration, runtime
  environment template, and tests for secret-reference validation and duplicate
  upstream detection.
