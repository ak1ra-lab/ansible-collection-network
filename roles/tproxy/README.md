# ak1ra_lab.network.tproxy

Engine-agnostic TPROXY transparent proxy plumbing for Linux gateways:
nftables marking (fwmark), policy routing (`ip rule` / `ip route`), sysctl
tuning and kernel module loading. Installs and configures **no proxy engine**.

## What it deploys

| Artifact | Purpose |
| --- | --- |
| `/etc/nftables.d/ansible_tproxy.nft` | `table inet ansible_tproxy` — prerouting TPROXY interception + output marking. **Chain-first rule transparently intercepts all DNS (`tcp/udp dport 53`)** ahead of every bypass/reject decision; the engine consumes it (e.g. sing-box `hijack-dns`, or a future REDIRECT delivery to an engine DNS listener). |
| `/etc/nftables.conf` | Base config including `/etc/nftables.d/*.nft`. |
| `/etc/systemd/system/ansible-tproxy-routing.service` | Adds/removes `ip rule` + `ip route` policy routing entries. |
| `/etc/iproute2/rt_tables.d/ansible_tproxy.conf` | Route table name entry (`ansible_tproxy`). |
| `/etc/sysctl.d/90-ansible-tproxy-*.conf` | ip_forward (gateway mode), nf_conntrack, tcp_bbr. |
| `/etc/resolv.conf` | Optional static resolver file (content is advisory only — DNS is intercepted upstream). |

## Variable contract

Any proxy engine that listens on a TPROXY inbound plugs in through these
variables alone; the role never references engine-specific names.

| Variable | Default | Description |
| --- | --- | --- |
| `tproxy_state` | `present` | `present` applies the plumbing; `absent` atomically tears down everything this role created (see below). |
| `tproxy_mode` | `gateway` | `gateway` proxies LAN-forwarded + local traffic (enables ip_forward); `local` proxies local traffic only. |
| `tproxy_listen_port` | `7895` | Engine's TPROXY inbound listen port. **Also the delivery point of DNS transparent interception.** |
| `tproxy_uid` / `tproxy_gid` | `13` / `13` | Engine runtime identity; its packets get the bypass mark (loop prevention). |
| `tproxy_route_table` | `224` | Policy routing table number. |
| `tproxy_fwmark` | `224` | fwmark selecting the policy routing table. |
| `tproxy_bypass_mark` | `225` | fwmark for engine-originated traffic (bypass). |
| `tproxy_interface` / `tproxy_interface6` | fact-detected | Exit interfaces. |
| `tproxy_enable_ipv6` | fact-detected | IPv6 interception support; override to force. |
| `tproxy_bypass_cidr4` / `tproxy_bypass_cidr6` | `[]` | Kernel-level bypass CIDRs (never enter the proxy path). |
| `tproxy_reject_cidr4` / `tproxy_reject_cidr6` | `[]` | Kernel-level reject CIDRs. |
| `tproxy_sysctl_nf_conntrack*` | see defaults | conntrack tuning for the interception path. |
| `tproxy_etc_resolv_conf` / `tproxy_etc_resolv_conf_servers` | `true` / `1.1.1.1, 1.0.0.1` | Optional static `/etc/resolv.conf`. |
| `tproxy_tcp_bbr_enabled` | `true` | **Temporary.** BBR sysctl is shipped here until its final home is decided; do not build on it. |

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
