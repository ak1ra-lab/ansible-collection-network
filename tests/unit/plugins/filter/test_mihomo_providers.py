"""Unit tests for plugins/filter/mihomo_providers.py.

Coverage follows the mihomo-setup incident and provider contracts:

* the proxy-provider normalization (derived cache paths, reserved
  `selfhost` name, always-injected file provider),
* the self-hosted node naming contract (selfhost tag, unique names, and the
  optional region-regex check), so nodes that would silently vanish from
  the selfhost-tier profile's `*-自建` groups fail the play.
"""

from __future__ import annotations

from typing import Any

import pytest
from ansible.errors import AnsibleFilterError
from mihomo_providers import mihomo_proxy_providers, mihomo_selfhost_proxies

PATTERN = "selfhost|自建"
REGIONS = [
    {"emoji": "🇺🇸", "label": "美国节点", "regex": "(?i:\\bUS[A]?\\d*\\b|美国)"},
    {"emoji": "🚀", "label": "所有节点", "regex": ".+", "catch_all": True},
]

# ── proxy providers ──────────────────────────────────────────────────────────


def test_proxy_providers_derive_path_and_inject_selfhost() -> None:
    result = mihomo_proxy_providers(
        {
            "providers": {
                "airport-a": {
                    "type": "http",
                    "url": "https://sub.example/x",
                    "proxy": "DIRECT",
                },
                "airport-b": {
                    "type": "http",
                    "url": "https://sub.example/y",
                    "path": "./custom.yaml",
                },
            }
        }
    )
    assert list(result) == ["airport-a", "airport-b", "selfhost"]
    assert result["airport-a"]["path"] == "./providers/airport-a.yaml"
    assert result["airport-b"]["path"] == "./custom.yaml"
    assert result["selfhost"] == {"type": "file", "path": "./providers/selfhost.yaml"}


def test_proxy_providers_reserved_name_fails() -> None:
    with pytest.raises(AnsibleFilterError, match="reserved"):
        mihomo_proxy_providers({"providers": {"selfhost": {"type": "http", "url": "x"}}})


def test_proxy_providers_must_be_mappings() -> None:
    with pytest.raises(AnsibleFilterError, match="must be a mapping"):
        mihomo_proxy_providers({"providers": {"airport-a": "https://sub.example/x"}})


# ── self-hosted naming contract ──────────────────────────────────────────────


def validate(nodes: list[dict[str, Any]], **overrides: Any) -> dict[str, Any]:
    return mihomo_selfhost_proxies({"proxies": nodes, "selfhost_pattern": PATTERN, "regions": REGIONS, **overrides})


def test_selfhost_nodes_accept_the_naming_contract() -> None:
    nodes = [
        {"name": "selfhost-US-node01-ss", "type": "ss"},
        {"name": "自建-US-hk01-trojan", "type": "trojan"},
    ]
    assert validate(nodes) == {"proxies": nodes}


def test_selfhost_node_without_tag_fails() -> None:
    with pytest.raises(AnsibleFilterError, match="self-hosted tag"):
        validate([{"name": "node01-ss"}])


def test_selfhost_node_without_region_fails() -> None:
    # The catch_all region matches every node by construction; the check must
    # skip it, otherwise this node would pass silently.
    with pytest.raises(AnsibleFilterError, match="matches no region regex"):
        validate([{"name": "selfhost-node01-ss"}])


def test_selfhost_region_check_is_optional() -> None:
    # The client role passes no region table (the region regexes live in the
    # profile template), so the contract must hold with the tag alone.
    nodes = [{"name": "selfhost-node01-ss", "type": "ss"}]
    assert mihomo_selfhost_proxies({"proxies": nodes, "selfhost_pattern": PATTERN}) == {"proxies": nodes}


def test_selfhost_duplicate_name_fails() -> None:
    node = {"name": "selfhost-US-node01-ss", "type": "ss"}
    with pytest.raises(AnsibleFilterError, match="duplicates"):
        validate([node, node])


def test_selfhost_node_without_name_fails() -> None:
    with pytest.raises(AnsibleFilterError, match="non-empty 'name'"):
        validate([{"type": "ss"}])


def test_selfhost_nodes_may_be_empty() -> None:
    assert validate([]) == {"proxies": []}
