---
hide:
  - toc
---

# Architecture

The collection is a set of independent roles with explicit, narrow contracts.
Playbooks orchestrate the roles; roles do not call each other, with the
exception of the collection playbooks documented in [Playbooks](playbooks.md).

The roles fall into four groups:

- Transparent proxy: `tproxy`, `flow_offload`, `proxy_guard`.
- mihomo: `mihomo_install`, `mihomo_client`, `mihomo_server`.
- Host networking: `systemd_bridge`, `systemd_netns`.
- Cloud-image network takeover: `cloud_init`, `netplan_static`,
  `systemd_resolved`.

## Transparent proxy: TPROXY versus TUN

`tproxy` is the engine-agnostic plumbing for engines that expose a TPROXY
inbound. It owns nftables marking, policy routing (`ip rule` / `ip route`),
sysctl tuning, and kernel module loading. The contract is its variable set:
`tproxy_listen_port` (where TPROXY and DNS interception deliver packets),
`tproxy_uid` / `tproxy_gid` (loop-prevention bypass mark), marks and route
table numbers, interfaces, and kernel-level bypass/reject CIDRs. See
[`tproxy` role](roles/tproxy.md) for the full table.

`mihomo_client` deliberately does not consume the `tproxy` contract. It
reproduces the mihomo-setup TUN design (`auto-route`, `auto-redirect`,
`auto-detect-interface`, and `dns-hijack`), which needs no nftables marking
and no policy-routing service. The `tproxy` role remains the plumbing for
engines with a TPROXY inbound, such as sing-box.

`flow_offload` and `proxy_guard` are independent opt-in roles. They do not
depend on `tproxy`; they own their own nftables tables and can be used on a
gateway that does not run this collection's TPROXY stack.

## mihomo client and server

`mihomo_install` owns only the static binary. It has no service identity, no
configuration, and no unit. The service roles own their own `mihomo` user,
unit, and configuration, and the collection playbooks apply the installer
first and wire its restart hook to the service role's handler.

`mihomo_server` generates the VPS-side listeners and two controller-local
artifacts:

- `playbooks/host_vars/<host>/mihomo_server.yaml` - generated credentials,
  mode `0600`, auto-loaded by Ansible on later runs.
- `config/client_outbounds/<host>.proxies.yaml` - clash-format client nodes
  ready for the client's `providers/selfhost.yaml` through
  `mihomo_client_selfhost_files`.

`mihomo_client` consumes those nodes, or inline nodes and airport
subscriptions, and renders the TUN profile. The profile templates are
hand-maintained; only a small set of values is rendered into them. See
[`mihomo_client` role](roles/mihomo_client.md) for the template and DNS
contract.

## Bridges and namespaces

`systemd_bridge` owns shared host-level bridges. They are stable
infrastructure: one bridge per dedicated physical interface (or a pure L2
island with no uplink), managed by `systemd-networkd` through `.netdev` and
`.network` files.

`systemd_netns` consumes those bridges. Each namespace gets veth legs with
real segment addresses and a default route, so services behave like ordinary
L2 neighbors. No host-side routing, NAT, or `ip_forward` is involved. The
role does not create bridges; that keeps the bridge lifecycle independent
from the namespace lifecycle.

## Cloud-image network takeover

The three cloud-image roles release the parts of a cloud image that normally
stay under cloud-init and then put stable host configuration in their place:

- `cloud_init` writes drop-ins under `/etc/cloud/cloud.cfg.d` and is otherwise
  a no-op; disabling network ownership is an explicit opt-in.
- `netplan_static` captures the live IPv4 addresses, default route, and MAC
  matches into `/etc/netplan/90-ansible-static.yaml`; it backs up and removes
  cloud-init's `50-cloud-init.yaml` only after cloud-init's network ownership
  is disabled. The conflict preflight understands netplan's multi-file merge
  order, so complementary files (for example a separate `mtu` file) remain
  valid.
- `systemd_resolved` owns the global resolver drop-in and the
  `/etc/resolv.conf` symlink mode. It deliberately has no static-file mode,
  because `mihomo_client` and `tproxy` already own that shape on their hosts.

The roles do not call each other; a site playbook orders them
`cloud_init` -> `netplan_static` -> `systemd_resolved`. Rollback is the reverse
path: `systemd_resolved` restores its resolver file, `netplan_static` restores
the cloud-init netplan backup, and `cloud_init` re-enables cloud-init's
network management. Role-managed rollback backups live under
`/var/lib/ansible/<namespace>/<collection>/<role>/` with the source path
mirrored below it; the path is fixed (first backup wins), not a timestamped
history.

## Role boundaries

| Role | Owns | Does not own |
| --- | --- | --- |
| `tproxy` | nftables marking, policy routing, sysctl, module loading | proxy engine, service identity |
| `flow_offload` | its own nftables flowtable table | the base nftables config |
| `proxy_guard` | its own nftables throttle/ban tables | the proxy engine or TPROXY rules |
| `systemd_bridge` | bridges and their systemd-networkd files | namespace veth legs |
| `systemd_netns` | namespace, veth legs, resolver file, service drop-ins | bridges |
| `cloud_init` | cloud-init drop-ins for network/SSH/host identity | netplan, DNS, `/etc/resolv.conf` |
| `netplan_static` | the static netplan file, cloud-init netplan backup, netplan generate/apply | cloud-init drop-ins, DNS resolver ownership |
| `systemd_resolved` | the resolved drop-in, service, `/etc/resolv.conf` symlink mode | static resolver files owned by `mihomo_client` / `tproxy` |
| `mihomo_install` | the static binary | service identity, config, unit |
| `mihomo_client` | client service, profile, unit, DNS handover | binary, firewall, subscription credentials |
| `mihomo_server` | server service, listeners, TLS material, credentials | binary, client service, certificate issuance (unless the playbook enables certbot) |
