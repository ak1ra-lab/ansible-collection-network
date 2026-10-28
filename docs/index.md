---
hide:
  - toc
---

# ak1ra_lab.network

Shared Ansible roles for network infrastructure. The collection covers
transparent-proxy plumbing, optional nftables helpers, and systemd-networkd
host networking.

## Start here

- [Getting started](getting-started.md) - install the collection and prepare
  the control and managed nodes.
- [Architecture](architecture.md) - how the role families fit together.
- [Playbooks](playbooks.md) - collection entry points and host defaults.
- [Roles](roles/index.md) - the canonical role contracts.
- [Plugins](ak1ra_lab.network/index.md) - generated filter and lookup
  reference.
- [Contributing](contributing.md) - development, testing, and docs workflow.
- [Changelog](changelog.md) - release history.

!!! note "Installation source"
    The collection is currently installed from git, not from Galaxy. Use the
    install command in [Getting started](getting-started.md); the generated
    plugin pages show the eventual Galaxy FQCN for reference.

Role documentation is maintained as each role's `README.md` and rendered in
the Roles section. The generated collection page under Plugins covers the
filter and lookup plugins only.

## Design at a glance

The proxy roles are deliberately split by engine and by deployment shape:

- `tproxy` is the engine-agnostic TPROXY plumbing. It marks and routes
  traffic but installs no proxy engine; an engine with a TPROXY inbound plugs
  in through variables.
- `mihomo_client` uses mihomo's TUN inbound instead of the TPROXY contract.
  It does not depend on `tproxy`.
- `mihomo_server` produces the VPS-side listeners and the clash-format client
  nodes consumed by `mihomo_client`; `mihomo_install` only owns the binary.
- `flow_offload` and `proxy_guard` are independent opt-in nftables roles.
- `systemd_bridge` owns shared host bridges; `systemd_netns` consumes them for
  per-service egress isolation.
- `cloud_init`, `netplan_static`, and `systemd_resolved` move a cloud image
  from cloud-init-managed networking to a static netplan file and a
  systemd-resolved host resolver.

The role READMEs are the source of truth for variables and deployed
artifacts. Plugin reference pages are generated from the `DOCUMENTATION`
blocks in `plugins/`.
