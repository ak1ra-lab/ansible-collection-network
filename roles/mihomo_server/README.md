# ak1ra_lab.network.mihomo_server

Deploys [mihomo](https://github.com/MetaCubeX/mihomo) on a VPS as a proxy
server and produces the client artifacts consumed by
`ak1ra_lab.network.mihomo_client`:

- inbound listeners (`listeners:` schema) for shadowsocks, trojan,
  hysteria2, vless, tuic and anytls, plus a raw `mihomo_server_extra_listeners`
  escape hatch;
- auto-generated credentials (user pool, cipher-aware base64 secrets, RFC
  4122 UUIDs) persisted to `playbooks/host_vars/<host>/mihomo_server.yaml`
  (mode 0600), where Ansible auto-loads them on later runs; only variables
  still left empty are generated (with the `ak1ra_lab.network.random_*`
  lookup plugins, control-node CSPRNG), and explicit non-empty variables
  always win;
- clash-format client nodes written to
  `config/client_outbounds/<host>.proxies.yaml`, ready to feed the client's
  `providers/selfhost.yaml` through `mihomo_client_selfhost_files`.

The role owns the service identity (`mihomo` user/group), the listeners
configuration, the systemd unit and the service.  The binary is deployed by
`ak1ra_lab.network.mihomo_install`, which `playbooks/mihomo_server.yaml`
applies before this role (the `mihomo_install_*` contract: version policy
`present` / `latest` / pinned, amd64 microarchitecture-aware).

mihomo schema facts the contract is built on:

- the shadowsocks listener is **single-user** (one cipher + password, no
  `users` field), so there is no `mihomo_server_shadowsocks_users`;
- trojan takes a `users` list, hysteria2/tuic/anytls a name/uuid -> password
  mapping - the role declares users in one uniform shape
  (`{name, password, uuid?}`) and the filter plugin maps them;
- TLS is flat `certificate` / `private-key` paths on every TLS-using
  listener, and mihomo has **no built-in ACME**: certificates are
  provisioned out of band (manual mode) and only referenced here.

The role does not manage a firewall or cloud security groups: open the
enabled ports (`mihomo_server_*_port`) yourself.

## Requirements

- A systemd-based Linux VPS (the binary is deployed as a static `.gz` archive
  by `ak1ra_lab.network.mihomo_install`).
- A TLS certificate/key pair for every TLS-using protocol
  (trojan/hysteria2/vless/tuic/anytls) - see
  `mihomo_server_tls_certificate_path` / `_key_path`.
- A DNS name pointing at the VPS and a region token the client's region
  regex can match (`mihomo_server_region`, e.g. `US`, `HK`, `JP`).
- Control node: `ak1ra_lab.general` (>= 0.2.0) for `github_releases_info`
  (installed from git, not published to Galaxy; see the collection README).

## What it deploys

| Artifact | Purpose |
| --- | --- |
| `/usr/local/bin/mihomo` | mihomo binary, deployed by `mihomo_install` (playbook) |
| `/etc/mihomo/config.yaml` | server configuration (`listeners` + `rules: [MATCH,DIRECT]`) |
| `/etc/systemd/system/mihomo.service` | service unit (`ExecStartPre` config test) |
| `<repo>/config/client_outbounds/<host>.proxies.yaml` | clash-format client nodes for `mihomo_client` |
| `<repo>/config/client_outbounds/<host>.config.yaml` | exact copy of the deployed server config |
| `<playbook>/host_vars/<host>/mihomo_server.yaml` | generated credentials (0600) |

The two `config/client_outbounds/` files and the `host_vars` file are
written on the controller; commit them only on a private branch (they carry
credentials) or keep them uncommitted.

## Naming contract for the generated nodes

```
<prefix>-<REGION>-<host-label>[-<user>]-<proto>
```

e.g. `selfhost-US-node01-ss` (shadowsocks is single-user, so no
user segment) and `selfhost-US-node01-alice-trojan`.  The prefix
(`mihomo_server_client_node_prefix`, default `selfhost`) plus the region
token are what make the node appear in the client's `*-自建` and region
groups; `<host-label>` is the first DNS label of `mihomo_server_hostname`
(hosts sharing a first label produce colliding node names).

## Variable contract

| Variable | Default | Description |
| --- | --- | --- |
| `mihomo_server_state` | `present` | `present` applies, `absent` tears the role-managed artifacts down |
| `mihomo_server_hostname` | `ansible_facts.fqdn` | Server address + TLS SNI |
| `mihomo_server_region` | `""` | Required region token for the client node names |
| `mihomo_server_log_level` | `warning` | `log-level` |
| `mihomo_server_listen` | `0.0.0.0` | Listener bind address |
| `mihomo_server_external_controller` | `""` | Optional Clash API on the server |
| `mihomo_server_external_controller_secret` | `""` | API secret (`secret`) when the controller is exposed |
| `mihomo_server_user_count` | `1` | Auto-generated users (1-10, first N of the pool) |
| `mihomo_server_enable_shadowsocks` | `true` | shadowsocks listener switch |
| `mihomo_server_shadowsocks_port` | `8388` | Single-user ss listener port |
| `mihomo_server_shadowsocks_method` | `2022-blake3-aes-128-gcm` | Cipher; 2022-blake3 ciphers get an exact-length base64 key, classic ciphers a 32-char passphrase |
| `mihomo_server_shadowsocks_password` | `""` | Server password (base64); generated when empty |
| `mihomo_server_enable_trojan` | `true` | trojan listener switch |
| `mihomo_server_trojan_port` | `8443` | Port |
| `mihomo_server_trojan_users` | `[]` | `[{name, password}]`; generated when empty |
| `mihomo_server_enable_hysteria2` | `true` | hysteria2 listener switch |
| `mihomo_server_hysteria2_port` | `8845` | Port |
| `mihomo_server_hysteria2_users` | `[]` | `[{name, password}]`; generated when empty |
| `mihomo_server_hysteria2_up_mbps` / `_down_mbps` | `1000` / `1000` | Bandwidth hints (each `0` hint is omitted from the client nodes) |
| `mihomo_server_hysteria2_obfs_enabled` / `_obfs_password` | `false` / `""` | salamander obfuscation (password generated when enabled and empty) |
| `mihomo_server_hysteria2_masquerade_enabled` / `_url` | `true` / bing.com | HTTP/3 masquerade |
| `mihomo_server_enable_vless` | `false` | vless listener switch |
| `mihomo_server_vless_port` | `8444` | Port |
| `mihomo_server_vless_users` | `[]` | `[{name, uuid}]`; generated when empty |
| `mihomo_server_vless_flow` | `""` | Optional per-user `flow` (e.g. `xtls-rprx-vision`) |
| `mihomo_server_enable_tuic` | `false` | tuic (v5) listener switch |
| `mihomo_server_tuic_port` | `8846` | Port |
| `mihomo_server_tuic_users` | `[]` | `[{name, uuid, password}]`; generated when empty |
| `mihomo_server_tuic_congestion_control` | `bbr` | Congestion controller |
| `mihomo_server_enable_anytls` | `false` | anytls listener switch |
| `mihomo_server_anytls_port` | `8447` | Port |
| `mihomo_server_anytls_users` | `[]` | `[{name, password}]`; generated when empty |
| `mihomo_server_anytls_padding_scheme` | `""` | Optional padding scheme |
| `mihomo_server_extra_listeners` | `[]` | Raw additional listeners appended after the generated ones |
| `mihomo_server_tls_certificate_path` / `_key_path` | `""` | Required for TLS-using protocols (manual mode) |
| `mihomo_server_alpn` | `[h3]` | ALPN for hysteria2/tuic listeners (and their generated client nodes) |
| `mihomo_server_client_node_prefix` | `selfhost` | Prefix of the generated client node names |
| `mihomo_server_local_artifacts_dir` | `<playbook>/../config/client_outbounds` | Controller-local artifacts directory |
| `mihomo_server_host_vars_file` | `<playbook>/host_vars/<host>/mihomo_server.yaml` | Generated credentials file |

Internal derived values (enumeration lists) live in `vars/main.yaml` and are
not meant to be overridden.  The service identity and paths
(`mihomo_server_user` / `_group` / `_etc_dir` / `_binary`, the same names on
`mihomo_client`) live there as role conventions - override them with role
params or `-e` if they really must differ.

## Example playbook

The supported entry point is the collection playbook, which installs the
binary first and then applies this role:

```shell
ansible-playbook ak1ra_lab.network.mihomo_server -e mihomo_install_version=latest
```

Applying the roles directly:

```yaml
- name: mihomo proxy server
  hosts: mihomo-server
  become: true
  gather_facts: true
  roles:
    - role: ak1ra_lab.network.mihomo_install
      vars:
        mihomo_install_restart_handler: systemctl restart mihomo.service
    - role: ak1ra_lab.network.mihomo_server
      vars:
        mihomo_server_hostname: node01.example.com
        mihomo_server_region: US
        mihomo_server_user_count: 2
        mihomo_server_enable_vless: true
        mihomo_server_tls_certificate_path: /etc/mihomo/tls/fullchain.pem
        mihomo_server_tls_key_path: /etc/mihomo/tls/privkey.pem
```

The client side then references the generated artifact:

```yaml
mihomo_client_selfhost_files:
  - "{{ playbook_dir }}/../config/client_outbounds/node01.proxies.yaml"
```

## Declarative teardown: `mihomo_server_state: absent`

Removed: `/etc/mihomo/config.yaml` and the unit (the service is stopped and
disabled first).

Deliberately left in place: the binary, the TLS certificate/key files, the
subscribed data (none), and the controller-local artifacts
(`config/client_outbounds/`, `host_vars`) - remove those manually when the
credentials are no longer needed.

## Companion roles

- `ak1ra_lab.network.mihomo_install` deploys the binary (applied by
  `playbooks/mihomo_server.yaml`);
- `ak1ra_lab.network.mihomo_client` consumes the generated client nodes
  through `mihomo_client_selfhost_files` (validated against the naming
  contract before the play writes `providers/selfhost.yaml`).
