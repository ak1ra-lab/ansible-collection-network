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

TLS is manual certificate/key paths only (mihomo has no built-in ACME), so
``mihomo_server_config`` validates that every TLS-using listener has both
paths set.
"""

from __future__ import annotations

from typing import Any

from ansible.errors import AnsibleFilterError

# Fixed listener order and the per-protocol facts the generation branches on.
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


def _fail(message: str) -> None:
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


def _validate_tls(config: dict[str, Any], enabled: list[str]) -> None:
    needs_tls = [name for name in enabled if name in TLS_PROTOCOLS]
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
        listeners.append(
            {
                "name": LISTENER_TAGS["vless"],
                "type": "vless",
                "listen": config["listen"],
                "port": config["vless_port"],
                "users": users,
                **_tls_fields(config),
            }
        )

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
        listener = {
            "name": LISTENER_TAGS["anytls"],
            "type": "anytls",
            "listen": config["listen"],
            "port": config["anytls_port"],
            "users": {user["name"]: user["password"] for user in _users(config, "anytls")},
            **_tls_fields(config),
        }
        padding_scheme = str(config["anytls_padding_scheme"]).strip()
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
        shadowsocks_port=8388,
        shadowsocks_method="2022-blake3-aes-128-gcm",
        shadowsocks_password="",
        enable_trojan=False,
        trojan_port=8443,
        trojan_users=[],
        enable_hysteria2=False,
        hysteria2_port=8845,
        hysteria2_users=[],
        hysteria2_up_mbps=1000,
        hysteria2_down_mbps=1000,
        hysteria2_obfs_enabled=False,
        hysteria2_obfs_password="",
        hysteria2_masquerade_enabled=True,
        hysteria2_masquerade_url="https://www.bing.com",
        enable_vless=False,
        vless_port=8444,
        vless_users=[],
        vless_flow="",
        enable_tuic=False,
        tuic_port=8846,
        tuic_users=[],
        tuic_congestion_control="bbr",
        enable_anytls=False,
        anytls_port=8447,
        anytls_users=[],
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
    make the node appear in the ``*-自建`` and region groups.

    shadowsocks is single-user, so it emits exactly one ``-ss`` node using
    the server password; every other protocol emits one node per user.

    Hysteria2 bandwidth is deliberately **not** emitted on the client nodes:
    the ``up``/``down`` values on the server listener are per-client Brutal
    caps (server upload/download direction, not the client's), and copying
    them into the client made asymmetric links impossible to express and
    forced every client into Brutal at an arbitrary rate.  A client node
    without bandwidth lets mihomo fall back to BBR; clients that want Brutal
    set their own ``up``/``down`` in the client profile.

    Args:
        config: the server mapping (as for ``mihomo_server_config``) plus
            ``hostname``, ``region`` and ``client_node_prefix``.

    Returns:
        ``{"proxies": [...]}`` - the ``providers/selfhost.yaml`` artifact.
    """
    c = _populate(
        config,
        hostname="",
        region="",
        client_node_prefix="selfhost",
        enable_shadowsocks=False,
        shadowsocks_port=8388,
        shadowsocks_method="2022-blake3-aes-128-gcm",
        shadowsocks_password="",
        enable_trojan=False,
        trojan_port=8443,
        trojan_users=[],
        enable_hysteria2=False,
        hysteria2_port=8845,
        hysteria2_users=[],
        hysteria2_obfs_enabled=False,
        hysteria2_obfs_password="",
        enable_vless=False,
        vless_port=8444,
        vless_users=[],
        vless_flow="",
        enable_tuic=False,
        tuic_port=8846,
        tuic_users=[],
        tuic_congestion_control="bbr",
        enable_anytls=False,
        anytls_port=8447,
        anytls_users=[],
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
        for user in _users(c, "vless"):
            proxy = {
                "name": f"{prefix}-{user['name']}-vless",
                "type": "vless",
                "server": hostname,
                "port": c["vless_port"],
                "uuid": user["uuid"],
                "tls": True,
                "udp": True,
                "servername": hostname,
                "skip-cert-verify": False,
            }
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
        for user in _users(c, "anytls"):
            proxies.append(
                {
                    "name": f"{prefix}-{user['name']}-anytls",
                    "type": "anytls",
                    "server": hostname,
                    "port": c["anytls_port"],
                    "password": user["password"],
                    "udp": True,
                    "sni": hostname,
                    "skip-cert-verify": False,
                }
            )

    return {"proxies": proxies}


class FilterModule:
    """Ansible filter plugin registration for the mihomo server."""

    def filters(self) -> dict[str, Any]:
        return {
            "mihomo_server_config": mihomo_server_config,
            "mihomo_server_client_proxies": mihomo_server_client_proxies,
        }
