"""Strict, secret-free runtime configuration for downstream MCP processes."""

from __future__ import annotations

import json
import os
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class ConfigurationError(ValueError):
    """Raised when gateway configuration is invalid or unsafe."""


_ENV_REFERENCE = re.compile(r"^\$\{([A-Z][A-Z0-9_]*)\}$")
_SERVER_NAME = re.compile(r"^[a-z][a-z0-9_-]{0,62}$")


@dataclass(frozen=True)
class UpstreamConfig:
    """One stdio MCP process launched by the gateway."""

    name: str
    command: str
    args: tuple[str, ...]
    env: Mapping[str, str]
    required: bool

    @classmethod
    def from_mapping(cls, value: object) -> UpstreamConfig:
        if not isinstance(value, dict):
            raise ConfigurationError("Each server entry must be an object")

        name = _required_string(value, "name")
        if not _SERVER_NAME.fullmatch(name):
            raise ConfigurationError("Server names must use lowercase letters, digits, '_' or '-'")

        command = _required_string(value, "command")
        raw_args = value.get("args", [])
        if not isinstance(raw_args, list) or not all(isinstance(item, str) for item in raw_args):
            raise ConfigurationError(f"{name}.args must be an array of strings")

        raw_env = value.get("env", {})
        if not isinstance(raw_env, dict) or not all(
            isinstance(key, str) and isinstance(item, str) for key, item in raw_env.items()
        ):
            raise ConfigurationError(f"{name}.env must be an object of string values")
        for variable, reference in raw_env.items():
            if not _ENV_REFERENCE.fullmatch(reference):
                raise ConfigurationError(
                    f"{name}.env.{variable} must reference an environment variable "
                    f"such as ${{{variable}}}"
                )

        required = value.get("required", True)
        if not isinstance(required, bool):
            raise ConfigurationError(f"{name}.required must be true or false")

        return cls(
            name=name,
            command=command,
            args=tuple(raw_args),
            env=dict(raw_env),
            required=required,
        )

    def resolved_environment(self, source: Mapping[str, str] | None = None) -> dict[str, str]:
        """Resolve only declared variable references without logging their values."""
        available = os.environ if source is None else source
        resolved = dict(os.environ)
        for variable, reference in self.env.items():
            match = _ENV_REFERENCE.fullmatch(reference)
            assert match is not None
            source_name = match.group(1)
            secret = available.get(source_name)
            if secret is None:
                raise ConfigurationError(f"{self.name} requires environment variable {source_name}")
            resolved[variable] = secret
        return resolved


def load_config(path: Path) -> tuple[UpstreamConfig, ...]:
    """Load a JSON configuration that can contain references but never secret values."""
    try:
        payload: Any = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise ConfigurationError(f"Gateway configuration does not exist: {path}") from error
    except json.JSONDecodeError as error:
        raise ConfigurationError(f"Gateway configuration is not valid JSON: {error.msg}") from error

    if not isinstance(payload, dict) or set(payload) != {"servers"}:
        raise ConfigurationError("Configuration must contain only a 'servers' property")
    raw_servers = payload["servers"]
    if not isinstance(raw_servers, list) or not raw_servers:
        raise ConfigurationError("Configuration must contain at least one server")

    servers = tuple(UpstreamConfig.from_mapping(item) for item in raw_servers)
    names = [server.name for server in servers]
    if len(names) != len(set(names)):
        raise ConfigurationError("Server names must be unique")
    return servers


def _required_string(value: Mapping[str, object], key: str) -> str:
    item = value.get(key)
    if not isinstance(item, str) or not item.strip():
        raise ConfigurationError(f"{key} must be a non-empty string")
    return item
