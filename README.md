# ansible-collection-network

Shared Ansible roles for network infrastructure, published as the
`ak1ra_lab.network` collection.

## Roles

| Role | Description | Default |
| --- | --- | --- |
| `ak1ra_lab.network.tproxy` | Engine-agnostic TPROXY transparent proxy plumbing: nftables marking, policy routing (`ip rule` / `ip route`), sysctl. Any proxy engine with a TPROXY inbound (sing-box, mihomo, ...) plugs in via variables. | always applied |
| `ak1ra_lab.network.flow_offload` | nftables flowtable offloading for forwarded traffic. | opt-in |
| `ak1ra_lab.network.proxy_guard` | Per-client TCP abuse protection (throttle / auto-ban) for transparent-proxy gateways. | opt-in |

## Engine contract

The `tproxy` role is decoupled from any specific proxy engine. The contract is
its variable set: `tproxy_listen_port` (where TPROXY and DNS interception
deliver packets), `tproxy_uid` / `tproxy_gid` (loop-prevention bypass mark),
marks and route table numbers, interfaces, and kernel-level bypass/reject
CIDRs. See `roles/tproxy/README.md` for the full table.

## Install

```shell
ansible-galaxy collection install git+https://github.com/ak1ra-lab/ansible-collection-network.git
```
