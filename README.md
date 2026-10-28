# ak1ra_lab.network

Shared Ansible roles for network infrastructure, published as the
`ak1ra_lab.network` collection.

Documentation: <https://ak1ra-lab.github.io/ansible-collection-network/>

The collection covers transparent-proxy plumbing, optional nftables helpers,
systemd-networkd host networking, and cloud-image network takeover:

- `tproxy` provides engine-agnostic TPROXY marking, policy routing, and
  sysctl; `mihomo_client` and `mihomo_server` deploy the mihomo TUN client and
  proxy server, with `mihomo_install` sharing the binary installer.
- `flow_offload` and `proxy_guard` are independent opt-in nftables roles for
  forwarded traffic and per-client abuse protection.
- `systemd_bridge` owns host-level Linux bridges; `systemd_netns` builds
  per-service network namespaces on top of them.
- `cloud_init`, `netplan_static`, and `systemd_resolved` take a cloud image
  off cloud-init's network management, capture the live IPv4 state into
  netplan, and put systemd-resolved in charge of the host resolver.

## Install

```shell
ansible-galaxy collection install git+https://github.com/ak1ra-lab/ansible-collection-network.git
```

The `mihomo_*` roles also need `ak1ra_lab.general`, which is not published to
Galaxy yet:

```yaml
collections:
  - name: git+https://github.com/ak1ra-lab/ansible-collection-general.git
    version: master
```

See [Getting started](docs/getting-started.md) for control-node dependencies
and the managed-node matrix.

## Roles

| Role | Description |
| --- | --- |
| [`tproxy`](roles/tproxy/README.md) | Engine-agnostic TPROXY plumbing: nftables marks, policy routing, sysctl. |
| [`flow_offload`](roles/flow_offload/README.md) | nftables flowtable offloading for forwarded traffic. |
| [`proxy_guard`](roles/proxy_guard/README.md) | Per-client TCP throttle and auto-ban for transparent-proxy gateways. |
| [`systemd_bridge`](roles/systemd_bridge/README.md) | Declarative host-level Linux bridges through systemd-networkd. |
| [`systemd_netns`](roles/systemd_netns/README.md) | Bridged network namespaces for per-service egress isolation. |
| [`cloud_init`](roles/cloud_init/README.md) | cloud-init drop-ins for network ownership, stable SSH host keys, and host identity. |
| [`netplan_static`](roles/netplan_static/README.md) | Captures the live IPv4 state into a static netplan file and takes over from cloud-init. |
| [`systemd_resolved`](roles/systemd_resolved/README.md) | systemd-resolved host resolver and `/etc/resolv.conf` mode management. |
| [`mihomo_install`](roles/mihomo_install/README.md) | Static mihomo binary installer from GitHub releases. |
| [`mihomo_client`](roles/mihomo_client/README.md) | mihomo TUN transparent-proxy client. |
| [`mihomo_server`](roles/mihomo_server/README.md) | mihomo proxy server with generated client artifacts. |

The role READMEs are the canonical variable contracts. The docs site renders
them as the role reference.

## Playbooks

| Playbook | Description |
| --- | --- |
| [`systemd_bridge`](playbooks/systemd_bridge.yaml) | Thin wrapper around the `systemd_bridge` role. |
| [`systemd_netns`](playbooks/systemd_netns.yaml) | Applies declared bridges first, then the namespace role. |
| [`cloud_init`](playbooks/cloud_init.yaml) | Thin wrapper around the `cloud_init` role. |
| [`netplan_static`](playbooks/netplan_static.yaml) | Thin wrapper around the `netplan_static` role; keep console access for the first run. |
| [`systemd_resolved`](playbooks/systemd_resolved.yaml) | Thin wrapper around the `systemd_resolved` role. |
| [`mihomo_install`](playbooks/mihomo_install.yaml) | Installs or upgrades the mihomo binary only. |
| [`mihomo_client`](playbooks/mihomo_client.yaml) | Applies `mihomo_install`, then the client role. |
| [`mihomo_server`](playbooks/mihomo_server.yaml) | Applies `mihomo_install`, optional certbot, then the server role. |

Quick examples:

```shell
ansible-playbook ak1ra_lab.network.systemd_bridge -e systemd_bridge_bridges='[{"name": "br_wan", "interface": "enp36s0"}]'
ansible-playbook ak1ra_lab.network.systemd_netns -e systemd_netns_name=qbittorrent
ansible-playbook ak1ra_lab.network.cloud_init -e playbook_hosts=cloud-image-vms
ansible-playbook ak1ra_lab.network.netplan_static -e playbook_hosts=cloud-image-vms
ansible-playbook ak1ra_lab.network.systemd_resolved -e playbook_hosts=cloud-image-vms
ansible-playbook ak1ra_lab.network.mihomo_client -e mihomo_install_version=latest
ansible-playbook ak1ra_lab.network.mihomo_server -e mihomo_install_version=latest
```

See [Playbooks](docs/playbooks.md) for the host defaults and orchestration
details.

## Development

```shell
just sync
just all
just molecule-test
```

`just all` covers lint, typecheck, unit tests, ansible-lint, and the docs
build. Molecule needs a rootful container runtime and is run separately.
See [CONTRIBUTING.md](CONTRIBUTING.md) for the full workflow.

## License

MIT. See [LICENSE](LICENSE).
