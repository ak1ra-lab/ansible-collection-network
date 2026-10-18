"""Shared pytest configuration for the collection unit tests.

The filter and lookup plugins are plain Python modules; plain pytest imports
them directly (ansible-test is not set up in this repository), so this file
puts ``plugins/filter/`` and ``plugins/lookup/`` on ``sys.path``.  Running
the tests requires ``ansible-core`` (for ``ansible.errors``) and ``pytest``.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
PLUGIN_ROOTS = (REPO_ROOT / "plugins" / "filter", REPO_ROOT / "plugins" / "lookup")

for plugin_root in PLUGIN_ROOTS:
    if str(plugin_root) not in sys.path:
        sys.path.insert(0, str(plugin_root))


def _role_defaults(role: str) -> dict[str, Any]:
    path = REPO_ROOT / "roles" / role / "defaults" / "main.yaml"
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


@pytest.fixture(scope="session")
def mihomo_client_defaults() -> dict[str, Any]:
    """The shipped ak1ra_lab.network.mihomo_client defaults."""
    return _role_defaults("mihomo_client")
