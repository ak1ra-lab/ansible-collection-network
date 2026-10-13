# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog, and this project does not currently guarantee stable backward compatibility.

## [Unreleased]

### Added

- `systemd_netns` per-netns sysctls (`systemd_netns_sysctl_params`),
  re-applied after every namespace (re)creation through the unit's
  `ExecStart`, documented with evidence-driven BitTorrent tuning
  candidates; only per-netns keys are isolated to the namespace,
  host-global keys are documented as such.

### Changed

- `systemd_netns` convention values and derived names (enumeration lists,
  verification URL, veth prefix/service names) move from
  `defaults/main.yaml` into `vars/main.yaml`, keeping the overridable
  public contract short; `systemd_netns_name` defaults to `qbittorrent`
  (the role's reference workload) instead of `dedicated_net`.

### Fixed

- `systemd_bridge` detects an actual NetworkManager installation by probing
  the unit file instead of `ansible_facts['services']`: on Debian-family
  hosts the packaged apt-daily units reference NetworkManager.service in
  their `After=` lines, which makes systemd instantiate a not-found unit and
  service_facts report NetworkManager.service even where NetworkManager is
  not installed - the role then wrote unmanaged-devices drop-ins and the
  reload handler failed hard on hosts without NetworkManager.
- `systemd_bridge` renders `RequiredForOnline=` in the `[Link]` section for
  interface-less bridges carrying an address instead of `[Network]`, where
  systemd-networkd ignores the key: such a bridge never has carrier on its
  own (its veth legs attach at run time, after network-online.target), so it
  stayed required-for-online and systemd-networkd-wait-online could wait for
  it forever - blocking network-online.target at boot.
- `systemd_netns` validates the bridged topology (links, referenced bridges)
  only when applying (`systemd_netns_state: present`): teardown (`absent`)
  needs only the namespace name.  Referenced bridges must now carry at least
  one enslaved member interface - a bridge without any uplink is an L2
  island the namespace cannot exit through; the defaults documented this
  contract but the check was missing.

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
