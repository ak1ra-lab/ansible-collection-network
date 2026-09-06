# ansible-collection-network

Shared Ansible roles for network infrastructure, published as the
`ak1ra_lab.network` collection.

## Roles

| Role | Description | Default |
| --- | --- | --- |
| `ak1ra_lab.network.tproxy` | Engine-agnostic TPROXY transparent proxy plumbing: nftables marking, policy routing (`ip rule` / `ip route`), sysctl. Any proxy engine with a TPROXY inbound (sing-box, mihomo, ...) plugs in via variables. | always applied |
| `ak1ra_lab.network.flow_offload` | nftables flowtable offloading for forwarded traffic. | opt-in |
| `ak1ra_lab.network.proxy_guard` | Per-client TCP abuse protection (throttle / auto-ban) for transparent-proxy gateways. | opt-in |
| `ak1ra_lab.network.systemd_bridge` | Declarative host-level Linux bridges (one per dedicated physical interface) via systemd-networkd: `.netdev` + enslave `.network` files, NetworkManager unmanaged-devices drop-ins. Stable shared infrastructure. | opt-in |
| `ak1ra_lab.network.systemd_netns` | Dedicated-segment egress isolation: bridged network namespaces for per-service direct egress - namespace veth legs with real segment addresses attach to the host-level bridges of `systemd_bridge`. No host-side routing/NAT. | opt-in |

## Engine contract

The `tproxy` role is decoupled from any specific proxy engine. The contract is
its variable set: `tproxy_listen_port` (where TPROXY and DNS interception
deliver packets), `tproxy_uid` / `tproxy_gid` (loop-prevention bypass mark),
marks and route table numbers, interfaces, and kernel-level bypass/reject
CIDRs. See `roles/tproxy/README.md` for the full table.

## Control-node requirements

The `systemd_netns` role uses `ansible.utils` filters (`ipaddr`,
`in_network`) for link validation on the control node:

```shell
ansible-galaxy collection install ansible.utils
```

`ansible.utils` itself is installed automatically as a collection
dependency.

## Playbooks

| Playbook | Description |
| --- | --- |
| `ak1ra_lab.network.systemd_bridge` | Thin wrapper around the `systemd_bridge` role (root privileges, fact gathering); drive it entirely through the `systemd_bridge_*` variable contract. |
| `ak1ra_lab.network.systemd_netns` | Thin wrapper around the `systemd_netns` role (root privileges, fact gathering); drive it entirely through the `systemd_netns_*` variable contract. |

```shell
ansible-playbook ak1ra_lab.network.systemd_bridge -e systemd_bridge_bridges='[{"name": "br_wan", "interface": "enp36s0"}]'
ansible-playbook ak1ra_lab.network.systemd_netns -e systemd_netns_name=qbittorrent
```

## Install

```shell
ansible-galaxy collection install git+https://github.com/ak1ra-lab/ansible-collection-network.git
```
