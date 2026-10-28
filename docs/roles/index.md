---
hide:
  - toc
---

# Roles

Each page below is the canonical `roles/<role>/README.md`, included in the
docs site from the role directory. Edit the role README, not this index, when
the contract changes.

| Role | Description |
| --- | --- |
| [`tproxy`](tproxy.md) | Engine-agnostic TPROXY plumbing: nftables marks, policy routing, sysctl. |
| [`flow_offload`](flow_offload.md) | nftables flowtable offloading for forwarded traffic. |
| [`proxy_guard`](proxy_guard.md) | Per-client TCP throttle and auto-ban for transparent-proxy gateways. |
| [`systemd_bridge`](systemd_bridge.md) | Declarative host-level Linux bridges through systemd-networkd. |
| [`systemd_netns`](systemd_netns.md) | Bridged network namespaces for per-service egress isolation. |
| [`cloud_init`](cloud_init.md) | cloud-init drop-ins for network ownership, stable SSH host keys, and host identity. |
| [`netplan_static`](netplan_static.md) | Captures the live IPv4 state into a static netplan file and takes over from cloud-init. |
| [`systemd_resolved`](systemd_resolved.md) | systemd-resolved host resolver and `/etc/resolv.conf` mode management. |
| [`mihomo_install`](mihomo_install.md) | Static mihomo binary installer from GitHub releases. |
| [`mihomo_client`](mihomo_client.md) | mihomo TUN transparent-proxy client. |
| [`mihomo_server`](mihomo_server.md) | mihomo proxy server with generated client artifacts. |

## Role families

- Transparent proxy: `tproxy`, `flow_offload`, `proxy_guard`.
- mihomo: `mihomo_install`, `mihomo_client`, `mihomo_server`.
- Host networking: `systemd_bridge`, `systemd_netns`.
- Cloud-image network takeover: `cloud_init`, `netplan_static`,
  `systemd_resolved`.

`tproxy`, `flow_offload`, `proxy_guard`, `systemd_bridge`,
`systemd_netns`, `cloud_init`, `netplan_static`, and `systemd_resolved` are
independent and opt-in. `mihomo_client` and `mihomo_server` do not depend on
`tproxy`; their playbooks apply `mihomo_install` first. The cloud-image roles
compose in a site playbook but never call each other.
