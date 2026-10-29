# Copyright: (c) 2026, ak1ra <ak1ra.komj@gmail.com>
# GNU General Public License v3.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Shared pytest configuration for the collection unit tests.

The filter plugins are plain Python modules; plain pytest imports them
directly, so this file puts ``plugins/filter/`` on ``sys.path``.  Running the
tests requires ``ansible-core`` (for ``ansible.errors``) and ``pytest``.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
FILTER_ROOT = REPO_ROOT / "plugins" / "filter"

if str(FILTER_ROOT) not in sys.path:
    sys.path.insert(0, str(FILTER_ROOT))


def _role_defaults(role: str) -> dict[str, Any]:
    path = REPO_ROOT / "roles" / role / "defaults" / "main.yaml"
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


@pytest.fixture(scope="session")
def mihomo_client_defaults() -> dict[str, Any]:
    """The shipped ak1ra_lab.network.mihomo_client defaults."""
    return _role_defaults("mihomo_client")
