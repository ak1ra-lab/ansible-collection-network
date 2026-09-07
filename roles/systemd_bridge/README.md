# ak1ra_lab.network.systemd_bridge

Declarative host-level Linux bridges, managed entirely by
`systemd-networkd`.  Each bridge optionally enslaves a dedicated physical
interface as its uplink and behaves like a L2 switch on that segment; any
interface can then be enslaved as an additional bridge port.  The natural
consumers are `ak1ra_lab.network.systemd_netns`, whose namespace veth legs
attach to these bridges, and `ak1ra_lab.network.systemd_netns_routing`,
whose namespaces hang off **interface-less** bridges (pure L2 islands with
a private address, no uplink - the namespaces exit through the host's L3
stack, never through the bridge).  Nothing prevents enslaving further
physical ports or other interfaces either.

Because bridges are shared, stable infrastructure, they are deliberately kept
in their own role - their lifecycle does not change when namespaces come and
go.

## Requirements

- Managed host: root privileges, `systemd-networkd` enabled (the role
  enables and starts it), `iproute2` (teardown fallback only).
- The physical interfaces declared in `systemd_bridge_bridges` (only
  bridges with an `interface` field) must be **dedicated** to the role:
  they must not be configured by netplan / ifupdown / another
  NetworkManager profile (the role writes an `unmanaged-devices` drop-in
  for them when NetworkManager is running), and they carry no address of
  their own - see [Addressing](#addressing).  The role scans `/etc`,
  `/run` and `/usr/lib` for other networkd configuration matching the
  managed devices and fails when it finds any (disable with
  `systemd_bridge_conflict_check: false`).

## What it deploys

Per `systemd_bridge_bridges` entry, under `/etc/systemd/network` (unless
otherwise noted):

| Artifact | Purpose |
| --- | --- |
| `10-<name>.netdev` | The Linux bridge itself (STP, forward delay, ageing time, multicast snooping and VLAN filtering are configurable per bridge). |
| `15-<interface>.network` | Enslaves the dedicated physical interface into the bridge (`[Match] Name=` + `[Network] Bridge=`) - **only rendered for bridges with an `interface` field**.  During teardown with a release mode this path instead carries the released interface's own configuration. |
| `20-<name>.network` | Configures the bridge link - always rendered.  With `address` (plus `gateway`/`dns`) declared it assigns them to the bridge; without, the file only makes `systemd-networkd` manage the bridge so it comes up: a bridge with no matching `.network` file is not managed at all. |
| `/etc/NetworkManager/conf.d/10-<name>.conf` | Marks the enslaved interface `unmanaged` for NetworkManager (only written when NetworkManager is present and the bridge declares an `interface`). |

The numeric prefixes encode the order systemd-networkd needs: bridge `.netdev`
first (10), then the uplink enslave (15), then the bridge's own configuration
(20).  Every rendered file carries a marker comment
(`# ... managed by ak1ra_lab.network.systemd_bridge ...`); the conflict
preflight greps for it so hand-written configuration that happens to use the
same device-based names is never mistaken for this role's own files.

The role also enables and starts `systemd-networkd`.

Regarding `RequiredForOnline=` (wait-online): a link only counts for
`systemd-networkd-wait-online.service` when it can actually reach an online
operational state.  The enslave file and address-less (pure L2) bridges are
therefore excluded (`RequiredForOnline=no`) - an enslaved port never carries
an address, and an uplink-less private bridge has no carrier at all, so
waiting on them would stall or fail `network-online.target` at boot.  Bridges
that carry the host's own `address` (plus `gateway`/`dns`) keep the systemd
default and are what wait-online waits for; the same applies to teardown
release files, which then hold the host's connectivity themselves.

## Addressing

A bridge is an ordinary Linux network device, and the role does not assume it
stays address-less: declare `address` when the host itself must be reachable
on that segment (management, monitoring, ...).  The host then appears as a
normal member of the segment, side by side with any namespace legs - nothing
about the L2 bridging or the namespaces changes.  Add `gateway` (at most one
per host - a second one would install a second default route) and `dns` when
the bridge serves as the host's uplink.  Interface-less (private segment)
bridges take an `address` the same way - it is the namespace gateway for
`systemd_netns_routing` - with neither a `gateway` nor a physical uplink
involved: that role routes namespace traffic at L3.

Do **not** configure addresses on the enslaved physical interface.  The
kernel accepts `ip addr add` on an enslaved port, but the port is a pure L2
member once joined to a bridge: inbound frames are handled by the bridge and
never delivered to an address configured on the port itself (inbound breaks,
and what little traffic flows is asymmetric at best).  Addresses belong on
the bridge device - that is what the `address` field is for.  This also means
the address must be configured on the bridge and not left on the physical
NIC when migrating an interface into a bridge.

With NetworkManager running, add the bridge itself to the unmanaged list as
well when it carries a host address, so NetworkManager does not try to claim
or autoconfigure it (`unmanaged-devices=interface-name:<bridge>` in a
conf.d file).

## Variable contract

| Variable | Default | Description |
| --- | --- | --- |
| `systemd_bridge_state` | `present` | `absent` tears down the declared bridges (see below). |
| `systemd_bridge_bridges` | `[]` | Bridges: `{name, interface?, address?, gateway?, dns?, stp?, forward_delay?, ageing_time?, multicast_snooping?, vlan_filtering?, absent_release_mode?}` per optional dedicated physical interface. |
| `systemd_bridge_conflict_check` | `true` | Fail when other networkd configuration matches the managed devices; `false` downgrades the check to a warning. |

Per-bridge element:

| Field | Default | Description |
| --- | --- | --- |
| `name` | - | Bridge device name (valid interface name, <= 15 chars). |
| `interface` | unset | Optional physical interface enslaved into the bridge (dedicated, no own address).  Unset for an interface-less bridge: a pure L2 island with no uplink, typically carrying a private `address` as the segment gateway for `systemd_netns_routing` namespaces. |
| `address` | unset | Optional IPv4 CIDR assigned to the bridge itself (host presence on the segment). |
| `gateway` | unset | Optional IPv4 gateway for the bridge's own default route; requires `address`, at most one per host. |
| `dns` | unset | Optional list of IPv4 resolvers for the bridge's own `.network` file; requires `address`. |
| `stp` | `false` | Spanning Tree Protocol. Enable once the bridge carries more than one physical (potentially looping) port; with one uplink plus veth legs no loop can form. |
| `forward_delay` | `0` | Forward delay in seconds; only meaningful with `stp: true`, give it at least a few seconds then. |
| `ageing_time` | `300` | FDB entry lifetime in seconds (kernel default). |
| `multicast_snooping` | `true` | IGMP/MLD snooping (kernel default). |
| `vlan_filtering` | `false` | 802.1Q VLAN filtering on the bridge. |
| `absent_release_mode` | `none` | How to keep the freed physical interface reachable on teardown: `none`, `static` (moves `address`/`gateway`/`dns` onto the interface), or `dhcp`.  Requires `interface` (the release file replaces the enslave file on the `15-<interface>.network` path). |

## Example playbook

Create several bridges - with any mix of uplink, pure L2 and
host-addressed segments:

```yaml
- hosts: gw-host
  roles:
    - role: ak1ra_lab.network.systemd_bridge
      vars:
        systemd_bridge_bridges:
          - {name: br_wan, interface: enp36s0}
          - {name: br_private, address: 10.200.0.1/24}
          - {name: br_mgmt, interface: enp36s1, address: 192.0.2.10/24,
             gateway: 192.0.2.1, dns: [223.5.5.5],
             stp: true, forward_delay: 4}
```

`br_private` is an interface-less bridge - a private segment island whose
gateway address `10.200.0.1/24` the host carries on the bridge device.  It
never touches the host's physical uplinks; `systemd_netns_routing`
namespaces attach here and exit through the host's L3 stack (NAT + policy
routing), which is why no physical interface is enslaved.

Then run `systemd_netns` (once per namespace) with `systemd_netns_links`
referencing these bridges, or `systemd_netns_routing` for the private
bridge networks.  Apply `systemd_bridge` before the netns roles on fresh
hosts: they validate bridge existence at run time.

## Declarative teardown: `systemd_bridge_state: absent`

Removes the NetworkManager drop-ins and all `.netdev`/`.network` files,
lets `systemd-networkd` drop the bridges and removes leftover runtime state
as a fallback.  Any interface still enslaved - e.g. veth legs of a
`systemd_netns` namespace - is released from the bridge and loses its L2
connectivity; tear the namespaces down first (`systemd_netns_state: absent`)
to keep the teardown clean.

Removing a bridge that carries the host's own `address` takes that address
away with it - if it is the host's only one, the host becomes unreachable
(the role prints a warning for exactly this case).  Set
`absent_release_mode` on such bridges to keep connectivity:

- `static` - the `15-<interface>.network` file (the regular enslave path,
  replaced in the same run) re-applies the bridge's `address` (plus
  `gateway`/`dns` when set) to the physical interface; the same networkd
  restart that drops the bridge activates it, so the address never
  disappears.  The file stays behind after teardown and is replaced by the
  enslave file again on the next `state: present` run - drop it manually if
  the bridge is gone for good.
- `dhcp` - same mechanism, but the interface obtains an address via DHCP
  (`DHCP=ipv4`) instead; note the address may change if the segment hands
  out different leases.

Always run the teardown from a connection that does not depend on the bridge
being removed (console, IPMI, out-of-band uplink, or a `dhcp`/`static`
release on the very bridge you are removing), and prefer a `networkctl
status` / `ip -br addr` check right after the run.
