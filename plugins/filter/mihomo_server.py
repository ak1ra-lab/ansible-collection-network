"""Ansible filter plugins: generate the mihomo server configuration.

The role ``ak1ra_lab.network.mihomo_server`` deploys mihomo on a VPS as a
proxy server (``listeners``) and writes the matching client artifact for the
``mihomo_client`` role.  This module owns the two structures that are painful
to keep consistent in YAML:

* ``mihomo_server_config`` - the full server configuration: per-protocol
  ``listeners`` entries where the user shape differs (shadowsocks is
  single-user, trojan/vless take a list, hysteria2/tuic/anytls take a
  username/uuid -> password mapping) and TLS fields are flat.
* ``mihomo_server_client_proxies`` - the clash-format client nodes, named
  ``<client_node_prefix>-<REGION>-<host>[-<user>]-<proto>`` (the default
  ``selfhost`` prefix is what the client's ``selfhost|自建`` tag and region
  regex groups pick up).

TLS is manual certificate/key paths (mihomo has no built-in ACME), except
VLESS REALITY, which uses a borrowed ``dest`` handshake and an X25519
keypair instead of a certificate, and AnyTLS with ``security_mode: jls``,
which uses the JLS outer TLS layer and falls back to a real destination.
``mihomo_server_config`` validates that every certificate-using listener has
both paths set and that JLS has a complete, mutually consistent configuration.
"""

from __future__ import annotations

import ipaddress
import re
from typing import Any, NoReturn

from ansible.errors import AnsibleFilterError

DOCUMENTATION = r"""
---
name: mihomo_server
short_description: Build mihomo server listeners and client nodes
description:
  - This file provides two filter plugins used by the mihomo server role.
  - C(mihomo_server_config) validates the role's server contract and returns
    the complete mihomo configuration with the per-protocol C(listeners)
    entries.
  - C(mihomo_server_client_proxies) returns the clash-format client nodes for
    the same server contract, named C(<prefix>-<REGION>-<host>[-<user>]-<proto>)
    so the mihomo client region groups pick them up.
  - The full input contract, including listener, TLS, REALITY, JLS, and
    padding options, is documented in C(roles/mihomo_server/README.md).
options:
  config:
    description:
      - Server mapping assembled by the role (and, for the client filter,
        extended with C(hostname), C(region), and C(client_node_prefix)).
    type: dict
    required: true
author:
  - ak1ra
"""

EXAMPLES = r"""
- name: Render the server configuration
  ansible.builtin.set_fact:
    mihomo_server_config_rendered: >-
      {{ mihomo_server_spec | ak1ra_lab.network.mihomo_server_config }}

- name: Render the clash-format client nodes
  ansible.builtin.set_fact:
    mihomo_server_client_nodes: >-
      {{ mihomo_server_spec
         | combine({'hostname': mihomo_server_hostname,
                    'region': mihomo_server_client_node_region,
                    'client_node_prefix': mihomo_server_client_node_prefix})
         | ak1ra_lab.network.mihomo_server_client_proxies }}
"""

RETURN = r"""
_raw:
  description:
    - The server configuration mapping for C(mihomo_server_config), or a
      mapping with a C(proxies) list for C(mihomo_server_client_proxies).
  type: dict
  returned: always
"""

# Fixed listener order and the per-protocol facts the generation branches on.
# The fallback defaults below mirror roles/mihomo_server/defaults/main.yaml;
# the role passes its full spec, so they only cover direct filter calls.
PROTOCOLS = ("shadowsocks", "trojan", "hysteria2", "vless", "tuic", "anytls")
TLS_PROTOCOLS = ("trojan", "hysteria2", "vless", "tuic", "anytls")
PASSWORD_PROTOCOLS = ("trojan", "hysteria2", "tuic", "anytls")
UUID_PROTOCOLS = ("vless", "tuic")
LISTENER_TAGS = {
    "shadowsocks": "ss-in",
    "trojan": "trojan-in",
    "hysteria2": "hysteria2-in",
    "vless": "vless-in",
    "tuic": "tuic-in",
    "anytls": "anytls-in",
}
CLIENT_PROTO_TAGS = {
    "trojan": "trojan",
    "hysteria2": "hy2",
    "vless": "vless",
    "tuic": "tuic",
    "anytls": "anytls",
}
ANYTLS_SECURITY_MODES = ("certificate", "jls")


def _fail(message: str) -> NoReturn:
    raise AnsibleFilterError(f"mihomo_server: {message}")


def _populate(config: Any, **defaults: Any) -> dict[str, Any]:
    if not isinstance(config, dict):
        _fail(f"expected a mapping of server options, got {type(config).__name__}")
    merged = dict(defaults)
    merged.update(config)
    return merged


def _truthy(value: Any) -> bool:
    """Ansible-style truthiness for switches that may arrive as 'false'."""
    if isinstance(value, str):
        return value.strip().lower() not in ("", "false", "no", "off", "0")
    return bool(value)


def _enabled(config: dict[str, Any]) -> list[str]:
    enabled = [name for name in PROTOCOLS if _truthy(config[f"enable_{name}"])]
    if not enabled:
        _fail("at least one protocol must be enabled")
    return enabled


def _validate_port(config: dict[str, Any], protocol: str) -> None:
    port = config[f"{protocol}_port"]
    if not isinstance(port, int) or isinstance(port, bool) or not 1 <= port <= 65535:
        _fail(f"{protocol}_port must be an integer between 1 and 65535, got {port!r}")


def _int_at_least(config: dict[str, Any], key: str, minimum: int) -> int:
    value = config[key]
    if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
        _fail(f"{key} must be an integer >= {minimum}, got {value!r}")
    return value


def _reality_dest(config: dict[str, Any]) -> str:
    dest = str(config["vless_reality_dest"]).strip()
    if not re.fullmatch(r".+:[0-9]+", dest):
        _fail(f"vless_reality_dest must be host:port, got {dest!r}")
    return dest


def _reality_short_id(config: dict[str, Any]) -> str:
    short_id = str(config["vless_reality_short_id"]).strip()
    if not short_id or len(short_id) % 2 or not re.fullmatch(r"[0-9a-fA-F]{2,16}", short_id):
        _fail(f"vless_reality_short_id must be even-length hex (2-16 chars), got {short_id!r}")
    return short_id


def _reality_server_names(config: dict[str, Any]) -> list[str]:
    names = config["vless_reality_server_names"]
    if not isinstance(names, list):
        _fail("vless_reality_server_names must be a list")
    cleaned: list[str] = []
    for index, name in enumerate(names):
        if not isinstance(name, str) or not name.strip():
            _fail(f"vless_reality_server_names[{index}] must be a non-empty string")
        value = name.strip()
        if any(char.isspace() for char in value):
            _fail(f"vless_reality_server_names[{index}] must not contain whitespace, got {value!r}")
        cleaned.append(value)
    if cleaned:
        return cleaned
    host = _reality_dest(config).rsplit(":", 1)[0].strip().strip("[]")
    if not host:
        _fail("vless_reality_dest must include a host before the port")
    return [host]


def _validate_vless_reality(config: dict[str, Any]) -> None:
    if not _truthy(config["vless_reality_enabled"]) or not _truthy(config["enable_vless"]):
        return
    _reality_dest(config)
    _reality_short_id(config)
    _reality_server_names(config)
    if not str(config["vless_reality_private_key"]).strip():
        _fail("vless_reality_private_key must not be empty (generated by the role)")


def _anytls_security_mode(config: dict[str, Any]) -> str:
    mode = str(config["anytls_security_mode"]).strip().lower()
    if mode not in ANYTLS_SECURITY_MODES:
        _fail(f"anytls_security_mode must be one of {', '.join(ANYTLS_SECURITY_MODES)}, got {mode!r}")
    return mode


def _validate_tls(config: dict[str, Any], enabled: list[str]) -> None:
    reality = _truthy(config["vless_reality_enabled"])
    anytls_jls = "anytls" in enabled and _anytls_security_mode(config) == "jls"
    needs_tls = [
        name
        for name in enabled
        if name in TLS_PROTOCOLS and not (name == "vless" and reality) and not (name == "anytls" and anytls_jls)
    ]
    if not needs_tls:
        return
    certificate = config["tls_certificate_path"]
    private_key = config["tls_key_path"]
    if not isinstance(certificate, str) or not certificate.strip():
        certificate = ""
    if not isinstance(private_key, str) or not private_key.strip():
        private_key = ""
    if not certificate or not private_key:
        _fail(
            f"{', '.join(needs_tls)} enabled but tls_certificate_path / "
            f"tls_key_path are not both set (mihomo has no built-in ACME; "
            f"provide PEM paths)"
        )


def _users(config: dict[str, Any], protocol: str) -> list[dict[str, Any]]:
    users = config[f"{protocol}_users"]
    if not isinstance(users, list) or not users:
        _fail(f"{protocol}_users must be a non-empty list when {protocol} is enabled")
    seen: set[str] = set()
    for index, user in enumerate(users):
        if not isinstance(user, dict):
            _fail(f"{protocol}_users[{index}] must be a mapping")
        name = user.get("name")
        if not isinstance(name, str) or not name.strip():
            _fail(f"{protocol}_users[{index}] requires a non-empty 'name'")
        if name in seen:
            _fail(f"{protocol}_users[{index}] duplicates user name {name!r}")
        seen.add(name)
        if protocol in PASSWORD_PROTOCOLS:
            password = user.get("password")
            if not isinstance(password, str) or not password.strip():
                _fail(f"{protocol}_users[{index}] requires a non-empty 'password'")
        if protocol in UUID_PROTOCOLS:
            uuid = user.get("uuid")
            if not isinstance(uuid, str) or not uuid.strip():
                _fail(f"{protocol}_users[{index}] requires a non-empty 'uuid'")
    return users


def _tls_fields(config: dict[str, Any]) -> dict[str, Any]:
    return {
        "certificate": config["tls_certificate_path"],
        "private-key": config["tls_key_path"],
    }


def _split_host_port(value: str, key: str) -> tuple[str, int]:
    host, separator, port_text = value.rpartition(":")
    if not separator or not port_text.isdigit():
        _fail(f"{key} must be host:port, got {value!r}")
    if host.startswith("[") and host.endswith("]"):
        host = host[1:-1]
    elif ":" in host:
        _fail(f"{key} must bracket IPv6 addresses as [addr]:port, got {value!r}")
    port = int(port_text)
    if not host or not 1 <= port <= 65535:
        _fail(f"{key} must be host:port with a port in 1..65535, got {value!r}")
    return host, port


def _jls_dest(config: dict[str, Any]) -> str:
    dest = config["anytls_jls_dest"]
    if not isinstance(dest, str):
        _fail(f"anytls_jls_dest must be a string, got {type(dest).__name__}")
    dest = dest.strip()
    _split_host_port(dest, "anytls_jls_dest")
    return dest


def _jls_sni(config: dict[str, Any]) -> str:
    dest_host, _ = _split_host_port(_jls_dest(config), "anytls_jls_dest")
    sni = config["anytls_jls_sni"]
    if not isinstance(sni, str):
        _fail(f"anytls_jls_sni must be a string, got {type(sni).__name__}")
    sni = sni.strip() or dest_host
    if any(char.isspace() for char in sni) or ":" in sni:
        _fail(f"anytls_jls_sni must be a DNS name without whitespace or port, got {sni!r}")
    try:
        ipaddress.ip_address(sni)
    except ValueError:
        pass
    else:
        _fail(
            "anytls_jls_sni must be a DNS name, not an IP address; set "
            "anytls_jls_sni explicitly when anytls_jls_dest uses an IP host"
        )
    return sni


def _jls_alpn(config: dict[str, Any]) -> list[str]:
    alpn = config["anytls_jls_alpn"]
    if not isinstance(alpn, list) or not alpn:
        _fail("anytls_jls_alpn must be a non-empty list of protocol names")
    cleaned: list[str] = []
    for index, value in enumerate(alpn):
        if not isinstance(value, str) or not value.strip():
            _fail(f"anytls_jls_alpn[{index}] must be a non-empty string")
        value = value.strip()
        if any(char.isspace() for char in value):
            _fail(f"anytls_jls_alpn[{index}] must not contain whitespace, got {value!r}")
        cleaned.append(value)
    return cleaned


def _jls_users(config: dict[str, Any]) -> list[dict[str, Any]]:
    users = config["anytls_jls_users"]
    if not isinstance(users, list) or not users:
        _fail("anytls_jls_users must be a non-empty list when anytls_security_mode is jls")
    seen: set[str] = set()
    for index, user in enumerate(users):
        if not isinstance(user, dict):
            _fail(f"anytls_jls_users[{index}] must be a mapping")
        name = user.get("name")
        if not isinstance(name, str) or not name.strip():
            _fail(f"anytls_jls_users[{index}] requires a non-empty 'name'")
        if name in seen:
            _fail(f"anytls_jls_users[{index}] duplicates user name {name!r}")
        seen.add(name)
        password = user.get("password")
        if not isinstance(password, str) or not password.strip():
            _fail(f"anytls_jls_users[{index}] requires a non-empty 'password'")
    return users


def _validate_anytls_jls(config: dict[str, Any]) -> None:
    _jls_dest(config)
    _jls_sni(config)
    _jls_alpn(config)
    jls_names = {user["name"] for user in _jls_users(config)}
    missing = [user["name"] for user in _users(config, "anytls") if user["name"] not in jls_names]
    if missing:
        _fail(
            "anytls_security_mode is jls but anytls_jls_users has no credential for "
            f"AnyTLS user(s): {', '.join(missing)}"
        )
    _int_at_least(config, "anytls_jls_rate_limit", 0)


def _validate_anytls(config: dict[str, Any]) -> str:
    mode = _anytls_security_mode(config)
    if not _truthy(config["enable_anytls"]):
        if mode != "certificate":
            _fail("anytls_security_mode is jls but enable_anytls is false")
        return mode
    if mode == "jls":
        _validate_anytls_jls(config)
    return mode


def _padding_scheme(config: dict[str, Any]) -> str:
    scheme = config["anytls_padding_scheme"]
    if scheme is None:
        return ""
    if not isinstance(scheme, str):
        _fail(f"anytls_padding_scheme must be a string, got {type(scheme).__name__}")
    lines = [line.strip() for line in scheme.splitlines() if line.strip()]
    if not lines:
        return ""

    stop: int | None = None
    packets: set[int] = set()
    canonical: list[str] = []
    for line in lines:
        stop_match = re.fullmatch(r"stop\s*=\s*([0-9]+)", line)
        if stop_match:
            if stop is not None:
                _fail("anytls_padding_scheme must define stop= exactly once")
            stop = int(stop_match.group(1))
            canonical.append(f"stop={stop}")
            continue

        packet_match = re.fullmatch(r"([0-9]+)\s*=\s*(.+)", line)
        if not packet_match:
            _fail(f"anytls_padding_scheme has an invalid line: {line!r}")
        index = int(packet_match.group(1))
        if index in packets:
            _fail(f"anytls_padding_scheme defines packet {index} more than once")
        packets.add(index)

        rules = [rule.strip() for rule in packet_match.group(2).split(",")]
        if not rules or any(not rule for rule in rules):
            _fail(f"anytls_padding_scheme packet {index} has an empty rule")
        normalized: list[str] = []
        for rule in rules:
            if rule == "c":
                normalized.append("c")
                continue
            rule_match = re.fullmatch(r"([0-9]+)-([0-9]+)", rule)
            if not rule_match:
                _fail(f"anytls_padding_scheme packet {index} has an invalid rule {rule!r}; expected N-M or c")
            low, high = int(rule_match.group(1)), int(rule_match.group(2))
            if low <= 0 or high <= 0 or low > high:
                _fail(f"anytls_padding_scheme packet {index} has an invalid range {rule!r}; expected 1 <= min <= max")
            normalized.append(f"{low}-{high}")
        canonical.append(f"{index}={','.join(normalized)}")

    if stop is None:
        _fail("anytls_padding_scheme must define stop=N")
    for index in sorted(packets):
        if index >= stop:
            _fail(f"anytls_padding_scheme packet {index} is outside stop={stop}; packets at or above stop are ignored")
    return "\n".join(canonical)


def _validate_ports_unique(config: dict[str, Any], enabled: list[str]) -> None:
    ports: dict[int, str] = {}
    for protocol in enabled:
        port = config[f"{protocol}_port"]
        if port in ports:
            _fail(
                f"{protocol}_port {port} is already used by {ports[port]}; enabled listeners must bind distinct ports"
            )
        ports[port] = protocol

    extra = config["extra_listeners"]
    if not isinstance(extra, list):
        _fail("extra_listeners must be a list of listener mappings")
    for index, listener in enumerate(extra):
        port = listener.get("port") if isinstance(listener, dict) else None
        if isinstance(port, bool) or not isinstance(port, int):
            continue
        if port in ports:
            _fail(
                f"extra_listeners[{index}] port {port} is already used by "
                f"{ports[port]}; enabled listeners must bind distinct ports"
            )
        ports[port] = f"extra_listeners[{index}]"


def _build_listeners(config: dict[str, Any]) -> list[dict[str, Any]]:
    enabled = _enabled(config)
    _validate_ports_unique(config, enabled)

    listeners: list[dict[str, Any]] = []

    if "shadowsocks" in enabled:
        method = str(config["shadowsocks_method"]).strip()
        password = str(config["shadowsocks_password"]).strip()
        if not method:
            _fail("shadowsocks_method must not be empty")
        if not password:
            _fail("shadowsocks_password must not be empty (auto-generated by the role)")
        listeners.append(
            {
                "name": LISTENER_TAGS["shadowsocks"],
                "type": "shadowsocks",
                "listen": config["listen"],
                "port": config["shadowsocks_port"],
                "cipher": method,
                "password": password,
                "udp": True,
            }
        )

    if "trojan" in enabled:
        users = [{"username": user["name"], "password": user["password"]} for user in _users(config, "trojan")]
        listeners.append(
            {
                "name": LISTENER_TAGS["trojan"],
                "type": "trojan",
                "listen": config["listen"],
                "port": config["trojan_port"],
                "users": users,
                **_tls_fields(config),
            }
        )

    if "hysteria2" in enabled:
        listener: dict[str, Any] = {
            "name": LISTENER_TAGS["hysteria2"],
            "type": "hysteria2",
            "listen": config["listen"],
            "port": config["hysteria2_port"],
            "users": {user["name"]: user["password"] for user in _users(config, "hysteria2")},
        }
        up = config["hysteria2_up_mbps"]
        down = config["hysteria2_down_mbps"]
        if up or down:
            listener["up"] = up
            listener["down"] = down
            listener["ignore-client-bandwidth"] = False
        if _truthy(config["hysteria2_obfs_enabled"]):
            obfs_password = str(config["hysteria2_obfs_password"]).strip()
            if not obfs_password:
                _fail(
                    "hysteria2_obfs_enabled requires a non-empty hysteria2_obfs_password (auto-generated by the role)"
                )
            listener["obfs"] = "salamander"
            listener["obfs-password"] = obfs_password
        if _truthy(config["hysteria2_masquerade_enabled"]):
            listener["masquerade"] = config["hysteria2_masquerade_url"]
        listener["alpn"] = list(config["alpn"])
        listener.update(_tls_fields(config))
        listeners.append(listener)

    if "vless" in enabled:
        flow = str(config["vless_flow"]).strip()
        users: list[dict[str, Any]] = []
        for user in _users(config, "vless"):
            entry = {"username": user["name"], "uuid": user["uuid"]}
            if flow:
                entry["flow"] = flow
            users.append(entry)
        listener = {
            "name": LISTENER_TAGS["vless"],
            "type": "vless",
            "listen": config["listen"],
            "port": config["vless_port"],
            "users": users,
        }
        if _truthy(config["vless_reality_enabled"]):
            listener["reality-config"] = {
                "dest": _reality_dest(config),
                "private-key": str(config["vless_reality_private_key"]).strip(),
                "short-id": [_reality_short_id(config)],
                "server-names": _reality_server_names(config),
            }
        else:
            listener.update(_tls_fields(config))
        listeners.append(listener)

    if "tuic" in enabled:
        listeners.append(
            {
                "name": LISTENER_TAGS["tuic"],
                "type": "tuic",
                "listen": config["listen"],
                "port": config["tuic_port"],
                "users": {user["uuid"]: user["password"] for user in _users(config, "tuic")},
                "congestion-controller": config["tuic_congestion_control"],
                "alpn": list(config["alpn"]),
                **_tls_fields(config),
            }
        )

    if "anytls" in enabled:
        mode = _validate_anytls(config)
        listener = {
            "name": LISTENER_TAGS["anytls"],
            "type": "anytls",
            "listen": config["listen"],
            "port": config["anytls_port"],
            "users": {user["name"]: user["password"] for user in _users(config, "anytls")},
        }
        if mode == "jls":
            jls_config: dict[str, Any] = {
                "enable": True,
                "users": [{"username": user["name"], "password": user["password"]} for user in _jls_users(config)],
                "dest": _jls_dest(config),
                "sni": _jls_sni(config),
                "alpn": _jls_alpn(config),
            }
            rate_limit = _int_at_least(config, "anytls_jls_rate_limit", 0)
            if rate_limit:
                jls_config["rate-limit"] = rate_limit
            listener["jls-config"] = jls_config
        else:
            listener.update(_tls_fields(config))
        padding_scheme = _padding_scheme(config)
        if padding_scheme:
            listener["padding-scheme"] = padding_scheme
        listeners.append(listener)

    extra = config["extra_listeners"]
    if not isinstance(extra, list):
        _fail("extra_listeners must be a list of listener mappings")
    generated_names = [listener["name"] for listener in listeners]
    for index, listener in enumerate(extra):
        if not isinstance(listener, dict) or "name" not in listener or "type" not in listener:
            _fail(f"extra_listeners[{index}] requires 'name' and 'type'")
        if listener["name"] in generated_names:
            _fail(f"extra_listeners[{index}] name {listener['name']!r} is already used")
        generated_names.append(listener["name"])
        listeners.append(listener)
    return listeners


def mihomo_server_config(config: dict[str, Any] | None = None) -> dict[str, Any]:
    """Build the mihomo server configuration (``listeners`` schema).

    Args:
        config: mapping with ``enable_<protocol>`` / ``<protocol>_port`` /
            ``<protocol>_users`` / protocol options, plus ``log_level``,
            ``listen``, ``tls_certificate_path``, ``tls_key_path``,
            ``alpn``, ``external_controller`` and ``extra_listeners``.
            With ``vless_reality_enabled``, the vless listener uses
            ``vless_reality_dest``/``_private_key``/``_short_id``/
            ``_server_names`` instead of the certificate paths.  With
            ``anytls_security_mode: jls``, the anytls listener uses
            ``anytls_jls_dest``/``_sni``/``_alpn``/``_users`` and an optional
            ``_rate_limit`` instead of the certificate paths.

            ``anytls_padding_scheme`` is validated even though mihomo also
            validates it at listener startup; ``mihomo -t`` does not.

            Users use one uniform input shape for every protocol:
            ``[{name, password, uuid?}]`` - ``password`` is required for
            trojan/hysteria2/tuic/anytls, ``uuid`` for vless/tuic.  The
            output maps them to the per-protocol listener shape (shadowsocks
            itself is single-user and uses ``shadowsocks_password``).

    Returns:
        The server configuration mapping (``log-level``, ``listeners``,
        ``rules``, optional ``external-controller``).
    """
    c = _populate(
        config,
        log_level="warning",
        listen="0.0.0.0",
        enable_shadowsocks=True,
        shadowsocks_port=9442,
        shadowsocks_method="2022-blake3-aes-128-gcm",
        shadowsocks_password="",
        enable_trojan=False,
        trojan_port=9443,
        trojan_users=[],
        enable_hysteria2=True,
        hysteria2_port=9444,
        hysteria2_users=[],
        hysteria2_up_mbps=0,
        hysteria2_down_mbps=0,
        hysteria2_obfs_enabled=False,
        hysteria2_obfs_password="",
        hysteria2_masquerade_enabled=True,
        hysteria2_masquerade_url="https://www.bing.com",
        enable_vless=True,
        vless_port=9445,
        vless_users=[],
        vless_flow="xtls-rprx-vision",
        vless_reality_enabled=True,
        vless_reality_dest="www.microsoft.com:443",
        vless_reality_private_key="",
        vless_reality_public_key="",
        vless_reality_short_id="",
        vless_reality_server_names=[],
        vless_reality_client_fingerprint="chrome",
        enable_tuic=False,
        tuic_port=9446,
        tuic_users=[],
        tuic_congestion_control="bbr",
        enable_anytls=True,
        anytls_port=9447,
        anytls_users=[],
        anytls_security_mode="certificate",
        anytls_jls_dest="www.microsoft.com:443",
        anytls_jls_sni="",
        anytls_jls_alpn=["h2", "http/1.1"],
        anytls_jls_users=[],
        anytls_jls_rate_limit=0,
        anytls_padding_scheme="",
        tls_certificate_path="",
        tls_key_path="",
        external_controller="",
        external_controller_secret="",
        alpn=["h3"],
        extra_listeners=[],
    )

    alpn = c["alpn"]
    if not isinstance(alpn, list) or not alpn:
        _fail("alpn must be a non-empty list of protocol names")

    enabled = _enabled(c)
    for protocol in enabled:
        _validate_port(c, protocol)
    _validate_vless_reality(c)
    _validate_anytls(c)
    _validate_tls(c, enabled)
    listeners = _build_listeners(c)

    result: dict[str, Any] = {
        "log-level": c["log_level"],
        "listeners": listeners,
        "rules": ["MATCH,DIRECT"],
    }
    if c["external_controller"]:
        result["external-controller"] = c["external_controller"]
    if c["external_controller_secret"]:
        result["secret"] = c["external_controller_secret"]
    return result


def mihomo_server_client_proxies(
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the clash-format client nodes for a mihomo server.

    Node names follow the naming contract consumed by the client profile:
    ``<client_node_prefix>-<REGION>-<host>[-<user>]-<proto>`` - the
    ``selfhost`` prefix (default) and the region token (e.g. ``US``) are what
    make the node appear in the client's region groups; the optional
    selfhost-tier profile also uses the prefix for its ``*-自建`` groups.

    shadowsocks is single-user, so it emits exactly one ``-ss`` node using
    the server password; every other protocol emits one node per user.

    Hysteria2 bandwidth is deliberately **not** emitted on the client nodes:
    the ``up``/``down`` values on the server listener are per-client Brutal
    caps (server upload/download direction, not the client's), and copying
    them into the client made asymmetric links impossible to express and
    forced every client into Brutal at an arbitrary rate.  A client node
    without bandwidth lets mihomo fall back to BBR; clients that want Brutal
    set their own ``up``/``down`` in the client profile.

    AnyTLS nodes carry ``client-fingerprint`` and the idle-session knobs from
    the ``anytls_*`` keys; an empty fingerprint keeps mihomo's fallback to
    Go's standard-library TLS, which is rarely what a browser looks like.
    With ``anytls_security_mode: jls`` the node's ``sni`` is the JLS SNI (not
    the server hostname), ``alpn`` mirrors the JLS ALPN list, and the
    ``jls-opts`` credentials are the separate JLS user, matched to the AnyTLS
    user by name.

    Args:
        config: the server mapping (as for ``mihomo_server_config``) plus
            ``hostname``, ``region`` and ``client_node_prefix``.  With
            ``vless_reality_enabled``, the vless node carries
            ``reality-opts`` and uses the first
            ``vless_reality_server_names`` entry as its ``servername``.

    Returns:
        ``{"proxies": [...]}`` - the ``providers/selfhost.yaml`` artifact.
    """
    c = _populate(
        config,
        hostname="",
        region="",
        client_node_prefix="selfhost",
        enable_shadowsocks=True,
        shadowsocks_port=9442,
        shadowsocks_method="2022-blake3-aes-128-gcm",
        shadowsocks_password="",
        enable_trojan=False,
        trojan_port=9443,
        trojan_users=[],
        enable_hysteria2=True,
        hysteria2_port=9444,
        hysteria2_users=[],
        hysteria2_obfs_enabled=False,
        hysteria2_obfs_password="",
        enable_vless=True,
        vless_port=9445,
        vless_users=[],
        vless_flow="xtls-rprx-vision",
        vless_reality_enabled=True,
        vless_reality_dest="www.microsoft.com:443",
        vless_reality_public_key="",
        vless_reality_short_id="",
        vless_reality_server_names=[],
        vless_reality_client_fingerprint="chrome",
        enable_tuic=False,
        tuic_port=9446,
        tuic_users=[],
        tuic_congestion_control="bbr",
        enable_anytls=True,
        anytls_port=9447,
        anytls_users=[],
        anytls_security_mode="certificate",
        anytls_jls_dest="www.microsoft.com:443",
        anytls_jls_sni="",
        anytls_jls_alpn=["h2", "http/1.1"],
        anytls_jls_users=[],
        anytls_jls_rate_limit=0,
        anytls_client_fingerprint="chrome",
        anytls_idle_session_check_interval=30,
        anytls_idle_session_timeout=30,
        anytls_min_idle_session=0,
        alpn=["h3"],
    )

    hostname = str(c["hostname"]).strip()
    if not hostname:
        _fail("hostname is required to name the generated client nodes")
    region = str(c["region"]).strip()
    if not region or any(char.isspace() for char in region):
        _fail(
            f"region must be a non-empty token without whitespace that the "
            f"client region regex can match (e.g. 'US', 'HK'), got {region!r}"
        )
    client_node_prefix = str(c["client_node_prefix"]).strip()
    if not client_node_prefix:
        _fail("client_node_prefix must not be empty")
    server_short = hostname.split(".")[0]
    prefix = f"{client_node_prefix}-{region}-{server_short}"

    enabled = [name for name in PROTOCOLS if _truthy(c[f"enable_{name}"])]
    if not enabled:
        _fail("at least one protocol must be enabled")
    for protocol in enabled:
        _validate_port(c, protocol)
    anytls_mode = _validate_anytls(c)

    proxies: list[dict[str, Any]] = []

    if _truthy(c["enable_shadowsocks"]):
        password = str(c["shadowsocks_password"]).strip()
        if not password:
            _fail("shadowsocks_password must not be empty (auto-generated by the role)")
        proxies.append(
            {
                "name": f"{prefix}-ss",
                "type": "ss",
                "server": hostname,
                "port": c["shadowsocks_port"],
                "cipher": c["shadowsocks_method"],
                "password": password,
                "udp": True,
            }
        )

    if _truthy(c["enable_trojan"]):
        for user in _users(c, "trojan"):
            proxies.append(
                {
                    "name": f"{prefix}-{user['name']}-trojan",
                    "type": "trojan",
                    "server": hostname,
                    "port": c["trojan_port"],
                    "password": user["password"],
                    "udp": True,
                    "sni": hostname,
                    "skip-cert-verify": False,
                }
            )

    if _truthy(c["enable_hysteria2"]):
        for user in _users(c, "hysteria2"):
            proxy: dict[str, Any] = {
                "name": f"{prefix}-{user['name']}-hy2",
                "type": "hysteria2",
                "server": hostname,
                "port": c["hysteria2_port"],
                "password": user["password"],
                "sni": hostname,
                "skip-cert-verify": False,
            }
            if _truthy(c["hysteria2_obfs_enabled"]):
                proxy["obfs"] = "salamander"
                proxy["obfs-password"] = c["hysteria2_obfs_password"]
            proxy["alpn"] = list(c["alpn"])
            proxies.append(proxy)

    if _truthy(c["enable_vless"]):
        flow = str(c["vless_flow"]).strip()
        reality = _truthy(c["vless_reality_enabled"])
        if reality:
            _reality_dest(c)
            server_name = _reality_server_names(c)[0]
            short_id = _reality_short_id(c)
            public_key = str(c["vless_reality_public_key"]).strip()
            if not public_key:
                _fail("vless_reality_public_key must not be empty (generated by the role)")
            fingerprint = str(c["vless_reality_client_fingerprint"]).strip()
            if not fingerprint:
                _fail("vless_reality_client_fingerprint must not be empty")
        for user in _users(c, "vless"):
            proxy = {
                "name": f"{prefix}-{user['name']}-vless",
                "type": "vless",
                "server": hostname,
                "port": c["vless_port"],
                "uuid": user["uuid"],
                "tls": True,
                "udp": True,
            }
            if reality:
                proxy["servername"] = server_name
                proxy["client-fingerprint"] = fingerprint
                proxy["reality-opts"] = {
                    "public-key": public_key,
                    "short-id": short_id,
                }
            else:
                proxy["servername"] = hostname
                proxy["skip-cert-verify"] = False
            if flow:
                proxy["flow"] = flow
            proxies.append(proxy)

    if _truthy(c["enable_tuic"]):
        for user in _users(c, "tuic"):
            proxies.append(
                {
                    "name": f"{prefix}-{user['name']}-tuic",
                    "type": "tuic",
                    "server": hostname,
                    "port": c["tuic_port"],
                    "uuid": user["uuid"],
                    "password": user["password"],
                    "congestion-controller": c["tuic_congestion_control"],
                    "udp": True,
                    "sni": hostname,
                    "skip-cert-verify": False,
                    "alpn": list(c["alpn"]),
                }
            )

    if _truthy(c["enable_anytls"]):
        fingerprint = str(c["anytls_client_fingerprint"]).strip()
        if not fingerprint:
            _fail("anytls_client_fingerprint must not be empty")
        check_interval = _int_at_least(c, "anytls_idle_session_check_interval", 1)
        timeout = _int_at_least(c, "anytls_idle_session_timeout", 1)
        min_idle = _int_at_least(c, "anytls_min_idle_session", 0)
        jls_credentials: dict[str, str] = {}
        jls_sni = ""
        jls_alpn: list[str] = []
        if anytls_mode == "jls":
            jls_credentials = {user["name"]: user["password"] for user in _jls_users(c)}
            jls_sni = _jls_sni(c)
            jls_alpn = _jls_alpn(c)
        for user in _users(c, "anytls"):
            proxy: dict[str, Any] = {
                "name": f"{prefix}-{user['name']}-anytls",
                "type": "anytls",
                "server": hostname,
                "port": c["anytls_port"],
                "password": user["password"],
                "udp": True,
                "sni": hostname,
                "skip-cert-verify": False,
                "client-fingerprint": fingerprint,
                "idle-session-check-interval": check_interval,
                "idle-session-timeout": timeout,
                "min-idle-session": min_idle,
            }
            if anytls_mode == "jls":
                if user["name"] not in jls_credentials:
                    _fail(f"AnyTLS user {user['name']!r} has no matching anytls_jls_users credential")
                proxy["sni"] = jls_sni
                proxy["alpn"] = jls_alpn
                proxy["jls-opts"] = {
                    "username": user["name"],
                    "password": jls_credentials[user["name"]],
                }
            proxies.append(proxy)

    return {"proxies": proxies}


class FilterModule:
    """Ansible filter plugin registration for the mihomo server."""

    def filters(self) -> dict[str, Any]:
        return {
            "mihomo_server_config": mihomo_server_config,
            "mihomo_server_client_proxies": mihomo_server_client_proxies,
        }
