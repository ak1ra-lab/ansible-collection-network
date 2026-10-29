# Copyright: (c) 2026, ak1ra <ak1ra.komj@gmail.com>
# GNU General Public License v3.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Shared pytest configuration for the collection unit tests.

Tests import the filter plugins through the installed collection namespace
(``ansible_collections.ak1ra_lab.network.plugins.filter...``). Run them with
``ansible-test units`` (the tox-ansible ``unit-*`` environments), which puts
the collection on the import path; do not add a ``sys.path`` shim here.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]


def _role_defaults(role: str) -> dict[str, Any]:
    path = REPO_ROOT / "roles" / role / "defaults" / "main.yaml"
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


@pytest.fixture(scope="session")
def mihomo_client_defaults() -> dict[str, Any]:
    """The shipped ak1ra_lab.network.mihomo_client defaults."""
    return _role_defaults("mihomo_client")
