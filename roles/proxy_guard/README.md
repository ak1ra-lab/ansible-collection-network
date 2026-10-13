# ak1ra_lab.network.proxy_guard

Per-client TCP abuse protection for transparent-proxy gateways, implemented as
a standalone nftables table. Independent opt-in role: does not depend on
`ak1ra_lab.network.tproxy`.

## How it works

Two chains are used:

- `chain prerouting` (priority filter 0) — rate-limiting and auto-ban
  enforcement. Fires **AFTER** the TPROXY redirect at prerouting mangle (-150)
  and BEFORE socket delivery. Scoped to LAN subnet sets so WAN return traffic
  is never rate-limited.
- `chain input` (priority filter 0) — `ct state invalid drop`. Fires AFTER the
  routing decision; only packets destined for this machine reach this hook.
  Placed here (not in prerouting) so that forwarded LAN-to-LAN traffic is not
  affected: in bypass-router deployments intra-LAN reply packets arrive via the
  default route but their SYN bypassed the gateway entirely, leaving no
  conntrack entry — prerouting would classify them as invalid and drop them.
  TPROXY-redirected and explicit-proxy connections are delivered to local
  sockets and therefore pass through the input hook — they remain fully
  protected.

Protection layers (evaluation order):

1. `[prerouting]` `fib saddr local accept` — skip rate-limiting for the
   gateway's own traffic (otherwise the gateway could throttle/ban itself and
   break proxy operation entirely).
2. `[prerouting]` auto-ban enforcement — drop ALL TCP (new + established) from
   banned IPs.
3. `[prerouting]` auto-ban detection — rate meter; ban IPs exceeding the hard
   threshold.
4. `[prerouting]` throttle enforcement — drop NEW TCP only from throttled IPs
   (softer).
5. `[prerouting]` throttle detection — rate meter; throttle IPs exceeding the
   soft threshold.
6. `[input]` `ct state invalid drop` — only for locally-destined traffic.

A throttled client that keeps aggressively retrying new connections still
accumulates counts in the auto-ban rate meter (step 3 fires before step 4
drops), so persistent abuse can escalate from throttle to full auto-ban
automatically. Ban/throttle set entries use add-once timeout semantics — the
timer is written exactly once and cannot be extended by further packets.

## Variables

| Variable | Default | Description |
| --- | --- | --- |
| `proxy_guard_state` | `present` | `present` applies the table; `absent` removes the table file this role created. |
| `proxy_guard_enabled` | `false` | Master switch: when disabled the role removes the drop-in it created (and otherwise touches nothing); review all parameters before enabling. |
| `proxy_guard_lan4_subnets` | RFC 1918 trio | LAN prefixes subject to protection. |
| `proxy_guard_lan6_subnets` | `[]` | IPv6 LAN prefixes (empty = IPv6 protection disabled). |
| `proxy_guard_throttle_enabled` / `_rate` / `_burst` / `_timeout` | `false` / `600` / `150` / `2m` | Soft protection: drops only NEW TCP from throttled IPs. |
| `proxy_guard_auto_ban_enabled` / `_rate` / `_burst` / `_timeout` | `false` / `1200` / `300` / `5m` | Hard protection: drops ALL TCP from banned IPs. |

## Deployed artifact

`/etc/nftables.d/ansible_proxy_guard.nft` — `table inet ansible_proxy_guard`,
picked up by the `include "/etc/nftables.d/*.nft"` glob in the base
`nftables.conf` deployed by `ak1ra_lab.network.tproxy` (or any equivalent base
config).
