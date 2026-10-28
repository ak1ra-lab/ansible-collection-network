# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog, and this project does not currently guarantee stable backward compatibility.

## [Unreleased]

### Added

- `netplan_static_default_interface` selects the physical interface that
  carries the static default route. The new
  `netplan_static_default_routes` filter reads the kernel main table
  (`/proc/net/route`), and `netplan_static_gateway` defaults to `auto` so the
  gateway is captured from that interface.

### Fixed

- `netplan_static` no longer fails when a TUN client such as `mihomo_client`
  owns `ansible_facts.default_ipv4` through policy routing. The TUN
  (`mihomo0`) is never rendered; the role selects the captured ethernet
  interface and gateway from the kernel main table instead.
- `netplan_static` treats an empty `ansible_facts.default_ipv6` mapping as
  "no IPv6 default route" instead of failing the IPv6-loss gate on hosts with
  IPv6 disabled.
- The Docs workflow installs `distlib` through the docs dependency group, so
  `ansible-galaxy` can read the `galaxy.yml` manifest when installing the
  collection from source. The `just` collection recipes use the uv
  environment for the same reason.
- Molecule keeps `systemd-resolved` pointed at the container runtime's
  upstream DNS, so the resolver scenarios no longer break package downloads
  in later scenarios.

### Changed

- Refreshed CI action pins: `actions/setup-python` 7.1.0,
  `astral-sh/setup-uv` 10.3.1 and `actions/upload-pages-artifact` 5.0.0.

## [v0.3.0] - 2026-10-28

### Added

- `ak1ra_lab.network.mihomo_install`: shared installer for the official
  statically linked mihomo release.  It selects the platform (and amd64
  microarchitecture) asset, verifies the digest, installs to
  `/usr/local/bin/mihomo`, and supports `present`, `latest` and pinned
  versions plus a local file/URL archive override.  The mihomo roles require
  `ak1ra_lab.general` (not on Galaxy yet).
- `ak1ra_lab.network.mihomo_client`: TUN transparent-proxy client for LAN
  gateway or host-only deployments.  It owns the `mihomo` service identity,
  profile and unit, ships plain and selfhost-tier profile templates,
  provisions the rule-set data, takes over `:53` from systemd-resolved,
  persists the `tun` module and the gateway sysctls, and stores the generated
  API secret in auto-loaded host_vars.  `absent` restores systemd-resolved
  and the distro resolver.
- `ak1ra_lab.network.mihomo_server`: VPS-side listeners for shadowsocks,
  trojan, hysteria2, vless, tuic and anytls, with generated and persisted
  credentials, clash-format client artifacts, external TLS material, optional
  certbot issuance orchestration and a renewal hook.  The defaults enable
  shadowsocks, hysteria2, anytls and VLESS REALITY on ports `9442-9447`
  (trojan/tuic opt-in); AnyTLS JLS and the client fingerprint/idle-session
  knobs are supported.
- Playbooks `ak1ra_lab.network.mihomo_install`, `mihomo_client` and
  `mihomo_server`; the client/server playbooks apply the installer first and
  wire its restart hook to the service handler.  Filter plugins
  (`mihomo_proxy_providers`, `mihomo_selfhost_proxies`,
  `mihomo_server_config`, `mihomo_server_client_proxies`, `to_pretty_yaml`)
  and lookup plugins (`random_password`, `random_base64_key`,
  `random_uuid`) cover provider normalization, listener/client-node
  generation, YAML rendering and credential generation.
- `ak1ra_lab.network.cloud_init`, `netplan_static` and `systemd_resolved`:
  three independent roles for taking a cloud image off cloud-init's network
  management:
  - `cloud_init` writes cloud-init drop-ins for network ownership, stable SSH
    host keys, `/etc/hosts`/hostname preservation and an extra-config escape
    hatch; its defaults are no-ops.
  - `netplan_static` captures the live IPv4 state into a static netplan file
    (addresses, one default gateway, nameservers and MAC-matched `set-name`),
    validates it with `netplan generate`, backs up and removes cloud-init's
    netplan file, and restores it on teardown.  It is IPv4-only, fails closed
    on IPv6, and uses a merge-aware conflict policy (`strict` / `overlap` /
    `none`) for complementary netplan files.
  - `systemd_resolved` manages the global resolver drop-in and the
    `/etc/resolv.conf` `stub`/`uplink`/`static`/`unmanaged` mode, with backup
    and restore of a pre-role regular resolver file.  It has no static-file
    mode: `tproxy` and `mihomo_client` keep their own static resolver files.
- Playbooks for the three cloud-image roles, the cloud-image rollback backup
  convention under `/var/lib/ansible/<namespace>/<collection>/<role>/`, and
  the `netplan_static_interfaces` / `netplan_conflicts` filter plugins.
- `systemd_netns` per-netns sysctls (`systemd_netns_sysctl_params`),
  re-applied after every namespace creation through the unit's `ExecStart`.
- An ansible-native Molecule harness under `extensions/molecule/` covering
  every role on shared systemd-enabled Debian/Ubuntu containers, with
  prepare/converge/idempotence/verify/teardown runs and selectable rootful
  Podman or Docker.  CI runs ansible-lint, ruff, ty, unit tests, every
  Molecule scenario and the docs build.
- A MkDocs Material documentation site with guides, role pages included from
  the canonical role READMEs, generated plugin reference pages and a GitHub
  Pages workflow.  Development tooling is uv-managed (`just sync`, `lint`,
  `typecheck`, `unit-test`, `ansible-lint`, docs recipes).

### Changed

- `systemd_netns` convention values moved into `vars/main.yaml`, and the role
  name now defaults to `qbittorrent`.  Its playbook applies the declared host
  bridges and flushes their handlers before validating the namespace.
- `flow_offload` and `proxy_guard` honor their `*_enabled` master switch: the
  drop-in is removed when the switch is turned off, and the removal restarts
  nftables.

### Fixed

- Roles and Molecule playbooks work on the declared ansible-core 2.18
  minimum: Jinja2 builtins stay bare, while collection plugins use their
  `ansible.builtin.` FQCN.
- `systemd_bridge` detects NetworkManager by probing its unit file instead of
  `service_facts`, and renders `RequiredForOnline=` in `[Link]` for
  interface-less bridges carrying an address.
- `systemd_netns` validates the bridged topology only when applying, and
  requires referenced bridges to carry at least one enslaved member.
- `tproxy` now restarts `ansible-tproxy-routing.service` with a matching
  handler, and `proxy_guard` restores its documented LAN, throttle and
  auto-ban defaults.
- `ansible-galaxy collection build` excludes controller-local
  `playbooks/host_vars/`, `playbooks/group_vars/`, scripts and templates from
  the artifact.

## [v0.2.0] - 2026-09-09

### Added

- `systemd_bridge` — declarative host-level Linux bridges, each optionally
  enslaving one dedicated physical interface, managed entirely by
  `systemd-networkd` (`.netdev` files, enslave `.network` files,
  NetworkManager `unmanaged-devices` drop-ins when NetworkManager is
  running).  Bridges without an `interface` are pure L2 private segments
  (no uplink).  Bridges are shared, stable infrastructure; STP, forward
  delay, FDB ageing time, multicast snooping and VLAN filtering are
  configurable per bridge, and an optional `address` gives the bridge (and
  thereby the host) an L3 presence on the segment.  `RequiredForOnline=` is
  scoped to links that actually carry host connectivity (address-carrying
  bridges and teardown release files keep the default; enslaved ports and
  address-less bridges are excluded), so `systemd-networkd-wait-online`
  neither stalls on never-online devices nor loses its only required link.
- `systemd_netns` — dedicated-segment egress isolation (opt-in,
  independent): a network namespace attaching veth legs to the host-level
  bridges of `systemd_bridge` (or any existing bridge), carrying real
  segment addresses and its default route via the leg that declares a
  gateway - the host does no routing, NAT or filtering for this traffic.
  `systemd_netns_links` entries are one veth leg per segment
  (`{bridge, address, gateway?, mac?}`), with at most one gateway leg owning
  the default route; bridge existence and gateway subnet membership are
  validated at run time.
- Collection dependency on `ansible.utils >= 6.0.0` for `systemd_netns` link
  validation (`ipaddr` / `in_network` filters on the control node).
- Egress verification (`systemd_netns_verify`) uses `curl` consistently for
  the namespace and the host against a configurable exit-IP echo service
  (`systemd_netns_verify_url`, default `https://ip.sb`); the namespace
  resolv.conf defaults to AliDNS `223.5.5.5` and DNSPod `119.29.29.29`.
- Collection playbooks `ak1ra_lab.network.systemd_bridge` and
  `ak1ra_lab.network.systemd_netns`: thin entry points running the roles on
  `localhost` by default with root privileges; the built artifact ships
  `playbooks/` (`galaxy.yml` manifest graft).

### Changed

- `systemd_bridge` networkd artifacts are named after the device they
  configure with numeric prefixes encoding the load order: `10-<name>.netdev`
  (bridge definition), `15-<interface>.network` (uplink enslave) and
  `20-<name>.network` (bridge configuration, always rendered - a bridge
  without a matching `.network` file is not managed by networkd at all;
  `address`/`gateway`/`dns` are added when declared).  Every rendered file
  embeds an ownership marker comment
  (`# ... managed by ak1ra_lab.network.systemd_bridge ...`), and the networkd
  conflict preflight (`systemd_bridge_conflict_check`) evaluates `Name=`
  patterns semantically instead of grepping: a file only conflicts when one
  of its shell-glob patterns actually matches a managed device (marker-carrying
  files are this role's own), so distro-packaged wildcard defaults such as
  `80-container-*.network` or `80-vm-vt.network` are ignored unless they
  really claim a managed interface or bridge.
- `systemd_bridge` enslave file places `Bridge=` under `[Network]`; the
  previous `[Bridge]` section made systemd-networkd ignore the enslave
  (`Unknown key 'Bridge' in section [Bridge]`), leaving the uplink
  unconfigured and the host unreachable after a reload.
- `systemd_bridge` teardown release files now take over the regular
  `15-<interface>.network` path instead of a separate file of their own.
- `systemd_netns` teardown discovers leftover veth legs by naming prefix
  instead of relying on the declared link list.
- `systemd_netns` teardown stops namespace-joined services discovered from
  the namespace's own processes via cgroup attribution
  (`ip netns pids` + `/proc/<pid>/cgroup`) instead of deriving unit names
  from drop-in paths - this also handles template-unit instances
  (`foo@bar.service` hooked through a `foo@.service` drop-in).
- `systemd_bridge` bridges may carry an optional `gateway` and `dns` next to
  their `address` (host-uplink style; at most one gateway-carrying bridge
  per host, gateway must lie inside the address network).
- `systemd_bridge` teardown is connectivity-safe when requested: per-bridge
  `absent_release_mode: static|dhcp` writes a release `.network` file so the
  freed physical interface keeps the former address (or uses DHCP) in the
  same networkd restart that drops the bridge; address-carrying bridges
  removed without a release mode are reported.
- `systemd_bridge` preflights the networkd configuration directories
  (`systemd_bridge_conflict_check`) and fails when other `.network` files
  already match the interfaces or bridges it manages.
- The `systemd_netns` documentation now describes per-service next-hop
  gateway selection in both directions: host proxied with a service direct,
  or host direct with a single service proxied through a TPROXY gateway on
  the same bridged segment.

## [v0.1.0] - 2026-09-07

### Added

- Initial collection with three roles:
  - `tproxy` — engine-agnostic TPROXY transparent proxy plumbing (nftables
    marking, policy routing, sysctl), extracted from
    `ak1ra-lab/sing-box-tproxy` `roles/sing_box_tproxy` and renamed to the
    `tproxy_*` variable contract.
  - `flow_offload` — nftables flowtable offloading for forwarded traffic
    (opt-in, independent).
  - `proxy_guard` — per-client TCP abuse protection with throttle / auto-ban
    (opt-in, independent).
- Declarative state for every role: `<role>_state` (default `present`);
  `absent` atomically tears down the role's own artifacts via
  `tasks/reset.yaml`, leaving shared system files untouched.
