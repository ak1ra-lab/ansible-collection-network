# ak1ra_lab.network.tproxy

> The canonical variable reference is generated from
> [`meta/argument_specs.yml`](meta/argument_specs.yml) in the
> [collection documentation](https://ak1ra-lab.github.io/ansible-collection-network/collection_index.html).
> This README keeps purpose, deployed artifacts, teardown
> behavior, and operational notes.

!!! warning "Experimental role"
    `tproxy` is marked **experimental**.  The role name is stable, but its
    variable contract and deployed artifacts may change without a deprecation
    cycle until it is promoted.  Pin a collection version and review the
    changelog before upgrading.

Engine-agnostic TPROXY transparent proxy plumbing for Linux gateways:
nftables marking (fwmark), policy routing (`ip rule` / `ip route`), sysctl
tuning and kernel module loading. Installs and configures **no proxy engine**.
`gateway` mode proxies LAN-forwarded and local traffic (and enables
`ip_forward`); `local` mode proxies local traffic only.

## What it deploys

| Artifact | Purpose |
| --- | --- |
| `/etc/nftables.d/ansible_tproxy.nft` | `table inet ansible_tproxy` — prerouting TPROXY interception + output marking. **Chain-first rule transparently intercepts all DNS (`tcp/udp dport 53`)** ahead of every bypass/reject decision; the engine consumes it (e.g. sing-box `hijack-dns`, or a future REDIRECT delivery to an engine DNS listener). |
| `/etc/nftables.conf` | Base config including `/etc/nftables.d/*.nft`. |
| `/etc/systemd/system/ansible-tproxy-routing.service` | Adds/removes `ip rule` + `ip route` policy routing entries. |
| `/etc/iproute2/rt_tables.d/ansible_tproxy.conf` | Route table name entry (`ansible_tproxy`). |
| `/etc/sysctl.d/90-ansible-tproxy-*.conf` | ip_forward (gateway mode), nf_conntrack, tcp_bbr. |
| `/etc/resolv.conf` | Optional static resolver file (content is advisory only — DNS is intercepted upstream). |

## Engine integration

Any proxy engine that listens on a TPROXY inbound plugs in through the listen
port and its runtime uid/gid alone; the role never references engine-specific
names. The listen port is also the delivery point of DNS transparent
interception. Marks, the policy-routing table, exit interfaces, bypass/reject
CIDRs and the conntrack/BBR sysctls are host plumbing; the generated role
reference lists their defaults and accepted values.

## Declarative teardown: `tproxy_state: absent`

Setting `tproxy_state: absent` removes, in one atomic pass: the routing unit
(stopped first — its `ExecStop` removes the `ip rule` / `ip route` entries),
`/etc/nftables.d/ansible_tproxy.nft`, the rt_tables entry, the
`90-ansible-tproxy-*.conf` sysctl drop-ins, and the `/etc/modules-load.d/`
entries written by persistent modprobe. nftables is reloaded afterwards.

Deliberately **not** touched: `/etc/nftables.conf`, the `nftables.service`
unit, `/etc/resolv.conf` (the previous content was never backed up), and the
packages. Kernel sysctl values persist until reboot — reverting shared keys
like `net.ipv4.ip_forward` is left to the operator.

## Escape hatch: stop one service for direct connectivity

fwmark and policy routing are deliberately decoupled:

```shell
systemctl stop ansible-tproxy-routing.service    # traffic flows directly
systemctl start ansible-tproxy-routing.service   # transparent proxying restored
```

While stopped, packets keep their fwmark but no longer match the policy
routing rule, so nothing is delivered to the proxy — nftables stays untouched.
DNS interception follows the same path and recovers identically.

## Companion roles (independent, opt-in)

- `ak1ra_lab.network.flow_offload` — flowtable offloading.
- `ak1ra_lab.network.proxy_guard` — per-client TCP abuse protection.
