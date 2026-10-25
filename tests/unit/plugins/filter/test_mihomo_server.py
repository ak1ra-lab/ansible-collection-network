"""Unit tests for plugins/filter/mihomo_server.py.

Coverage follows the mihomo listener schema (verified against
wiki.metacubex.one) and the client-facing naming contract:

* shadowsocks is single-user; trojan/vless take user lists; hysteria2, tuic
  and anytls take name/uuid -> password mappings,
* TLS fields are flat on every TLS-using listener and both paths are
  mandatory (mihomo has no built-in ACME),
* enabled listeners must not share ports,
* generated client nodes are named <prefix>-<REGION>-<host>[-<user>]-<proto>
  (prefix `selfhost` by default) and pass the client-side naming validation.
"""

from __future__ import annotations

from typing import Any

import pytest
from ansible.errors import AnsibleFilterError
from mihomo_providers import mihomo_selfhost_proxies
from mihomo_server import mihomo_server_client_proxies, mihomo_server_config

CERT = "/etc/mihomo/tls/fullchain.pem"
KEY = "/etc/mihomo/tls/privkey.pem"
UUID_A = "11111111-1111-1111-1111-111111111111"


def server_spec(**overrides: Any) -> dict[str, Any]:
    """A disabled-by-default spec; tests enable what they exercise."""
    spec: dict[str, Any] = {
        "enable_shadowsocks": False,
        "enable_trojan": False,
        "enable_hysteria2": False,
        "enable_vless": False,
        "enable_tuic": False,
        "enable_anytls": False,
        "tls_certificate_path": CERT,
        "tls_key_path": KEY,
    }
    spec.update(overrides)
    return spec


def all_protocols(**overrides: Any) -> dict[str, Any]:
    spec = server_spec(
        enable_shadowsocks=True,
        shadowsocks_password="c2VydmVyLXBhc3M=",
        enable_trojan=True,
        trojan_users=[{"name": "alice", "password": "trojan-pw"}],
        enable_hysteria2=True,
        hysteria2_users=[{"name": "alice", "password": "hy2-pw"}],
        hysteria2_up_mbps=100,
        hysteria2_down_mbps=200,
        enable_vless=True,
        vless_users=[{"name": "alice", "uuid": UUID_A}],
        vless_flow="xtls-rprx-vision",
        enable_tuic=True,
        tuic_users=[{"name": "alice", "uuid": UUID_A, "password": "tuic-pw"}],
        enable_anytls=True,
        anytls_users=[{"name": "alice", "password": "anytls-pw"}],
    )
    spec.update(overrides)
    return spec


# ── server config ────────────────────────────────────────────────────────────


def test_listener_order_and_schema() -> None:
    config = mihomo_server_config(all_protocols())
    listeners = {listener["name"]: listener for listener in config["listeners"]}
    assert [listener["name"] for listener in config["listeners"]] == [
        "ss-in",
        "trojan-in",
        "hysteria2-in",
        "vless-in",
        "tuic-in",
        "anytls-in",
    ]
    assert config["rules"] == ["MATCH,DIRECT"]
    assert config["log-level"] == "warning"

    ss = listeners["ss-in"]
    assert ss["type"] == "shadowsocks"
    assert ss["password"] == "c2VydmVyLXBhc3M="
    assert ss["udp"] is True
    assert "users" not in ss
    assert "certificate" not in ss

    trojan = listeners["trojan-in"]
    assert trojan["users"] == [{"username": "alice", "password": "trojan-pw"}]
    assert trojan["certificate"] == CERT
    assert trojan["private-key"] == KEY

    hy2 = listeners["hysteria2-in"]
    assert hy2["users"] == {"alice": "hy2-pw"}
    assert hy2["up"] == 100
    assert hy2["down"] == 200
    assert hy2["alpn"] == ["h3"]
    assert hy2["certificate"] == CERT

    vless = listeners["vless-in"]
    assert vless["users"] == [{"username": "alice", "uuid": UUID_A, "flow": "xtls-rprx-vision"}]

    tuic = listeners["tuic-in"]
    assert tuic["users"] == {UUID_A: "tuic-pw"}
    assert tuic["congestion-controller"] == "bbr"
    assert tuic["alpn"] == ["h3"]

    anytls = listeners["anytls-in"]
    assert anytls["users"] == {"alice": "anytls-pw"}
    assert "padding-scheme" not in anytls
    assert anytls["certificate"] == CERT


def test_hysteria2_obfs_and_masquerade() -> None:
    config = mihomo_server_config(
        all_protocols(
            hysteria2_obfs_enabled=True,
            hysteria2_obfs_password="obfs-pw",
        )
    )
    hy2 = next(listener for listener in config["listeners"] if listener["name"] == "hysteria2-in")
    assert hy2["obfs"] == "salamander"
    assert hy2["obfs-password"] == "obfs-pw"
    assert hy2["masquerade"] == "https://www.bing.com"


def test_hysteria2_server_bandwidth_is_optional() -> None:
    config = mihomo_server_config(all_protocols(hysteria2_up_mbps=0, hysteria2_down_mbps=0))
    hy2 = next(listener for listener in config["listeners"] if listener["name"] == "hysteria2-in")
    assert "up" not in hy2
    assert "down" not in hy2
    assert "ignore-client-bandwidth" not in hy2


def test_anytls_padding_scheme() -> None:
    config = mihomo_server_config(all_protocols(anytls_padding_scheme="stop=8"))
    anytls = next(listener for listener in config["listeners"] if listener["name"] == "anytls-in")
    assert anytls["padding-scheme"] == "stop=8"


def test_extra_listeners_are_appended() -> None:
    config = mihomo_server_config(all_protocols(extra_listeners=[{"name": "vmess-in", "type": "vmess", "port": 9000}]))
    assert config["listeners"][-1] == {
        "name": "vmess-in",
        "type": "vmess",
        "port": 9000,
    }


def test_extra_listener_name_collision_fails() -> None:
    with pytest.raises(AnsibleFilterError, match="already used"):
        mihomo_server_config(all_protocols(extra_listeners=[{"name": "ss-in", "type": "socks"}]))


def test_no_protocol_enabled_fails() -> None:
    with pytest.raises(AnsibleFilterError, match="at least one protocol"):
        mihomo_server_config(server_spec())


def test_tls_paths_required_for_tls_protocols() -> None:
    with pytest.raises(AnsibleFilterError, match="no built-in ACME"):
        mihomo_server_config(
            server_spec(
                enable_trojan=True,
                trojan_users=[{"name": "alice", "password": "pw"}],
                tls_certificate_path="",
                tls_key_path="",
            )
        )


def test_duplicate_ports_fail() -> None:
    with pytest.raises(AnsibleFilterError, match="already used by shadowsocks"):
        mihomo_server_config(all_protocols(trojan_port=8388))


def test_users_are_required_for_enabled_protocols() -> None:
    with pytest.raises(AnsibleFilterError, match="trojan_users must be a non-empty list"):
        mihomo_server_config(server_spec(enable_trojan=True))


def test_uuid_is_required_for_vless_users() -> None:
    with pytest.raises(AnsibleFilterError, match="requires a non-empty 'uuid'"):
        mihomo_server_config(server_spec(enable_vless=True, vless_users=[{"name": "alice"}]))


def test_shadowsocks_password_is_required() -> None:
    with pytest.raises(AnsibleFilterError, match="shadowsocks_password"):
        mihomo_server_config(server_spec(enable_shadowsocks=True))


def test_string_switches_are_coerced() -> None:
    config = mihomo_server_config(all_protocols(enable_trojan="false", enable_vless="0", enable_tuic="off"))
    names = [listener["name"] for listener in config["listeners"]]
    assert "trojan-in" not in names
    assert "vless-in" not in names
    assert "tuic-in" not in names
    assert "ss-in" in names


def test_duplicate_user_names_fail() -> None:
    with pytest.raises(AnsibleFilterError, match="duplicates user name"):
        mihomo_server_config(
            server_spec(
                enable_trojan=True,
                trojan_users=[
                    {"name": "alice", "password": "a"},
                    {"name": "alice", "password": "b"},
                ],
            )
        )


def test_null_tls_paths_fail() -> None:
    with pytest.raises(AnsibleFilterError, match="no built-in ACME"):
        mihomo_server_config(
            server_spec(
                enable_trojan=True,
                trojan_users=[{"name": "alice", "password": "pw"}],
                tls_certificate_path=None,
                tls_key_path=None,
            )
        )


def test_extra_listener_port_collision_fails() -> None:
    with pytest.raises(AnsibleFilterError, match="already used by shadowsocks"):
        mihomo_server_config(
            server_spec(
                enable_shadowsocks=True,
                shadowsocks_password="c2VydmVyLXBhc3M=",
                extra_listeners=[{"name": "socks-in", "type": "socks", "port": 8388}],
            )
        )


# ── client proxies ───────────────────────────────────────────────────────────


def client_config(**overrides: Any) -> dict[str, Any]:
    spec = all_protocols(
        hostname="node01.example.com",
        region="US",
    )
    spec.update(overrides)
    return mihomo_server_client_proxies(spec)


def test_client_proxy_names_follow_the_contract() -> None:
    proxies = client_config()["proxies"]
    names = [proxy["name"] for proxy in proxies]
    assert names == [
        "selfhost-US-node01-ss",
        "selfhost-US-node01-alice-trojan",
        "selfhost-US-node01-alice-hy2",
        "selfhost-US-node01-alice-vless",
        "selfhost-US-node01-alice-tuic",
        "selfhost-US-node01-alice-anytls",
    ]


def test_client_proxy_shapes() -> None:
    proxies = {proxy["name"]: proxy for proxy in client_config()["proxies"]}
    ss = proxies["selfhost-US-node01-ss"]
    assert ss["type"] == "ss"
    assert ss["password"] == "c2VydmVyLXBhc3M="
    assert ss["udp"] is True

    trojan = proxies["selfhost-US-node01-alice-trojan"]
    assert trojan["sni"] == "node01.example.com"
    assert trojan["skip-cert-verify"] is False

    hy2 = proxies["selfhost-US-node01-alice-hy2"]
    assert "up" not in hy2
    assert "down" not in hy2

    vless = proxies["selfhost-US-node01-alice-vless"]
    assert vless["servername"] == "node01.example.com"
    assert vless["flow"] == "xtls-rprx-vision"

    tuic = proxies["selfhost-US-node01-alice-tuic"]
    assert tuic["alpn"] == ["h3"]
    assert tuic["congestion-controller"] == "bbr"


def test_client_proxy_prefix_can_be_overridden() -> None:
    proxies = client_config(client_node_prefix="relay")["proxies"]
    assert proxies[0]["name"] == "relay-US-node01-ss"
    with pytest.raises(AnsibleFilterError, match="client_node_prefix"):
        client_config(client_node_prefix="  ")


def test_tuic_alpn_follows_the_server_spec() -> None:
    proxies = client_config(alpn=["h3", "h2"])["proxies"]
    tuic = next(proxy for proxy in proxies if proxy["name"].endswith("-tuic"))
    assert tuic["alpn"] == ["h3", "h2"]


def test_hysteria2_client_bandwidth_is_never_emitted() -> None:
    proxies = client_config(hysteria2_up_mbps=100, hysteria2_down_mbps=200)["proxies"]
    hy2 = next(proxy for proxy in proxies if proxy["name"].endswith("-hy2"))
    assert "up" not in hy2
    assert "down" not in hy2
    assert hy2["alpn"] == ["h3"]


def test_client_proxies_validate_ports() -> None:
    with pytest.raises(AnsibleFilterError, match="trojan_port must be an integer"):
        client_config(trojan_port="8443")


def test_client_proxies_require_hostname_and_region() -> None:
    with pytest.raises(AnsibleFilterError, match="hostname is required"):
        mihomo_server_client_proxies(all_protocols(region="US"))
    with pytest.raises(AnsibleFilterError, match="region must be"):
        mihomo_server_client_proxies(all_protocols(hostname="node01.example.com"))
    with pytest.raises(AnsibleFilterError, match="region must be"):
        mihomo_server_client_proxies(all_protocols(hostname="node01.example.com", region="two words"))


# ── cross-role contract ──────────────────────────────────────────────────────


def test_generated_nodes_carry_the_client_naming_tokens() -> None:
    # The client profile matches nodes by the `selfhost|自建` tag and a region
    # token; its region regexes live in the client profile template, so the
    # mechanical region check runs there.  Here: both tokens must survive the
    # generation, and the names must pass the client-side tag validation.
    proxies = client_config()["proxies"]
    for proxy in proxies:
        assert "selfhost" in proxy["name"]
        assert "-US-" in proxy["name"]
    validated = mihomo_selfhost_proxies({"proxies": proxies, "selfhost_pattern": "selfhost|自建"})
    assert validated["proxies"] == proxies
