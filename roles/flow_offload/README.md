# ak1ra_lab.network.flow_offload

nftables flowtable offloading for forwarded traffic. Independent opt-in role:
owns its own table (`table inet ansible_flow_offload`, forward hook) and does
not depend on `ak1ra_lab.network.tproxy`.

Processed on the forward hook — TPROXY'd traffic is diverted in prerouting and
never reaches this hook, so every forwarded packet here has already been
classified as bypass-proxy traffic.

## Variables

| Variable | Default | Description |
| --- | --- | --- |
| `flow_offload_state` | `present` | `present` applies the table; `absent` removes the table file this role created. |
| `flow_offload_enabled` | `false` | Master switch: when disabled the role removes the drop-in it created (and otherwise touches nothing). |
| `flow_offload_interfaces` | fact-detected | Interfaces bound to the flowtable (`eth*`, `enp*`, `ens*`, `enx*`, `br*`). |

## Deployed artifact

`/etc/nftables.d/ansible_flow_offload.nft` — picked up by the `include
"/etc/nftables.d/*.nft"` glob in the base `nftables.conf` deployed by
`ak1ra_lab.network.tproxy` (or any equivalent base config).
