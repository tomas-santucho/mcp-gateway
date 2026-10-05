from __future__ import annotations

import json
from pathlib import Path

import pytest

from mcp_gateway.config import ConfigurationError, UpstreamConfig, load_config


def test_resolved_environment_reads_references_without_embedding_values() -> None:
    config = UpstreamConfig.from_mapping(
        {
            "name": "mail",
            "command": "python",
            "env": {"MAIL_PASSWORD": "${RUNTIME_PASSWORD}"},
        }
    )

    resolved = config.resolved_environment({"RUNTIME_PASSWORD": "only-at-runtime"})

    assert resolved["MAIL_PASSWORD"] == "only-at-runtime"


def test_resolved_environment_does_not_forward_unlisted_secrets() -> None:
    config = UpstreamConfig.from_mapping({"name": "mail", "command": "python"})

    resolved = config.resolved_environment(
        {"PATH": "/usr/bin", "UNRELATED_SECRET": "must-not-leak"}
    )

    assert resolved["PATH"] == "/usr/bin"
    assert "UNRELATED_SECRET" not in resolved


def test_rejects_literal_secret_values() -> None:
    with pytest.raises(ConfigurationError, match="must reference an environment variable"):
        UpstreamConfig.from_mapping(
            {"name": "mail", "command": "python", "env": {"MAIL_PASSWORD": "do-not-store-me"}}
        )


def test_load_config_rejects_duplicate_names(tmp_path: Path) -> None:
    path = tmp_path / "servers.json"
    path.write_text(
        json.dumps(
            {
                "servers": [
                    {"name": "mail", "command": "python"},
                    {"name": "mail", "command": "python"},
                ]
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ConfigurationError, match="unique"):
        load_config(path)
