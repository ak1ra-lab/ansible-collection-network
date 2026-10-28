"""Unit tests for the netplan_static filter plugins."""

from __future__ import annotations

import base64

import pytest
from ansible.errors import AnsibleFilterError
from netplan_static import netplan_conflicts, netplan_static_interfaces


def _facts(*interfaces: dict) -> dict:
    return {
        "interfaces": [interface["device"] for interface in interfaces],
        **{interface["device"]: interface for interface in interfaces},
    }


def _ether(name: str, address: str = "192.0.2.10", prefix: str = "24", **extra) -> dict:
    return {
        "device": name,
        "type": "ether",
        "macaddress": "52:54:00:00:00:01",
        "ipv4": {"address": address, "prefix": prefix},
        **extra,
    }


def _pairs(*entries: tuple[str, str]) -> list[list[str]]:
    return [[path, base64.b64encode(content.encode()).decode()] for path, content in entries]


def test_primary_address() -> None:
    result = netplan_static_interfaces(_facts(_ether("eth0")))
    assert result == [
        {
            "name": "eth0",
            "macaddress": "52:54:00:00:00:01",
            "addresses": ["192.0.2.10/24"],
        }
    ]


def test_primary_and_secondaries() -> None:
    facts = _facts(
        _ether(
            "eth0",
            ipv4_secondaries=[
                {"address": "198.51.100.10", "prefix": "24"},
                {"address": "203.0.113.10", "prefix": "28"},
            ],
        )
    )
    result = netplan_static_interfaces(facts)
    assert result[0]["addresses"] == [
        "192.0.2.10/24",
        "198.51.100.10/24",
        "203.0.113.10/28",
    ]


def test_override_replaces_captured_addresses() -> None:
    facts = _facts(_ether("eth0"))
    result = netplan_static_interfaces(
        facts,
        {"eth0": ["172.16.0.10/24", "172.16.1.10/24"]},
    )
    assert result[0]["addresses"] == ["172.16.0.10/24", "172.16.1.10/24"]


def test_non_ethernet_interfaces_are_skipped() -> None:
    facts = _facts(
        _ether("eth0"),
        {
            "device": "lo",
            "type": "loopback",
            "ipv4": {"address": "127.0.0.1", "prefix": "8"},
        },
    )
    result = netplan_static_interfaces(facts)
    assert [entry["name"] for entry in result] == ["eth0"]


def test_ethernet_without_ipv4_is_skipped() -> None:
    facts = _facts({"device": "eth1", "type": "ether", "macaddress": "52:54:00:00:00:02"})
    assert netplan_static_interfaces(facts) == []


def test_unknown_override_fails() -> None:
    with pytest.raises(AnsibleFilterError, match="unknown interface"):
        netplan_static_interfaces(_facts(_ether("eth0")), {"eth9": ["192.0.2.10/24"]})


def test_override_on_non_ethernet_fails() -> None:
    facts = _facts({"device": "lo", "type": "loopback"})
    with pytest.raises(AnsibleFilterError, match="not an ethernet interface"):
        netplan_static_interfaces(facts, {"lo": ["127.0.0.1/8"]})


def test_ipv6_override_fails() -> None:
    with pytest.raises(AnsibleFilterError, match="IPv4-only"):
        netplan_static_interfaces(_facts(_ether("eth0")), {"eth0": ["2001:db8::10/64"]})


def test_invalid_cidr_fails() -> None:
    with pytest.raises(AnsibleFilterError, match="prefix length"):
        netplan_static_interfaces(_facts(_ether("eth0")), {"eth0": ["192.0.2.10"]})


def test_missing_mac_fails() -> None:
    facts = _facts(
        {
            "device": "eth0",
            "type": "ether",
            "ipv4": {"address": "192.0.2.10", "prefix": "24"},
        }
    )
    with pytest.raises(AnsibleFilterError, match="no MAC address"):
        netplan_static_interfaces(facts)


ROLE = "/etc/netplan/90-ansible-static.yaml"
MARKER = "ak1ra_lab.network.netplan_static"
MANAGED_KEYS = [
    "match",
    "set-name",
    "dhcp4",
    "dhcp6",
    "accept-ra",
    "addresses",
    "routes",
    "gateway4",
    "gateway6",
    "nameservers.addresses",
]


def _report(
    pairs: list[list[str]],
    devices: list[str] | None = None,
    macs: list[str] | None = None,
    managed: list[str] | None = None,
    role: str = ROLE,
    mode: str = "overlap",
) -> dict:
    return netplan_conflicts(
        pairs,
        devices or ["eth0"],
        macs or ["52:54:00:00:00:01"],
        managed or MANAGED_KEYS,
        role,
        MARKER,
        mode,
    )


def test_overlap_allows_complementary_mtu() -> None:
    pairs = _pairs(
        (
            "/etc/netplan/10-mtu.yaml",
            "network:\n  ethernets:\n    eth0:\n      mtu: 9000\n",
        )
    )
    assert _report(pairs) == {"hard": [], "shadowed": []}


def test_overlap_allows_complementary_nameserver_search() -> None:
    pairs = _pairs(
        (
            "/etc/netplan/99-extra.yaml",
            "network:\n  ethernets:\n    eth0:\n      nameservers:\n        search: [lab]\n",
        )
    )
    assert _report(pairs) == {"hard": [], "shadowed": []}


def test_overlap_warns_on_earlier_managed_key() -> None:
    pairs = _pairs(
        (
            "/etc/netplan/10-extra.yaml",
            "network:\n  ethernets:\n    eth0:\n      addresses: [192.0.2.20/24]\n",
        )
    )
    report = _report(pairs)
    assert report["hard"] == []
    assert [entry["path"] for entry in report["shadowed"]] == ["/etc/netplan/10-extra.yaml"]


def test_overlap_fails_on_later_managed_key() -> None:
    pairs = _pairs(
        (
            "/etc/netplan/99-extra.yaml",
            "network:\n  ethernets:\n    eth0:\n      addresses: [192.0.2.20/24]\n",
        )
    )
    report = _report(pairs)
    assert [entry["path"] for entry in report["hard"]] == ["/etc/netplan/99-extra.yaml"]
    assert report["shadowed"] == []


def test_overlap_fails_on_later_nameserver_addresses() -> None:
    pairs = _pairs(
        (
            "/etc/netplan/99-extra.yaml",
            "network:\n  ethernets:\n    eth0:\n      nameservers:\n        addresses: [1.1.1.1]\n",
        )
    )
    assert [entry["path"] for entry in _report(pairs)["hard"]] == ["/etc/netplan/99-extra.yaml"]


def test_overlap_fails_on_later_gateway4() -> None:
    pairs = _pairs(
        (
            "/etc/netplan/99-extra.yaml",
            "network:\n  ethernets:\n    eth0:\n      gateway4: 192.0.2.1\n",
        )
    )
    assert [entry["path"] for entry in _report(pairs)["hard"]] == ["/etc/netplan/99-extra.yaml"]


def test_overlap_fails_on_different_id_same_mac() -> None:
    pairs = _pairs(
        (
            "/etc/netplan/10-extra.yaml",
            (
                "network:\n  ethernets:\n    uplink:\n      match:\n"
                "        macaddress: 52:54:00:00:00:01\n      mtu: 9000\n"
            ),
        )
    )
    assert [entry["path"] for entry in _report(pairs)["hard"]] == ["/etc/netplan/10-extra.yaml"]


def test_overlap_fails_on_different_id_same_name_glob() -> None:
    pairs = _pairs(
        (
            "/etc/netplan/10-extra.yaml",
            "network:\n  ethernets:\n    uplink:\n      match:\n        name: 'eth*'\n",
        )
    )
    assert [entry["path"] for entry in _report(pairs)["hard"]] == ["/etc/netplan/10-extra.yaml"]


def test_overlap_ignores_other_interfaces() -> None:
    pairs = _pairs(
        (
            "/etc/netplan/99-extra.yaml",
            "network:\n  ethernets:\n    eth1:\n      addresses: [192.0.2.20/24]\n",
        )
    )
    assert _report(pairs) == {"hard": [], "shadowed": []}


def test_overlap_skips_the_role_marker() -> None:
    pairs = _pairs(
        (
            ROLE,
            f"# {MARKER}\nnetwork:\n  ethernets:\n    eth0:\n      addresses: [192.0.2.20/24]\n",
        )
    )
    assert _report(pairs) == {"hard": [], "shadowed": []}


def test_strict_flags_complementary_configuration() -> None:
    pairs = _pairs(
        (
            "/etc/netplan/10-mtu.yaml",
            "network:\n  ethernets:\n    eth0:\n      mtu: 9000\n",
        )
    )
    assert [entry["path"] for entry in _report(pairs, mode="strict")["hard"]] == ["/etc/netplan/10-mtu.yaml"]


def test_off_returns_no_findings() -> None:
    pairs = _pairs(
        (
            "/etc/netplan/99-extra.yaml",
            "network:\n  ethernets:\n    eth0:\n      addresses: [192.0.2.20/24]\n",
        )
    )
    assert _report(pairs, mode="none") == {"hard": [], "shadowed": []}


def test_run_same_filename_shadows_the_role_file() -> None:
    pairs = _pairs(
        (
            "/run/netplan/90-ansible-static.yaml",
            "network:\n  ethernets:\n    eth0:\n      mtu: 9000\n",
        )
    )
    report = _report(pairs)
    assert [entry["path"] for entry in report["hard"]] == ["/run/netplan/90-ansible-static.yaml"]


def test_lib_same_filename_is_shadowed_by_the_role_file() -> None:
    pairs = _pairs(
        (
            "/lib/netplan/90-ansible-static.yaml",
            "network:\n  ethernets:\n    eth0:\n      mtu: 9000\n",
        )
    )
    assert _report(pairs) == {"hard": [], "shadowed": []}
