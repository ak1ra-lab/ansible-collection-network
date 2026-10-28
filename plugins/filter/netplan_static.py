"""Ansible filter plugins for ``ak1ra_lab.network.netplan_static``.

* ``netplan_static_interfaces`` - normalize Ansible network facts into the
  role's minimal interface model: one entry per physical ethernet interface
  with a non-empty IPv4 address list.  Per-interface address overrides are
  validated and replace the captured list.  IPv6 is rejected: the role is
  deliberately IPv4-only and fails closed instead of silently dropping an
  existing IPv6 configuration.
* ``netplan_static_default_routes`` - parse the kernel IPv4 route table
  (``/proc/net/route``) for default routes on captured interfaces.  The
  kernel main table is used instead of ``ansible_facts.default_ipv4`` because
  a TUN client (mihomo's ``auto-route``) can hijack the route lookup without
  owning a netplan-managed interface.
* ``netplan_conflicts`` - classify foreign netplan YAML files against the
  role-managed interfaces.  Netplan merges files by filename order: later
  files amend new mapping keys and override the same keys; list values are
  replaced, not concatenated.  A foreign file defining the same interface is
  therefore only a hard conflict when it would override a key the role owns
  (or when it claims the same device under a different ID).  Complementary
  split configuration is allowed in ``overlap`` mode.
"""

from __future__ import annotations

import base64
import fnmatch
import ipaddress
import re
from pathlib import Path
from typing import Any, NoReturn

import yaml
from ansible.errors import AnsibleFilterError

DOCUMENTATION = r"""
---
name: netplan_static
short_description: Normalize netplan_static interface facts and conflicts
description:
  - This file provides three filter plugins used by the netplan_static role.
  - C(netplan_static_interfaces) normalizes the Ansible network facts into
    the role's minimal interface model (name, MAC address, IPv4 addresses).
    It keeps physical ethernet interfaces with an IPv4 address, validates the
    optional per-interface address overrides, and fails closed on IPv6.
  - C(netplan_static_default_routes) parses the kernel IPv4 route table for
    default routes on the captured interfaces. It reads the main table, so a
    TUN client's policy routing does not leak into the captured gateway.
  - C(netplan_conflicts) classifies foreign netplan YAML files against the
    role-managed interfaces. Netplan merges files by filename order, so a
    complementary split file such as a separate MTU file is allowed in
    C(overlap) mode; a later file that sets a managed key, a different
    interface ID claiming the same device, or a same-named C(/run/netplan)
    file is a hard conflict. Earlier files that the role shadows are
    reported separately as warnings.
options:
  facts:
    description:
      - Full C(ansible_facts) mapping for C(netplan_static_interfaces).
      - It needs C(interfaces) and the per-interface C(type), C(ipv4),
        C(ipv4_secondaries), and C(macaddress) keys.
    type: dict
    required: true
  address_overrides:
    description:
      - Optional mapping of interface name to a CIDR list for
        C(netplan_static_interfaces). A listed interface uses exactly this
        list instead of the captured primary and secondary addresses.
    type: dict
  route_table:
    description:
      - Contents of C(/proc/net/route) for
        C(netplan_static_default_routes), usually the decoded
        C(ansible.builtin.slurp) result.
    type: str
    required: true
  pairs:
    description:
      - List of C([path, base64_encoded_content]) pairs for
        C(netplan_conflicts), usually the C(ansible.builtin.slurp) results
        zipped with the file list.
    type: list
    elements: list
    required: true
  devices:
    description: Managed interface names for C(netplan_conflicts).
    type: list
    elements: str
    required: true
  macaddresses:
    description:
      - Managed MAC addresses for C(netplan_conflicts); matching is
        case-insensitive.
    type: list
    elements: str
  managed_keys:
    description:
      - Key paths the role owns for C(netplan_conflicts). Defaults to the
        keys documented in C(roles/netplan_static/README.md);
        C(nameservers.addresses) is matched as a nested key and C(match)
        covers any C(match.*) key.
    type: list
    elements: str
  role_path:
    description:
      - The role's own netplan file for C(netplan_conflicts); used for the
        filename-order comparison.
    type: str
  marker:
    description:
      - Marker comment identifying the role's own files; matching files are
        ignored by C(netplan_conflicts).
    type: str
  mode:
    description:
      - Conflict policy for C(netplan_conflicts).
      - C(strict) treats any definition of a managed interface as a hard
        conflict; C(overlap) is the merge-aware default; C(none) disables the
        check.
    type: str
    choices: [strict, overlap, none]
    default: overlap
author:
  - ak1ra
"""

EXAMPLES = r"""
- name: Normalize the live interface state for the role template
  ansible.builtin.set_fact:
    _netplan_static_interfaces: >-
      {{ ansible_facts
         | ak1ra_lab.network.netplan_static_interfaces(
             netplan_static_addresses) }}

- name: Capture the physical default routes from the kernel main table
  ansible.builtin.set_fact:
    _netplan_static_physical_default_routes: >-
      {{ route_table.content | ansible.builtin.b64decode
         | ak1ra_lab.network.netplan_static_default_routes(managed_devices) }}

- name: Check foreign netplan files for conflicts
  ansible.builtin.set_fact:
    _netplan_static_conflicts: >-
      {{ (candidate_paths | ansible.builtin.zip(
            slurp_results | map(attribute='content') | list))
         | map('list') | list
         | ak1ra_lab.network.netplan_conflicts(
             managed_devices, managed_macs, managed_keys,
             netplan_static_config_file, file_marker,
             netplan_static_conflict_check) }}
"""

RETURN = r"""
_raw:
  description:
    - A list of C({name, macaddress, addresses}) mappings for
      C(netplan_static_interfaces).
    - A list of C({interface, gateway, metric}) mappings for
      C(netplan_static_default_routes), sorted by metric and interface.
    - A C({hard, shadowed}) mapping for C(netplan_conflicts); each entry
      carries a C(path) and a C(reason), and C(shadowed) entries are
      warnings rather than failures.
  type: raw
  returned: always
"""

_DEFAULT_MANAGED_KEYS = (
    "match",
    "set-name",
    "dhcp4",
    "dhcp6",
    "accept-ra",
    "addresses",
    "routes",
    # gateway4/gateway6 are deprecated but still accepted.  They are not
    # generated by the role; they are listed because a foreign legacy
    # default-route key collides with the role's modern `routes` entry.
    "gateway4",
    "gateway6",
    "nameservers.addresses",
)


def _fail(message: str) -> NoReturn:
    raise AnsibleFilterError(f"netplan_static: {message}")


def _cidr(value: Any, context: str) -> str:
    if not isinstance(value, str) or not value.strip():
        _fail(f"{context} must be a non-empty CIDR string")
    if "/" not in value:
        _fail(f"{context} must include a prefix length: {value!r}")
    try:
        interface = ipaddress.ip_interface(value.strip())
    except ValueError as exc:
        _fail(f"{context} is not a valid CIDR: {value!r} ({exc})")
    if interface.version != 4:
        _fail(f"{context} is IPv6 ({value!r}); netplan_static is IPv4-only")
    return str(interface)


def _primary_cidr(entry: dict[str, Any], context: str) -> str:
    address = entry.get("address")
    prefix = entry.get("prefix")
    if not address or prefix in (None, ""):
        _fail(f"{context} requires address and prefix")
    return _cidr(f"{address}/{prefix}", context)


def _captured_ipv4(data: dict[str, Any], name: str) -> list[str]:
    addresses: list[str] = []
    primary = data.get("ipv4")
    if isinstance(primary, dict):
        addresses.append(_primary_cidr(primary, f"{name}.ipv4"))
    elif isinstance(primary, list):
        for index, entry in enumerate(primary):
            if isinstance(entry, dict):
                addresses.append(_primary_cidr(entry, f"{name}.ipv4[{index}]"))
    for index, entry in enumerate(data.get("ipv4_secondaries") or []):
        if not isinstance(entry, dict):
            _fail(f"{name}.ipv4_secondaries[{index}] must be a mapping")
        addresses.append(_primary_cidr(entry, f"{name}.ipv4_secondaries[{index}]"))
    return addresses


def netplan_static_default_routes(route_table: Any, devices: Any) -> list[dict[str, Any]]:
    """Return the IPv4 default routes from ``/proc/net/route``.

    Only routes to ``0.0.0.0/0`` that carry the ``RTF_GATEWAY`` flag and use
    one of ``devices`` are returned.  ``/proc/net/route`` contains the kernel
    main table only: policy-routing tables created by a TUN client (mihomo's
    table 2022) and ``ansible_facts.default_ipv4`` do not influence it.

    Args:
        route_table: the decoded ``/proc/net/route`` content.
        devices: captured interface names.

    Returns:
        A list of ``{interface, gateway, metric}`` mappings sorted by metric,
        interface and gateway.
    """
    if isinstance(route_table, bytes):
        route_table = route_table.decode("utf-8", errors="replace")
    if not isinstance(route_table, str):
        _fail(f"route_table must be text, got {type(route_table).__name__}")
    if not isinstance(devices, list):
        _fail("devices must be a list of interface names")
    names = {str(device) for device in devices}

    routes: list[dict[str, Any]] = []
    for line in route_table.splitlines()[1:]:
        fields = line.split()
        if len(fields) < 8:
            continue
        interface, destination, gateway, flags, _refcnt, _use, metric, mask = fields[:8]
        if interface not in names:
            continue
        if destination.upper() != "00000000" or mask.upper() != "00000000":
            continue
        try:
            flag_bits = int(flags, 16)
            metric_value = int(metric)
            gateway_address = str(ipaddress.IPv4Address(int(gateway, 16).to_bytes(4, "little")))
        except (ValueError, OverflowError):
            continue
        # RTF_GATEWAY (0x2): a default route without a next hop cannot be
        # rendered as `via`, and the role's contract is one gateway route.
        if not flag_bits & 0x2:
            continue
        routes.append(
            {
                "interface": interface,
                "gateway": gateway_address,
                "metric": metric_value,
            }
        )
    return sorted(routes, key=lambda route: (route["metric"], route["interface"], route["gateway"]))


def netplan_static_interfaces(facts: Any, address_overrides: Any = None) -> list[dict[str, Any]]:
    """Return the normalized interface list for the netplan_static template.

    Args:
        facts: the full ``ansible_facts`` mapping (needs ``interfaces`` and
            the per-interface ``type``/``ipv4``/``ipv4_secondaries``/
            ``macaddress`` keys).
        address_overrides: optional mapping ``{interface: [CIDR, ...]}``.
            A listed interface uses exactly this address list instead of the
            captured primary + secondary addresses.

    Returns:
        A list of ``{name, macaddress, addresses}`` mappings sorted by name.
    """
    if not isinstance(facts, dict):
        _fail(f"facts must be a mapping, got {type(facts).__name__}")
    overrides = address_overrides or {}
    if not isinstance(overrides, dict):
        _fail("address_overrides must be a mapping of interface name to CIDR list")

    normalized_overrides: dict[str, list[str]] = {}
    for name, values in overrides.items():
        if not isinstance(name, str) or not name:
            _fail("address_overrides keys must be non-empty interface names")
        if not isinstance(values, list) or not values:
            _fail(f"address_overrides[{name!r}] must be a non-empty list of CIDRs")
        normalized_overrides[name] = [
            _cidr(value, f"address_overrides[{name!r}][{index}]") for index, value in enumerate(values)
        ]

    interfaces = facts.get("interfaces") or []
    if not isinstance(interfaces, list):
        _fail("facts['interfaces'] must be a list")

    known = {name for name in interfaces if isinstance(name, str)}
    for name in normalized_overrides:
        if name not in known:
            _fail(f"address_overrides references unknown interface {name!r}")

    result: list[dict[str, Any]] = []
    for name in sorted(known):
        data = facts.get(name)
        if not isinstance(data, dict):
            continue
        if data.get("type") != "ether":
            if name in normalized_overrides:
                _fail(f"address_overrides[{name!r}] is not an ethernet interface")
            continue
        if name in normalized_overrides:
            addresses = normalized_overrides[name]
        else:
            addresses = _captured_ipv4(data, name)
        if not addresses:
            continue
        macaddress = data.get("macaddress")
        if not isinstance(macaddress, str) or not macaddress:
            _fail(f"interface {name!r} has no MAC address; use a custom template")
        result.append(
            {
                "name": name,
                "macaddress": macaddress,
                "addresses": addresses,
            }
        )
    return result


def _decode(content: Any) -> str:
    try:
        return base64.b64decode((content or "").strip(), validate=False).decode("utf-8", errors="replace")
    except (ValueError, TypeError):
        return ""


def _matches_name(value: Any, devices: list[str]) -> bool:
    return isinstance(value, str) and any(fnmatch.fnmatchcase(device, value) for device in devices)


_MAC_LINE = re.compile(
    r"^\s*macaddress:\s*['\"]?([0-9A-Fa-f]{2}(?::[0-9A-Fa-f]{2}){5})['\"]?\s*$",
    re.MULTILINE,
)


def _text_mac_conflicts(text: str, macaddresses: set[str]) -> bool:
    # PyYAML parses an unquoted MAC like 52:54:00:00:00:01 as a YAML 1.1
    # sexagesimal integer, so match the raw line as well as the parsed value.
    return any(match.group(1).lower() in macaddresses for match in _MAC_LINE.finditer(text))


def _netplan_order(path: str) -> tuple[str, int]:
    """Return the netplan read order for a file.

    Netplan orders files lexicographically by filename regardless of their
    directory.  A same-named file in /run/netplan shadows /etc/netplan, which
    shadows /lib/netplan.
    """
    file_path = Path(path)
    if file_path.parent == Path("/run/netplan"):
        priority = 3
    elif file_path.parent == Path("/etc/netplan"):
        priority = 2
    else:
        priority = 1
    return (file_path.name, priority)


def _managed_key_present(entry: dict[str, Any], key: str) -> bool:
    if key == "match":
        return "match" in entry
    if key == "nameservers.addresses":
        nameservers = entry.get("nameservers")
        return isinstance(nameservers, dict) and "addresses" in nameservers
    return key in entry


def _overlap_keys(entry: dict[str, Any], managed_keys: list[str]) -> list[str]:
    return [key for key in managed_keys if _managed_key_present(entry, key)]


def _entry_device_match(
    entry_id: str,
    entry: dict[str, Any],
    devices: list[str],
    macaddresses: set[str],
    file_mac_match: bool,
) -> tuple[bool, bool]:
    """Return ``(same_id, different_id_match)`` for one ethernet entry."""
    same_id = entry_id in devices
    match = entry.get("match")
    different_id_match = False
    if isinstance(match, dict):
        if _matches_name(match.get("name"), devices):
            different_id_match = True
        macaddress = match.get("macaddress")
        if isinstance(macaddress, str) and macaddress.lower() in macaddresses:
            different_id_match = True
        if file_mac_match and "macaddress" in match:
            different_id_match = True
    if entry.get("set-name") in devices:
        different_id_match = True
    return same_id, different_id_match


def netplan_conflicts(
    pairs: Any,
    devices: Any,
    macaddresses: Any = None,
    managed_keys: Any = None,
    role_path: str = "",
    marker: str = "",
    mode: str = "overlap",
) -> dict[str, list[dict[str, str]]]:
    """Classify foreign netplan files against the role-managed interfaces.

    Args:
        pairs: list of ``[path, base64-encoded content]`` entries (slurp
            output zipped with the file list).
        devices: managed interface names.
        macaddresses: managed MAC addresses (case-insensitive).
        managed_keys: key paths the role owns.  ``nameservers.addresses`` is
            matched as a nested key; ``match`` covers any ``match.*`` key.
        role_path: the role's own netplan file; used for read-order comparison.
        marker: role marker comment; files containing it are ignored.
        mode: ``strict`` (any same-interface definition is hard), ``overlap``
            (merge-aware) or ``none``.

    Returns:
        ``{"hard": [{"path": ..., "reason": ...}], "shadowed": [...]}``.
        ``shadowed`` entries set a managed key before the role file, so the
        role wins; they are warnings, not failures.
    """
    if mode not in {"strict", "overlap", "none"}:
        _fail(f"mode must be one of strict, overlap, none (got: {mode!r})")
    if mode == "none":
        return {"hard": [], "shadowed": []}
    if not isinstance(pairs, list):
        _fail("conflict pairs must be a list of [path, base64 content]")
    if not isinstance(devices, list):
        _fail("devices must be a list")
    if managed_keys is None:
        managed = list(_DEFAULT_MANAGED_KEYS)
    elif isinstance(managed_keys, list):
        managed = [str(key) for key in managed_keys]
    else:
        _fail("managed_keys must be a list of key paths")
    macs = {mac.lower() for mac in (macaddresses or []) if isinstance(mac, str)}
    role_order = _netplan_order(role_path) if role_path else ("", 0)

    hard: dict[str, list[str]] = {}
    shadowed: dict[str, list[str]] = {}

    def add(target: dict[str, list[str]], path: str, reason: str) -> None:
        reasons = target.setdefault(str(path), [])
        if reason not in reasons:
            reasons.append(reason)

    for pair in pairs:
        if not isinstance(pair, (list, tuple)) or len(pair) != 2:
            continue
        path, content = pair
        text = _decode(content)
        if marker and marker in text:
            continue
        file_mac_match = _text_mac_conflicts(text, macs)
        try:
            data = yaml.safe_load(text) or {}
        except yaml.YAMLError:
            continue
        network = data.get("network") if isinstance(data, dict) else None
        ethernets = network.get("ethernets") if isinstance(network, dict) else None
        if not isinstance(ethernets, dict):
            continue
        for entry_id, entry in ethernets.items():
            if not isinstance(entry, dict):
                continue
            same_id, different_id_match = _entry_device_match(str(entry_id), entry, devices, macs, file_mac_match)
            if not same_id and not different_id_match:
                continue
            if different_id_match and not same_id:
                add(hard, path, f"matches a managed device under a different ID {entry_id!r}")
                continue
            if mode == "strict":
                add(hard, path, "defines the managed interface (strict mode)")
                continue
            if (
                role_path
                and Path(str(path)).name == Path(role_path).name
                and Path(str(path)).parent == Path("/run/netplan")
                and Path(role_path).parent != Path("/run/netplan")
            ):
                # A same-named /run/netplan file completely shadows the role
                # file, even if it does not set one of the managed keys.
                add(hard, path, "shadows the role file with the same filename")
                continue
            overlap = _overlap_keys(entry, managed)
            if not overlap:
                continue
            if _netplan_order(str(path)) > role_order:
                add(hard, path, f"sets {', '.join(overlap)} after the role file")
            else:
                add(shadowed, path, f"sets {', '.join(overlap)} before the role file")

    return {
        "hard": [{"path": path, "reason": "; ".join(reasons)} for path, reasons in hard.items()],
        "shadowed": [{"path": path, "reason": "; ".join(reasons)} for path, reasons in shadowed.items()],
    }


class FilterModule:
    """Ansible filter plugin registration for the netplan_static role."""

    def filters(self) -> dict[str, Any]:
        return {
            "netplan_static_interfaces": netplan_static_interfaces,
            "netplan_static_default_routes": netplan_static_default_routes,
            "netplan_conflicts": netplan_conflicts,
        }
