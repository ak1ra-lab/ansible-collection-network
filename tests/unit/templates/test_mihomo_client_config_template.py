"""Unit tests for the mihomo_client profile template.

The profile is a hand-maintained template
(roles/mihomo_client/templates/etc/mihomo/config.yaml.j2): static mihomo
YAML plus a handful of rendered values.  These tests render it with the
shipped defaults (and payload fixtures) and assert the structure an operator
observes - the tier topology, the conditional inline custom rule sets, the
rule order, the DNS policy and the provider injection.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import jinja2
import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
TEMPLATE_PATH = REPO_ROOT / "roles" / "mihomo_client" / "templates" / "etc" / "mihomo" / "config.yaml.j2"

sys.path.insert(0, str(REPO_ROOT / "plugins" / "filter"))

from mihomo_providers import mihomo_proxy_providers
from pretty_yaml import to_pretty_yaml


def _bool(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() not in ("", "false", "no", "off", "0")
    return bool(value)


def _to_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def render_profile(variables: dict[str, Any]) -> dict[str, Any]:
    """Render the shipped profile template and parse it as YAML."""
    text = TEMPLATE_PATH.read_text(encoding="utf-8")
    options: dict[str, bool] = {}
    if text.startswith("#jinja2:"):
        header, text = text.split("\n", 1)
        for part in header.removeprefix("#jinja2:").split(","):
            key, _, value = part.partition(":")
            options[key.strip()] = value.strip().lower() == "true"
    environment = jinja2.Environment(
        undefined=jinja2.StrictUndefined,
        trim_blocks=options.get("trim_blocks", False),
        lstrip_blocks=options.get("lstrip_blocks", False),
    )
    environment.filters.update(
        {
            "ansible.builtin.bool": _bool,
            "ansible.builtin.to_json": _to_json,
            "ak1ra_lab.network.to_pretty_yaml": to_pretty_yaml,
            "ak1ra_lab.network.mihomo_proxy_providers": mihomo_proxy_providers,
        }
    )
    rendered = environment.from_string(text).render(**variables)
    return yaml.safe_load(rendered)


def profile_vars(defaults: dict[str, Any], **overrides: Any) -> dict[str, Any]:
    variables = {key: value for key, value in defaults.items() if key.startswith("mihomo_client_")}
    variables["mihomo_client_proxy_providers"] = {
        "airport-a": {"type": "http", "url": "https://sub.example/x", "proxy": "DIRECT"}
    }
    variables.update(overrides)
    return variables


# ── topology, providers, rules ───────────────────────────────────────────────


def test_default_profile_structure(mihomo_client_defaults: dict[str, Any]) -> None:
    profile = render_profile(profile_vars(mihomo_client_defaults))

    groups = profile["proxy-groups"]
    assert len(groups) == 31
    assert groups[0]["name"] == "PROXY"
    assert groups[0]["default-selected"] == "🚀 所有节点"
    assert groups[0]["proxies"][0] == "🇸🇬 新加坡节点 - 自建"
    assert groups[0]["proxies"][-1] == "DIRECT"
    assert [group["name"] for group in groups[1:7]] == [
        "FINAL",
        "AI",
        "Steam",
        "Telegram",
        "Entertainment",
        "SSH",
    ]
    assert groups[1]["proxies"][:2] == ["PROXY", "DIRECT"]
    # FINAL and the four application groups list the same members.
    assert all(groups[index]["proxies"] == groups[1]["proxies"] for index in range(2, 6))
    assert "TELEGRAM" not in [group["name"] for group in groups]

    assert list(profile["proxy-providers"]) == ["airport-a", "selfhost"]
    assert profile["proxy-providers"]["airport-a"]["path"] == "./providers/airport-a.yaml"
    assert profile["proxy-providers"]["selfhost"] == {"type": "file", "path": "./providers/selfhost.yaml"}

    providers = profile["rule-providers"]
    assert len(providers) == 13
    assert not [name for name in providers if name.startswith("custom-")]
    assert providers["geosite-steam@cn"]["path-in-bundle"] == "geo/geosite/steam@cn.mrs"

    assert list(profile["dns"]["nameserver-policy"]) == [
        "rule-set:geosite-private",
        "rule-set:geosite-cn",
        "rule-set:geosite-steam@cn",
    ]
    rules = profile["rules"]
    assert rules[-1] == "MATCH,FINAL"
    assert "RULE-SET,geosite-steam@cn,DIRECT" in rules
    assert "RULE-SET,geosite-telegram,Telegram" in rules
    assert not [rule for rule in rules if rule.startswith("RULE-SET,custom-")]


def test_rendered_profile_values(mihomo_client_defaults: dict[str, Any]) -> None:
    profile = render_profile(
        profile_vars(mihomo_client_defaults, mihomo_client_mixed_port=7892, mihomo_client_api_secret="s3cret")
    )
    assert profile["mixed-port"] == 7892
    assert profile["secret"] == "s3cret"


# ── conditional custom rule sets ─────────────────────────────────────────────


def test_custom_rule_sets_render_when_payloads_are_set(
    mihomo_client_defaults: dict[str, Any],
) -> None:
    profile = render_profile(
        profile_vars(
            mihomo_client_defaults,
            mihomo_client_custom_rejected_rule_set_payload=["ads.example"],
            mihomo_client_custom_direct_rule_set_payload=["direct.example"],
            mihomo_client_custom_proxied_rule_set_ip_payload=["1.2.3.0/24"],
        )
    )

    providers = profile["rule-providers"]
    assert providers["custom-rejected-rule-set"]["payload"] == ["ads.example"]
    assert providers["custom-rejected-rule-set"]["behavior"] == "domain"
    assert providers["custom-proxied-rule-set-ip"]["payload"] == ["1.2.3.0/24"]
    assert providers["custom-proxied-rule-set-ip"]["behavior"] == "ipcidr"
    # Sets without a payload stay out of the profile entirely.
    assert "custom-rejected-rule-set-ip" not in providers
    assert "custom-direct-rule-set-ip" not in providers
    assert "custom-internal-rule-set" not in providers
    assert len(providers) == 16

    rules = profile["rules"]
    assert rules[:3] == [
        "RULE-SET,custom-rejected-rule-set,REJECT",
        "RULE-SET,custom-direct-rule-set,DIRECT",
        "RULE-SET,custom-proxied-rule-set-ip,PROXY",
    ]
    # Force-direct domains resolve through the domestic DoH pair as well.
    assert "rule-set:custom-direct-rule-set" in profile["dns"]["nameserver-policy"]


def test_internal_rule_set_pairs_with_its_nameservers(
    mihomo_client_defaults: dict[str, Any],
) -> None:
    profile = render_profile(
        profile_vars(
            mihomo_client_defaults,
            mihomo_client_custom_internal_rule_set_payload=["corp.internal"],
            mihomo_client_custom_internal_nameservers=["192.168.1.1"],
        )
    )

    assert profile["rule-providers"]["custom-internal-rule-set"]["payload"] == ["corp.internal"]
    assert "RULE-SET,custom-internal-rule-set,DIRECT" in profile["rules"]
    policy = profile["dns"]["nameserver-policy"]
    assert next(iter(policy)) == "rule-set:custom-internal-rule-set"
    assert policy["rule-set:custom-internal-rule-set"] == ["192.168.1.1"]


def test_internal_rule_set_without_nameservers_gets_no_policy_entry(
    mihomo_client_defaults: dict[str, Any],
) -> None:
    # The role validation fails this combination; the template itself must at
    # least not render an empty (invalid) nameserver-policy entry.
    profile = render_profile(
        profile_vars(mihomo_client_defaults, mihomo_client_custom_internal_rule_set_payload=["corp.internal"])
    )
    assert "RULE-SET,custom-internal-rule-set,DIRECT" in profile["rules"]
    assert "rule-set:custom-internal-rule-set" not in profile["dns"]["nameserver-policy"]
