# ak1ra_lab.network.flow_offload

> The canonical variable reference is generated from
> [`meta/argument_specs.yml`](meta/argument_specs.yml) in the
> [collection documentation](https://ak1ra-lab.github.io/ansible-collection-network/collection_index.html).
> This README keeps purpose, deployed artifacts, and
> operational notes.

nftables flowtable offloading for forwarded traffic. Independent opt-in role:
owns its own table (`table inet ansible_flow_offload`, forward hook) and does
not depend on `ak1ra_lab.network.tproxy`.

Processed on the forward hook — TPROXY'd traffic is diverted in prerouting and
never reaches this hook, so every forwarded packet here has already been
classified as bypass-proxy traffic.

## Deployed artifact

`/etc/nftables.d/ansible_flow_offload.nft` — picked up by the
`include "/etc/nftables.d/*.nft"` glob in the base `nftables.conf` deployed by
`ak1ra_lab.network.tproxy` (or any equivalent base config).

The role is opt-in: the enable switch defaults off, and disabling it removes
the role's drop-in without touching any other nftables rule. The flowtable
interfaces default to fact-detected Ethernet and bridge devices, so the role
also works on hosts that do not use `tproxy` for their base configuration.
