# ak1ra_lab.network.mihomo_server

> The canonical variable reference is generated from
> [`meta/argument_specs.yml`](meta/argument_specs.yml) in the
> [collection documentation](https://ak1ra-lab.github.io/ansible-collection-network/collection_index.html).
> This README keeps purpose, requirements, deployed artifacts,
> protocol behavior, examples, and teardown notes.

Deploys [mihomo](https://github.com/MetaCubeX/mihomo) on a VPS as a proxy
server and produces the client artifacts consumed by
`ak1ra_lab.network.mihomo_client`:

- inbound listeners (`listeners:` schema) for shadowsocks, trojan,
  hysteria2, vless, tuic and anytls, plus a raw extra-listeners escape hatch;
- auto-generated credentials (user pool, cipher-aware base64 secrets, RFC
  4122 UUIDs) persisted to `inventory/host_vars/<host>/mihomo_server.yaml`
  (mode 0600), where Ansible auto-loads them on later runs when the path is
  inventory- or playbook-adjacent; only empty variables are generated (with
  the `ak1ra_lab.general.random_*` lookups, control-node CSPRNG), and
  explicit non-empty variables always win;
- clash-format client nodes written to
  `config/client_outbounds/<host>.proxies.yaml`, ready to feed the client's
  `providers/selfhost.yaml` through `mihomo_client_selfhost_files`.

The role owns the service identity (`mihomo` user/group), the listeners
configuration, the systemd unit and the service.  The binary is deployed by
`ak1ra_lab.network.mihomo_install`, which the consumer composition in
`ansible-playbooks-services` applies before this role.

mihomo schema facts the role is built on:

- the shadowsocks listener is **single-user** (one cipher + password, no
  `users` field), so there is no per-user shadowsocks option;
- trojan takes a `users` list, hysteria2/tuic/anytls a name/uuid -> password
  mapping - the role declares users in one uniform shape
  (`{name, password, uuid?}`) and the filter plugin maps them;
- TLS is flat `certificate` / `private-key` paths on the certificate-using
  listeners; vless with REALITY uses `reality-config` instead, and anytls
  with JLS uses `jls-config`.  mihomo has **no built-in ACME**: certificates
  are provisioned out of band.  The role can either reference an
  operator-managed pair in place (manual mode) or copy an external source
  pair into a service-readable location and install an optional TLS renewal
  hook (see [TLS material](#tls-material)).

The role does not manage a firewall or cloud security groups: open the
enabled listener ports yourself.

## Requirements

- A systemd-based Linux VPS (the binary is deployed as a static `.gz` archive
  by `ak1ra_lab.network.mihomo_install`).
- A TLS certificate/key pair for every certificate-using protocol
  (trojan/hysteria2/tuic/anytls, and vless when REALITY is disabled) - see
  [TLS material](#tls-material).  The role can copy an external source pair
  into a service-readable location, which is useful when the source lives in
  a root-only directory.  The default vless REALITY listener does not need
  its own certificate, and AnyTLS in JLS mode replaces its certificate with
  the JLS layer.
- For JLS: mihomo **>= 1.19.29** on both ends, a stable TLS destination with
  a certificate the generated mihomo clients trust, and a DNS `jls_sni`
  matching that certificate.  The JLS node is mihomo-only (the role's
  `mihomo_client` output); other clients cannot use it.
- A DNS name pointing at the VPS and a region token the client's region
  regex can match (`mihomo_server_region`, e.g. `US`, `HK`, `JP`).
- Control node: `ak1ra_lab.general` (>= 0.4.0) for `github_releases_info` and
  the `random_*` lookups; Galaxy resolves it from the collection dependencies.

## What it deploys

| Artifact | Purpose |
| --- | --- |
| `/usr/local/bin/mihomo` | mihomo binary, deployed by `mihomo_install` (consumer playbook) |
| `/etc/mihomo/config.yaml` | server configuration (`listeners` + `rules: [MATCH,DIRECT]`) |
| `/etc/systemd/system/mihomo.service` | service unit (`ExecStartPre` config test) |
| `/etc/mihomo/tls/{fullchain,privkey}.pem` | role-managed copies when a source pair is configured (`0640 root:mihomo`) |
| `/etc/letsencrypt/renewal-hooks/deploy/mihomo-server.sh` | optional TLS renewal deploy hook (role-managed) |
| `<repo>/config/client_outbounds/<host>.proxies.yaml` | clash-format client nodes for `mihomo_client` |
| `<repo>/config/client_outbounds/<host>.config.yaml` | exact copy of the deployed server config |
| `inventory/host_vars/<host>/mihomo_server.yaml` (or the configured `mihomo_server_host_vars_file`) | generated credentials (0600) |

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

## TLS material

**Manual mode (default).** Set `mihomo_server_tls_certificate_path` and
`mihomo_server_tls_key_path` to an existing certificate/key pair readable by
the `mihomo` user; the role only references the paths in the listeners.

**External source pair.** Set both `mihomo_server_tls_source_certificate_path`
and `mihomo_server_tls_source_key_path`.  The role then:

- ensures `mihomo_server_tls_dir` (`0750 root:mihomo`);
- copies the pair to the configured destination paths (`0640 root:mihomo`)
  on every apply, restarting mihomo only when the content changes;
- optionally installs a TLS renewal deploy hook via
  `mihomo_server_tls_renewal_hook_enabled`.

The source pair may live in a directory the mihomo service cannot read (for
example a root-only ACME lineage).  Point the source paths at the externally
managed pair and enable the hook:

```yaml
mihomo_server_tls_source_certificate_path: /etc/ssl/private/node01.example.com/fullchain.pem
mihomo_server_tls_source_key_path: /etc/ssl/private/node01.example.com/privkey.pem
mihomo_server_tls_renewal_hook_enabled: true
```

The hook is installed at `mihomo_server_tls_renewal_hook_path`; the external
certificate renewal tool runs every executable in its deploy-hook directory
after a successful renewal.  The role does not issue certificates.  The copy
task remains responsible for the initial material and for any manual re-run,
so the destination files always exist before the service starts or restarts.

### VLESS REALITY

Both the vless listener and REALITY are enabled in the default profile.
REALITY borrows the TLS handshake of `mihomo_server_vless_reality_dest`
(default `www.microsoft.com:443`), so the VLESS listener needs no certificate
of its own.  The role:

- generates the X25519 keypair on the target with
  `mihomo generate reality-keypair` when both key variables are empty;
- generates a 16-character hex short ID when the short-ID variable is empty;
- persists the private key, public key and short ID to the host_vars
  credential file (mode `0600`), so repeated runs reuse them;
- emits `reality-config` on the server listener and `reality-opts` on the
  generated client node.  `servername` becomes the first accepted server
  name (or the dest host when the list is empty), and `client-fingerprint`
  defaults to `chrome`.

`xtls-rprx-vision` is the recommended flow value with REALITY.  Certificate
paths are still required when any other certificate-using protocol
(trojan/hysteria2/tuic, or anytls in `certificate` mode) is enabled.

### AnyTLS

The generated AnyTLS client node sets `client-fingerprint` (default
`chrome`) and the idle-session knobs.  Leaving the fingerprint empty makes
mihomo use Go's standard-library TLS fingerprint, which is a weaker match for
browser traffic.  A positive `mihomo_server_anytls_min_idle_session` keeps
warm sessions on high-RTT links at the cost of keeping connections open.
AnyTLS has no REALITY support; keep it as a TLS/TCP fallback rather than a
REALITY replacement.

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
- JLS users are generated one-per-AnyTLS-user and persisted to host_vars;
  passwords are independent from the AnyTLS passwords;
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

Leaving the padding-scheme option empty uses mihomo's default scheme.  A
custom scheme is pushed to mihomo/sing-anytls clients through
`cmdUpdatePaddingScheme`; the first session still uses the client's default
scheme for its early packets.  The role validates the scheme syntax before
rendering because `mihomo -t` does not check listener runtime parameters.
Custom padding changes packet shape only; it does not hide SNI or fix the
TLS-in-TLS/timing weaknesses described by the AnyTLS FAQ.

## Certificate composition

This collection ships the `mihomo_server` role only; it does not issue
certificates and remains independent of any certificate collection. The
composition that pairs this role with certificate issuance lives in
`ansible-playbooks-services` as `mihomo_server_certbot.yml`:
`https://github.com/ak1ra-lab/ansible-playbooks-services`.

Use that playbook when the server certificate should be issued and renewed by
certbot. The role itself continues to accept operator-managed TLS material or
an external certificate pair as described above.

## Example playbook

The operational composition lives in `ansible-playbooks-services`
(`mihomo_server.yml`), which installs the binary first and then applies this
role:
`https://github.com/ak1ra-lab/ansible-playbooks-services`.

Applying the roles directly:

```yaml
- name: mihomo proxy server
  hosts: mihomo_server
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

Removed: `/etc/mihomo/config.yaml`, the unit and the optional TLS renewal
hook (the service is stopped and disabled first).

Deliberately left in place: the binary, the TLS source pair and the
role-managed copies, the external certificate lineage, and the
controller-local artifacts (`config/client_outbounds/`, `host_vars`) -
remove those manually when the credentials are no longer needed.

## Companion roles

- `ak1ra_lab.network.mihomo_install` deploys the binary (applied first by the
  consumer composition in `ansible-playbooks-services`);
- `ak1ra_lab.network.mihomo_client` consumes the generated client nodes
  through `mihomo_client_selfhost_files` (validated against the naming
  contract before the play writes `providers/selfhost.yaml`).
