"""Ansible filter plugins: normalize mihomo/clash providers and nodes.

* ``mihomo_proxy_providers`` - normalizes the airport subscription mapping
  (``proxy-providers``): an ``http`` provider without an explicit ``path``
  gets the conventional ``<provider_root>/<name>.yaml`` cache path, and the
  ``selfhost`` file provider is always injected last, matching the profile's
  group contract.
* ``mihomo_selfhost_proxies`` - validates the self-hosted node list against
  the naming contract: every node must carry the self-hosted tag
  (``selfhost|自建`` by default) or it silently disappears from the
  ``*-自建`` groups of the selfhost-tier profile (verified the hard way in
  the mihomo-setup deployment); the plain profile merges the nodes into the
  normal region groups by region token.  Names must be unique and non-empty.
  A ``regions`` list may additionally require a region-regex match
  (catch-all entries with ``catch_all: true`` are skipped: their regex
  matches every node by construction and would turn the check into a no-op);
  it is optional because the region regexes live in the profile templates,
  not in role variables.

The spec for ``mihomo_selfhost_proxies`` is ``proxies`` plus the
``selfhost_pattern`` (and optionally ``regions``) of the profile.
"""

from __future__ import annotations

import re
from typing import Any, NoReturn

from ansible.errors import AnsibleFilterError

DOCUMENTATION = r"""
---
name: mihomo_providers
short_description: Normalize mihomo providers and self-hosted nodes
description:
  - This file provides two filter plugins used by the mihomo client profile.
  - C(mihomo_proxy_providers) normalizes the C(proxy-providers) mapping. It
    adds the conventional cache path to HTTP providers that do not set one,
    and appends the reserved self-hosted file provider last.
  - C(mihomo_selfhost_proxies) validates the self-hosted node list against
    the naming contract used by the profile's region groups. It rejects
    missing or duplicate names, nodes that do not carry the self-hosted tag,
    and nodes that match no configured region regex.
options:
  config:
    description:
      - Filter input mapping.
      - For C(mihomo_proxy_providers), the mapping contains C(providers),
        optional C(provider_root), and optional C(selfhost_provider).
      - For C(mihomo_selfhost_proxies), the mapping contains C(proxies),
        C(selfhost_pattern), and optional C(regions).
    type: dict
    required: true
author:
  - ak1ra
"""

EXAMPLES = r"""
- name: Normalize the subscription providers and append the self-hosted file
  ansible.builtin.set_fact:
    proxy_providers: >-
      {{ {'providers': mihomo_client_proxy_providers,
          'provider_root': '/etc/mihomo/providers',
          'selfhost_provider': 'selfhost'}
         | ak1ra_lab.network.mihomo_proxy_providers }}

- name: Validate the self-hosted nodes before rendering the provider file
  ansible.builtin.set_fact:
    selfhost_provider: >-
      {{ {'proxies': mihomo_client_selfhost_proxies,
          'selfhost_pattern': 'selfhost|自建',
          'regions': profile_regions}
         | ak1ra_lab.network.mihomo_selfhost_proxies }}
"""

RETURN = r"""
_raw:
  description:
    - The normalized provider mapping for C(mihomo_proxy_providers), or a
      mapping with a C(proxies) list for C(mihomo_selfhost_proxies).
  type: dict
  returned: always
"""


def _fail(message: str) -> NoReturn:
    raise AnsibleFilterError(f"mihomo_providers: {message}")


def mihomo_proxy_providers(config: dict[str, Any] | None = None) -> dict[str, Any]:
    """Normalize the ``proxy-providers`` mapping for a mihomo profile.

    Args:
        config: ``{providers: {name: {...}}, provider_root: "./providers",
        selfhost_provider: "selfhost"}``.

    Returns:
        The ordered mapping to render under ``proxy-providers:``.
    """
    if not isinstance(config, dict):
        _fail(f"expected a mapping of provider options, got {type(config).__name__}")
    providers = config.get("providers", {})
    if not isinstance(providers, dict):
        _fail("providers must be a mapping of provider name to configuration")
    root = str(config.get("provider_root", "./providers")).rstrip("/")
    selfhost_provider = str(config.get("selfhost_provider", "selfhost"))

    result: dict[str, Any] = {}
    for name, provider in providers.items():
        if name == selfhost_provider:
            _fail(f"provider name {name!r} is reserved for the self-hosted file provider written by the role")
        if not isinstance(provider, dict):
            _fail(f"providers[{name!r}] must be a mapping")
        merged = dict(provider)
        kind = merged.get("type", "http")
        if kind == "http" and "path" not in merged:
            merged["path"] = f"{root}/{name}.yaml"
        result[name] = merged

    result[selfhost_provider] = {
        "type": "file",
        "path": f"{root}/{selfhost_provider}.yaml",
    }
    return result


def mihomo_selfhost_proxies(config: dict[str, Any] | None = None) -> dict[str, Any]:
    """Validate the self-hosted node list against the naming contract.

    Args:
        config: ``{proxies: [...], selfhost_pattern: str, regions: [...]}``;
            ``regions`` is optional (empty skips the region-regex check).

    Returns:
        ``{"proxies": [...]}`` - the shape of ``providers/selfhost.yaml``.
    """
    if not isinstance(config, dict):
        _fail(f"expected a mapping of node options, got {type(config).__name__}")
    proxies = config.get("proxies", [])
    if not isinstance(proxies, list):
        _fail("proxies must be a list of clash proxy mappings")

    regions = []
    for index, region in enumerate(config.get("regions") or []):
        if not isinstance(region, dict):
            _fail(f"regions[{index}] must be a mapping with emoji/label/regex")
        if region.get("catch_all"):
            # A catch-all entry (所有节点) matches every node by construction;
            # it must not satisfy the region-token requirement below.
            continue
        regex = region.get("regex", "")
        if not isinstance(regex, str) or not regex:
            _fail(f"regions[{index}] requires a non-empty 'regex' string")
        try:
            regions.append(re.compile(regex))
        except re.error as exc:
            _fail(f"regions[{index}] regex failed validation: {exc}")

    pattern_value = config.get("selfhost_pattern", "")
    if not isinstance(pattern_value, str):
        _fail("selfhost_pattern must be a string")
    pattern = pattern_value.strip()
    try:
        selfhost_pattern = re.compile(pattern) if pattern else None
    except re.error as exc:
        _fail(f"selfhost_pattern regex failed validation: {exc}")

    seen: set[str] = set()
    for index, proxy in enumerate(proxies):
        if not isinstance(proxy, dict):
            _fail(f"proxies[{index}] must be a mapping")
        name = proxy.get("name")
        if not isinstance(name, str) or not name:
            _fail(f"proxies[{index}] requires a non-empty 'name'")
        if name in seen:
            _fail(f"proxies[{index}] duplicates node name {name!r}")
        seen.add(name)
        if selfhost_pattern and not selfhost_pattern.search(name):
            _fail(
                f"self-hosted node {name!r} does not match the self-hosted tag "
                f"pattern {pattern!r}; it would be missing from the selfhost-tier "
                f"*-自建 groups"
            )
        if regions and not any(region.search(name) for region in regions):
            _fail(
                f"self-hosted node {name!r} matches no region regex; it would be missing from the selfhost-tier *-自建 region groups"
            )
    return {"proxies": list(proxies)}


class FilterModule:
    """Ansible filter plugin registration for providers and self-hosted nodes."""

    def filters(self) -> dict[str, Any]:
        return {
            "mihomo_proxy_providers": mihomo_proxy_providers,
            "mihomo_selfhost_proxies": mihomo_selfhost_proxies,
        }
