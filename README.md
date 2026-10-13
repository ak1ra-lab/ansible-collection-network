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
| `ak1ra_lab.network.systemd_netns` | Dedicated-segment egress isolation: bridged network namespaces for per-service egress over the shared host-level bridges of `systemd_bridge` - namespace veth legs with real segment addresses and an arbitrary per-service next-hop gateway (e.g. a TPROXY gateway when only the hooked service should be proxied). No host-side routing/NAT. | opt-in |

## Engine contract

The `tproxy` role is decoupled from any specific proxy engine. The contract is
its variable set: `tproxy_listen_port` (where TPROXY and DNS interception
deliver packets), `tproxy_uid` / `tproxy_gid` (loop-prevention bypass mark),
marks and route table numbers, interfaces, and kernel-level bypass/reject
CIDRs. See `roles/tproxy/README.md` for the full table.

## Control-node requirements

The `systemd_bridge` and `systemd_netns` roles use `ansible.utils` filters
(`ipaddr`, `in_network`) for validation on the control node:

```shell
ansible-galaxy collection install ansible.utils
python -m pip install netaddr   # required by the ansible.utils.ipaddr filter
```

`ansible.utils` itself is installed automatically as a collection
dependency.

## Playbooks

| Playbook | Description |
| --- | --- |
| `ak1ra_lab.network.systemd_bridge` | Thin wrapper around the `systemd_bridge` role (root privileges, fact gathering); drive it entirely through the `systemd_bridge_*` variable contract. |
| `ak1ra_lab.network.systemd_netns` | Entry point for the `systemd_netns` role: applies the host bridges declared for the run (`systemd_bridge_bridges`) first, then the namespace (root privileges, fact gathering); the `systemd_netns_*` contract drives the namespace. |

```shell
ansible-playbook ak1ra_lab.network.systemd_bridge -e systemd_bridge_bridges='[{"name": "br_wan", "interface": "enp36s0"}]'
ansible-playbook ak1ra_lab.network.systemd_netns -e systemd_netns_name=qbittorrent
```

## Testing

Molecule scenarios live under `extensions/molecule/` (collection-testing
layout).  The `default` scenario owns the shared container lifecycle
(`shared_state: true`); the component scenarios (`systemd_bridge`,
`systemd_netns`) reuse the same containers and each run prepare, converge,
idempotence, verify, the role's teardown (cleanup) and a teardown
verification.

The managed nodes are the systemd-enabled container images from
[ak1ra-lab/docker-systemd](https://github.com/ak1ra-lab/docker-systemd)
that these roles support: `debian:12`, `debian:13`, `ubuntu:24.04`,
`ubuntu:26.04`.  The roles require `systemd-networkd`, which is not
available on the RHEL family; Fedora would additionally need the separate
`systemd-networkd` package and `iproute` package name.

```shell
# First run only: the scenarios search the project-local collections path
# (ANSIBLE_COLLECTIONS_PATH in extensions/molecule/config.yml), and the
# default scenario creates the shared containers before Molecule installs
# anything itself.
just ansible-collection-install
ansible-galaxy collection install -r requirements.yml -p .ansible/collections

just molecule-test                   # every scenario (recursive glob)
just molecule-test-one systemd_netns # one scenario
just molecule-list
```

Podman is required.  Run it rootful (as the CI does): the `systemd_netns`
unit uses `ip netns exec`, whose recursive `/sys` bind mount is not
permitted inside the rootless user namespace.  When iterating with
`molecule create` plus `molecule converge -s <scenario>`, pass `molecule
prepare --force -s <scenario>` first if the shared "prepared" state is
already set.

## Install

```shell
ansible-galaxy collection install git+https://github.com/ak1ra-lab/ansible-collection-network.git
```
