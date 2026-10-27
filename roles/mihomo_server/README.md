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
- TLS is flat `certificate` / `private-key` paths on the certificate-using
  listeners; vless with REALITY uses `reality-config` instead, and anytls
  with JLS uses `jls-config`.  mihomo has **no built-in ACME**: certificates
  are provisioned out of band.  The role can either reference an
  operator-managed pair in place (manual mode) or copy an external source
  pair into a service-readable location and install an optional certbot
  renewal hook (see [TLS material](#tls-material)).

The role does not manage a firewall or cloud security groups: open the
enabled ports (`mihomo_server_*_port`) yourself.

## Requirements

- A systemd-based Linux VPS (the binary is deployed as a static `.gz` archive
  by `ak1ra_lab.network.mihomo_install`).
- A TLS certificate/key pair for every certificate-using protocol
  (trojan/hysteria2/tuic/anytls, and vless when REALITY is disabled) - see
  `mihomo_server_tls_certificate_path` / `_key_path`.  The role can copy an
  external source pair into a service-readable location, which is required
  for certbot's root-only `live/` paths.  The default vless REALITY listener
  does not need its own certificate, and AnyTLS with
  `mihomo_server_anytls_security_mode: jls` replaces its certificate with the
  JLS layer.
- For JLS: mihomo **>= 1.19.29** on both ends, a stable TLS destination with
  a certificate the generated mihomo clients trust, and a DNS `jls_sni`
  matching that certificate.  The JLS node is mihomo-only (the role's
  `mihomo_client` output); other clients cannot use it.
- A DNS name pointing at the VPS and a region token the client's region
  regex can match (`mihomo_server_region`, e.g. `US`, `HK`, `JP`).
- Control node: `ak1ra_lab.general` (>= 0.2.0) for `github_releases_info`
  (installed from git, not published to Galaxy; see the collection README).
  The optional certbot integration also needs the
  `ak1ra_lab.general.certbot` role from general >= 0.3.0.

## What it deploys

| Artifact | Purpose |
| --- | --- |
| `/usr/local/bin/mihomo` | mihomo binary, deployed by `mihomo_install` (playbook) |
| `/etc/mihomo/config.yaml` | server configuration (`listeners` + `rules: [MATCH,DIRECT]`) |
| `/etc/systemd/system/mihomo.service` | service unit (`ExecStartPre` config test) |
| `/etc/mihomo/tls/{fullchain,privkey}.pem` | role-managed copies when a source pair is configured (`0640 root:mihomo`) |
| `/etc/letsencrypt/renewal-hooks/deploy/mihomo-server.sh` | optional certbot renewal hook (role-managed, independent of the certbot role's dispatcher) |
| `<repo>/config/client_outbounds/<host>.proxies.yaml` | clash-format client nodes for `mihomo_client` |
| `<repo>/config/client_outbounds/<host>.config.yaml` | exact copy of the deployed server config |
| `<playbook>/host_vars/<host>/mihomo_server.yaml` | generated credentials (0600) |

The two `config/client_outbounds/` files and the `host_vars` file are
written on the controller; commit them only on a private branch (they carry
credentials) or keep them uncommitted.

## Default profile

The defaults enable four complementary listeners:

- `shadowsocks` - certificate-free fallback, TCP and UDP, supported by
  nearly every client;
- `vless` with REALITY and XTLS Vision - TCP primary; the listener borrows
  a real site's TLS handshake and needs no certificate of its own;
- `hysteria2` - QUIC/UDP fast path for lossy or high-RTT links; the role
  leaves the server bandwidth unset, so clients use BBR unless they opt
  into Brutal;
- `anytls` - TLS/TCP fallback designed to reduce the TLS-in-TLS packet
  length and timing fingerprint.

`trojan` and `tuic` are opt-in.  All six protocol switches remain
available; the default profile is a recommendation, not a restriction.
Ports are role defaults, not protocol conventions: the `9442-9447` block
avoids the historical shadowsocks `8388` / alt-HTTPS `8443` values and keeps
the listeners easy to enumerate.

## Naming contract for the generated nodes

```
<prefix>-<REGION>-<host-label>[-<user>]-<proto>
```

e.g. `selfhost-US-node01-ss` (shadowsocks is single-user, so no
user segment) and `selfhost-US-node01-alice-trojan`.  The prefix
(`mihomo_server_client_node_prefix`, default `selfhost`) plus the region
token are what make the node appear in the client's region groups; the
client's optional selfhost-tier profile additionally uses the prefix for
its `*-自建` groups.  `<host-label>` is the first DNS label of
`mihomo_server_hostname` (hosts sharing a first label produce colliding
node names).

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
| `mihomo_server_shadowsocks_port` | `9442` | Single-user ss listener port |
| `mihomo_server_shadowsocks_method` | `2022-blake3-aes-128-gcm` | Cipher; 2022-blake3 ciphers get an exact-length base64 key, classic ciphers a 32-char passphrase |
| `mihomo_server_shadowsocks_password` | `""` | Server password (base64); generated when empty |
| `mihomo_server_enable_trojan` | `false` | trojan listener switch (opt-in legacy TLS/TCP) |
| `mihomo_server_trojan_port` | `9443` | Port |
| `mihomo_server_trojan_users` | `[]` | `[{name, password}]`; generated when empty |
| `mihomo_server_enable_hysteria2` | `true` | hysteria2 listener switch |
| `mihomo_server_hysteria2_port` | `9444` | Port |
| `mihomo_server_hysteria2_users` | `[]` | `[{name, password}]`; generated when empty |
| `mihomo_server_hysteria2_up_mbps` / `_down_mbps` | `0` / `0` | Server-side Brutal caps in Mbps (`0` omits them). Generated client nodes never carry bandwidth, so clients use BBR unless they set their own; these caps only apply when a client opts into Brutal |
| `mihomo_server_hysteria2_obfs_enabled` / `_obfs_password` | `false` / `""` | salamander obfuscation (password generated when enabled and empty) |
| `mihomo_server_hysteria2_masquerade_enabled` / `_url` | `true` / bing.com | HTTP/3 masquerade |
| `mihomo_server_enable_vless` | `true` | vless listener switch |
| `mihomo_server_vless_port` | `9445` | Port |
| `mihomo_server_vless_users` | `[]` | `[{name, uuid}]`; generated when empty |
| `mihomo_server_vless_flow` | `xtls-rprx-vision` | Per-user `flow`; set `""` for plain vless |
| `mihomo_server_vless_reality_enabled` | `true` | Use `reality-config` instead of certificate/key for the vless listener |
| `mihomo_server_vless_reality_dest` | `www.microsoft.com:443` | Borrowed TLS 1.3 site (`host:port`) |
| `mihomo_server_vless_reality_private_key` / `_public_key` | `""` | X25519 keypair; generated on the target when both are empty and persisted to host_vars |
| `mihomo_server_vless_reality_short_id` | `""` | Even-length hex (2-16 chars); generated when empty |
| `mihomo_server_vless_reality_server_names` | `[]` | Accepted SNI list; defaults to the dest host when empty |
| `mihomo_server_vless_reality_client_fingerprint` | `chrome` | uTLS fingerprint on the generated client node |
| `mihomo_server_enable_tuic` | `false` | tuic (v5) listener switch |
| `mihomo_server_tuic_port` | `9446` | Port |
| `mihomo_server_tuic_users` | `[]` | `[{name, uuid, password}]`; generated when empty |
| `mihomo_server_tuic_congestion_control` | `bbr` | Congestion controller |
| `mihomo_server_enable_anytls` | `true` | anytls listener switch (TLS/TCP) |
| `mihomo_server_anytls_port` | `9447` | Port |
| `mihomo_server_anytls_users` | `[]` | `[{name, password}]`; generated when empty |
| `mihomo_server_anytls_security_mode` | `certificate` | `certificate` (certificate/private-key, no listener fallback) or `jls` (JLS outer TLS with a `dest` fallback) |
| `mihomo_server_anytls_jls_dest` | `www.microsoft.com:443` | JLS fallback TLS destination; authenticated traffic does not dial it |
| `mihomo_server_anytls_jls_sni` | `""` | JLS SNI; empty derives the dest host. Must be a DNS name matching the dest certificate |
| `mihomo_server_anytls_jls_alpn` | `[h2, http/1.1]` | JLS outer ALPN; the generated client node mirrors it |
| `mihomo_server_anytls_jls_users` | `[]` | `[{name, password}]`; independent second credential, generated per AnyTLS user when empty |
| `mihomo_server_anytls_jls_rate_limit` | `0` | Fallback forwarding limit in bit/s; `0` is unlimited |
| `mihomo_server_anytls_padding_scheme` | `""` | Optional padding scheme; empty uses mihomo's default scheme. Custom schemes are validated before rendering |
| `mihomo_server_anytls_client_fingerprint` | `chrome` | Client uTLS fingerprint; empty falls back to Go's standard-library TLS fingerprint |
| `mihomo_server_anytls_idle_session_check_interval` | `30` | Client idle-session check interval (seconds) |
| `mihomo_server_anytls_idle_session_timeout` | `30` | Client idle-session timeout (seconds) |
| `mihomo_server_anytls_min_idle_session` | `0` | Client idle sessions kept warm (`0` disables the reserved pool) |
| `mihomo_server_extra_listeners` | `[]` | Raw additional listeners appended after the generated ones |
| `mihomo_server_tls_dir` | `/etc/mihomo/tls` | Destination directory for role-managed copies |
| `mihomo_server_tls_certificate_path` / `_key_path` | derived from `_tls_dir` when a source pair is set, otherwise `""` | Listener paths; manual mode points at an existing pair readable by the mihomo user |
| `mihomo_server_tls_source_certificate_path` / `_key_path` | `""` | Optional source pair; set both to let the role copy it into the destination paths |
| `mihomo_server_tls_certbot_enabled` | `false` | Collection-playbook switch: apply certbot first and derive the source pair |
| `mihomo_server_tls_renewal_hook_enabled` | `mihomo_server_tls_certbot_enabled` | Install a certbot deploy hook that re-copies the source pair and reloads mihomo |
| `mihomo_server_tls_renewal_hook_path` | `/etc/letsencrypt/renewal-hooks/deploy/mihomo-server.sh` | Renewal hook path |
| `mihomo_server_alpn` | `[h3]` | ALPN for hysteria2/tuic listeners (and their generated client nodes) |
| `mihomo_server_client_node_prefix` | `selfhost` | Prefix of the generated client node names |
| `mihomo_server_local_artifacts_dir` | `<playbook>/../config/client_outbounds` | Controller-local artifacts directory |
| `mihomo_server_host_vars_file` | `<playbook>/host_vars/<host>/mihomo_server.yaml` | Generated credentials file |

Internal derived values (enumeration lists) live in `vars/main.yaml` and are
not meant to be overridden.  The service identity and paths
(`mihomo_server_user` / `_group` / `_etc_dir` / `_binary`, the same names on
`mihomo_client`) live there as role conventions - override them with role
params or `-e` if they really must differ.

## TLS material

**Manual mode (default).** Set `mihomo_server_tls_certificate_path` and
`mihomo_server_tls_key_path` to an existing certificate/key pair readable by
the `mihomo` user; the role only references the paths in the listeners.

**External source pair.** Set both `mihomo_server_tls_source_certificate_path`
and `mihomo_server_tls_source_key_path`.  The role then:

- ensures `mihomo_server_tls_dir` (`0750 root:mihomo`);
- copies the pair to `mihomo_server_tls_certificate_path` /
  `mihomo_server_tls_key_path` (`0640 root:mihomo`) on every apply,
  restarting mihomo only when the content changes;
- optionally installs a certbot deploy hook via
  `mihomo_server_tls_renewal_hook_enabled`.

This is the certbot integration point: `/etc/letsencrypt/live/` is
`0700 root:root`, so the service cannot read it in place.  Point the source
paths at the lineage and enable the hook:

```yaml
mihomo_server_tls_source_certificate_path: /etc/letsencrypt/live/node01.example.com/fullchain.pem
mihomo_server_tls_source_key_path: /etc/letsencrypt/live/node01.example.com/privkey.pem
mihomo_server_tls_renewal_hook_enabled: true
```

The hook is `/etc/letsencrypt/renewal-hooks/deploy/mihomo-server.sh`; certbot
runs every executable in that directory, so it coexists with the certbot
role's own `certbot-deploy-hooks.sh`.  Do not configure
`certbot_deploy_hooks` for mihomo.  The hook only covers `certbot renew`; the
role's copy task remains responsible for the initial issuance and for any
manual re-run, so the destination files always exist before the service
starts or restarts.

The collection playbook can perform the certbot invocation: set
`mihomo_server_tls_certbot_enabled: true` and provide the normal `certbot_*`
contract (`certbot_email`, `certbot_certificates`, challenge/provider).  The
playbook applies `ak1ra_lab.general.certbot` before this role and derives the
source paths and hook path from `mihomo_server_tls_certbot_config_dir` /
`_lineage`; it does not override `certbot_certificates`, so other certificates
on the same host keep their own hooks.  The lineage defaults to
`mihomo_server_hostname` (or the gathered fqdn); set
`mihomo_server_tls_certbot_lineage` for a custom cert name (for example a
wildcard lineage).  An explicit `mihomo_server_tls_source_*` pair always wins
over the derived `live/` paths.

### VLESS REALITY

Both `mihomo_server_enable_vless` and
`mihomo_server_vless_reality_enabled` are true in the default profile.  Set
them together to switch the vless listener from certificate TLS to REALITY.
REALITY borrows the TLS handshake of
`mihomo_server_vless_reality_dest` (default `www.microsoft.com:443`), so the
VLESS listener needs no certificate of its own.  The role:

- generates the X25519 keypair on the target with
  `mihomo generate reality-keypair` when both key variables are empty;
- generates a 16-character hex short ID when
  `mihomo_server_vless_reality_short_id` is empty;
- persists the private key, public key and short ID to the host_vars
  credential file (mode `0600`), so repeated runs reuse them;
- emits `reality-config` on the server listener and `reality-opts` on the
  generated client node.  `servername` becomes the first entry of
  `mihomo_server_vless_reality_server_names` (or the dest host when the list
  is empty), and `client-fingerprint` defaults to `chrome`.

`xtls-rprx-vision` is the recommended `mihomo_server_vless_flow` value with
REALITY.  Certificate paths are still required when any other
certificate-using protocol (trojan/hysteria2/tuic, or anytls in
`certificate` mode) is enabled.

### AnyTLS

The generated AnyTLS client node sets `client-fingerprint` (default
`chrome`) and the idle-session knobs.  Leaving
`mihomo_server_anytls_client_fingerprint` empty makes mihomo use Go's
standard-library TLS fingerprint, which is a weaker match for browser
traffic.  A positive `mihomo_server_anytls_min_idle_session` keeps warm
sessions on high-RTT links at the cost of keeping connections open.  AnyTLS
has no REALITY support; keep it as a TLS/TCP fallback rather than a REALITY
replacement.

#### Certificate mode (default)

`mihomo_server_anytls_security_mode: certificate` emits the flat
`certificate`/`private-key` fields.  The listener has no fallback: a failed
AnyTLS authentication closes the connection.  This is the only mode usable by
non-mihomo AnyTLS clients.

#### JLS mode

`mihomo_server_anytls_security_mode: jls` replaces the anytls listener's
certificate with a JLS outer TLS layer:

- the server emits `jls-config` (`users`, `dest`, `sni`, `alpn`, optional
  `rate-limit`) and keeps the AnyTLS `users` map; the two are separate
  credential layers;
- unauthenticated probes are relayed to `jls_dest`; authenticated clients
  never dial it;
- the generated client node uses `sni: <jls_sni>` (not
  `mihomo_server_hostname`), `alpn: <jls_alpn>`, and
  `jls-opts: {username, password}`;
- `mihomo_server_anytls_jls_users` is generated one-per-AnyTLS-user and
  persisted to host_vars; passwords are independent from the AnyTLS passwords;
- do not add `tls: true` to the node (AnyTLS is always TLS and mihomo ignores
  the field);
- `skip-cert-verify` is **not** applied to the JLS fallback; `jls_dest` must
  present a certificate the client trusts and a SAN matching `jls_sni`;
- JLS and ECH are mutually exclusive; ECH is not implemented by this role yet;
- it requires mihomo >= 1.19.29 on both ends and is mihomo-only.  Changing
  `security_mode` replaces the listener and is not backward compatible with
  old clients; plan a maintenance window or a parallel listener/host.

`jls_dest` being temporarily unreachable does not break authenticated traffic,
but it disables the probe fallback.  `jls_rate_limit` only limits fallback
forwarding, in bit/s.

#### Padding

Leaving `mihomo_server_anytls_padding_scheme` empty uses mihomo's default
scheme.  A custom scheme is pushed to mihomo/sing-anytls clients through
`cmdUpdatePaddingScheme`; the first session still uses the client's default
scheme for its early packets.  The role validates the scheme syntax before
rendering because `mihomo -t` does not check listener runtime parameters.
Custom padding changes packet shape only; it does not hide SNI or fix the
TLS-in-TLS/timing weaknesses described by the AnyTLS FAQ.

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

Removed: `/etc/mihomo/config.yaml`, the unit and the optional certbot renewal
hook (the service is stopped and disabled first).

Deliberately left in place: the binary, the TLS source pair and the
role-managed copies, the certbot lineage (`/etc/letsencrypt`), the subscribed
data (none), and the controller-local artifacts (`config/client_outbounds/`,
`host_vars`) - remove those manually when the credentials are no longer
needed.

## Companion roles

- `ak1ra_lab.network.mihomo_install` deploys the binary (applied by
  `playbooks/mihomo_server.yaml`);
- `ak1ra_lab.network.mihomo_client` consumes the generated client nodes
  through `mihomo_client_selfhost_files` (validated against the naming
  contract before the play writes `providers/selfhost.yaml`).
