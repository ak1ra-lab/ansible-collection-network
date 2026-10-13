# ak1ra_lab.network.systemd_netns

Dedicated-segment egress isolation: systemd services run inside a network
namespace that attaches veth legs to host-level Linux bridges, and the
namespace carries real addresses + a default route on the bridged segments.
Services joined to the namespace behave like any other L2 neighbor on those
segments - they have their own IP and **no** host-side policy routing, NAT or
`ip_forward` is involved.

The bridges themselves are shared host infrastructure and are **not** managed
by this role: declare them in `ak1ra_lab.network.systemd_bridge` (one role per
host, stable configuration), or rely on the host's own network configuration
layer.  This role only manages the namespace, its veth legs, the resolv.conf
and the per-service drop-ins.

Use it when a dedicated physical interface (or a segment with spare
addresses) exists: each service gets its own exit identity and inbound
arrives directly - the namespace traffic never passes through the host's
L3 stack, so there is no host-port DNAT, no conntrack/NAT state and no
`ip_forward` for this traffic.

## Requirements

- Managed host: root privileges, systemd with `iproute2`.  The bridges
  referenced by `systemd_netns_links` must already exist (created by
  `ak1ra_lab.network.systemd_bridge` or otherwise) and carry at least one
  enslaved member interface; the role validates both at run time.
- Control node: `ansible.utils` collection (pulled in as a collection
  dependency) - the `ipaddr` filters used for link validation run on the
  control node.

## What it deploys

| Artifact | Purpose |
| --- | --- |
| `/etc/systemd/system/netns-<name>.service` | Oneshot unit creating/destroying the namespace and its veth legs (idempotent restarts via `ExecStartPre` cleanup). |
| `/etc/netns/<name>/resolv.conf` | Namespace resolver file at the iproute2-convention path - `ip netns exec` bind-mounts it automatically; systemd drop-ins bind this path directly. |
| `/etc/systemd/system/<unit>.d/netns.conf` | Per hooked service: `NetworkNamespacePath=` + `PartOf=`/`Requires=`/`After=` wiring (see below). |

Deliberately **not** deployed: bridges (owned by `systemd_bridge`),
systemd-networkd / NetworkManager state, nftables rules, rt_tables entries,
policy routing, `ip_forward` - the host forwards nothing for the namespace,
it only switches frames (L2).

## How traffic flows

- **Egress**: the namespace's default route points at whatever next-hop the
  operator chooses per service - the leg declaring `gateway`.  Typically
  that is the segment's real gateway: packets leave through the bridge and
  the enslaved physical interface with the namespace's own source address,
  and the host's own default route (TPROXY / proxied or not) is never
  consulted.  But the choice is arbitrary among the routers reachable on
  that segment, and it may be used in *either* direction:

  - **Host proxied, service direct**: the host's default route points at a
    TPROXY gateway (`ak1ra_lab.network.tproxy`); a hooked service exits
    **directly** through the segment's real gateway with its own address.
  - **Host direct, service proxied**: the host uses the ordinary default
    route, while the service's leg declares the **TPROXY gateway** of
    another machine on the same segment as its default route - only that
    application is transparently proxied (per-service gateway selection,
    no host-wide tproxy needed).

  The gateway must be reachable on the *same bridged segment* as the
  namespace leg (the leg's own L2 neighbor): nothing here is policy-routed
  across the host, so a gateway on another segment does not work.
- **Inbound**: services are directly reachable at their namespace address on
  the bridged segment - no DNAT, no host port conflicts.  To expose a
  management interface on a *different* segment, declare a second leg on
  another bridge and reach the service there (one leg per segment).
- **Host -> namespace**: the host may or may not have an address on the
  bridge (see the `address` field of `systemd_bridge`).  With one, the host
  talks to the namespace like any other segment neighbor; without, reach the
  service from another machine on the segment or add a leg on a
  host-addressed bridge.

Each veth pair gets random MACs on every namespace recreation by default;
pin `mac:` on legs that need stable ARP entries or DHCP leases across
recreations.

## Variable contract

| Variable | Default | Description |
| --- | --- | --- |
| `systemd_netns_state` | `present` | `absent` tears down the per-namespace artifacts (see below). |
| `systemd_netns_name` | `dedicated_net` | Namespace identifier; also used in the unit and resolv.conf directory name. |
| `systemd_netns_links` | `[]` | Namespace veth legs (one per segment): `{bridge, address, gateway?, mac?}`. The `bridge` must already exist on the host. At most one leg may set `gateway`; it owns the namespace's default route. |
| `systemd_netns_dns_servers` | `223.5.5.5, 119.29.29.29` | Namespace resolvers. |
| `systemd_netns_hook_services` | `[]` | Systemd units to join to the namespace via a drop-in. The role only writes/removes the drop-in; it never manages the hooked services themselves. |
| `systemd_netns_disable_ipv6` | `true` | Disable IPv6 inside the namespace (segments are often v4-only; avoids happy-eyeballs stalls). |
| `systemd_netns_verify` | `false` | After deployment, curl the exit IP from inside the namespace and from the host (informational). |
| `systemd_netns_verify_url` | `https://ip.sb` | Exit-IP echo service used by the verification check. |

## Example playbook

With the bridges declared in `systemd_bridge` (see its README):

```yaml
- hosts: app-host
  roles:
    - role: ak1ra_lab.network.systemd_netns
      vars:
        systemd_netns_name: qbittorrent
        systemd_netns_links:
          - {bridge: br_wan, address: 10.255.0.245/24,
             gateway: 10.255.0.1, mac: "bc:24:11:b5:c3:bc"}
        systemd_netns_hook_services:
          - qbittorrent-nox@.service
```

## Hooking a service into the namespace

Set `systemd_netns_hook_services` to a list of systemd unit names; the role
writes a drop-in per unit and leaves the service lifecycle (enable / start /
restart) to the operator.  For `qbittorrent-nox@.service` the generated
drop-in is:

```ini
# /etc/systemd/system/qbittorrent-nox@.service.d/netns.conf
[Unit]
Requires=netns-qbittorrent.service
After=netns-qbittorrent.service
PartOf=netns-qbittorrent.service

[Service]
NetworkNamespacePath=/run/netns/qbittorrent
BindReadOnlyPaths=/etc/netns/qbittorrent/resolv.conf:/etc/resolv.conf
```

`PartOf=` matters: restarting the netns unit recreates the namespace, and the
application stops with it (`PartOf` propagates the stop).  The role writes
the drop-in but does not enable or start the hooked service; after a netns
unit restart the hooked services stay stopped until the operator starts them
again.

Operational notes:

- Bind the service to `0.0.0.0` or its namespace addresses; `127.0.0.1` is
  no longer shared with the host.
- To attach several legs (e.g. one on a host-LAN bridge for a management
  UI, one on `br_wan` for egress), declare several `systemd_netns_links`
  entries and set `gateway` only on the egress leg.
- Several namespaces may join the same bridge (e.g. one egress bridge shared
  by multiple services); each service still needs its own segment address.
- Multiple namespaces on one host (`allow_duplicates: true`): run the role
  once per namespace with distinct `systemd_netns_name` / links.
- Validation runs at play time: `systemd_netns_links[].bridge` must already
  exist on the host (any owner) and carry at least one enslaved member
  interface - a bridge without any uplink is an L2 island with no exit.
  Apply `systemd_bridge` first on fresh hosts.

## Declarative teardown: `systemd_netns_state: absent`

Stops services that still hold the namespace - they are discovered from the
namespace's own processes via cgroup attribution (`ip netns pids` +
`/proc/<pid>/cgroup`), which also covers template-unit instances
(`foo@bar.service` hooked through a `foo@.service` drop-in) and any other
systemd service inside the namespace.  Stops and disables the netns unit
(its `ExecStop` removes namespace and veth legs), then removes the unit
file, drop-ins, resolv.conf directory and leftover runtime state (fallback
for already-deleted unit files and veth legs discovered by naming prefix).
Processes inside the namespace that belong to no systemd service (e.g. a
manual `ip netns exec` shell) are reported, not killed - they keep a hidden
namespace alive until they exit; re-run after stopping them.

Deliberately **not** touched: the host-level bridges and everything
`systemd_bridge` manages - remove those with that role's `absent` state.
