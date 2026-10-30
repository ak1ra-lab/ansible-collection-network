# ak1ra_lab.network

Shared Ansible roles for network infrastructure, published as the
`ak1ra_lab.network` collection.

Documentation: <https://ak1ra-lab.github.io/ansible-collection-network/>
Release notes: [CHANGELOG.rst](CHANGELOG.rst)

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

## Roles

| Role | Purpose |
| --- | --- |
| [`tproxy`](roles/tproxy/README.md) | **Experimental.** Engine-agnostic TPROXY plumbing: nftables marks, policy routing, sysctl. |
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

The role argument specs (`roles/<role>/meta/argument_specs.yml`) are the
canonical variable reference and are rendered in the generated role
reference. The role READMEs keep purpose, requirements, deployed artifacts,
examples, and operational notes.

## Requirements

- Controller: `ansible-core >= 2.19.0`; tested with ansible-core 2.19, 2.20,
  and 2.21 (plus the weekly `devel`/`milestone` builds).
- Controller Python: `>= 3.11`; tested with Python 3.11, 3.12, and 3.13.
  ansible-core 2.20 and 2.21 additionally support Python 3.12-3.14.
- Controller Python package: `netaddr` for the `ansible.utils.ipaddr` filter
  used by address validation (see [`requirements.txt`](requirements.txt)).
- Managed nodes: systemd-based Debian/Ubuntu. Tested images are Debian 12
  (target Python 3.11), Debian 13 (target Python 3.13), and Ubuntu 24.04
  (target Python 3.12). The roles use the managed node's `/usr/bin/python3`.
- Collections: `ak1ra_lab.general >= 0.4.0`, `ansible.posix >= 1.5.4`,
  `community.general >= 8.0.0`, and `ansible.utils >= 6.0.0` (resolved from
  [`galaxy.yml`](galaxy.yml)).

`ak1ra_lab.network` depends on `ak1ra_lab.general` for `cpu_info`,
`github_releases_info`, and the `random_*` lookups. Galaxy resolves that
dependency automatically.

## Install

Install the released collection from Ansible Galaxy:

```shell
ansible-galaxy collection install ak1ra_lab.network
```

Or pin it in a consumer `requirements.yml`:

```yaml
---
collections:
  - name: ak1ra_lab.network
    version: ">=0.4.0"
```

```shell
ansible-galaxy collection install -r requirements.yml
```

Galaxy also installs `ak1ra_lab.general >= 0.4.0` and the other declared
dependencies. Certificate issuance is **not** part of this collection; the
consumer supplies the TLS material.

See [Getting started](docs/docsite/rst/getting-started.rst) for control-node
dependencies and the managed-node matrix.

## Versioning and deprecation

The collection follows semantic versioning once it reaches `1.0.0`. Before
`1.0.0`, a minor release may contain a documented breaking change; patch
releases are limited to compatible fixes.

- Breaking changes are listed under **Breaking Changes / Porting Guide** in
  [CHANGELOG.rst](CHANGELOG.rst).
- Deprecated role variables and features are documented in the changelog and
  the role reference, and remain available for at least one minor release
  before removal. Before `1.0.0`, removal may happen in a minor release.
- `tproxy` is experimental: its name is stable, but its contract may change
  without a deprecation cycle until it is promoted.
- Raising the minimum ansible-core or Python version is treated as a breaking
  change.
- The `galaxy.yml` version, the Git tag (`vX.Y.Z`), and the changelog release
  must match for every release.

Release order for the `ak1ra_lab` collections:

1. `ak1ra_lab.general 0.4.0`
2. `ak1ra_lab.network 0.4.0` (depends on general `>=0.4.0`)

## Playbooks

This collection ships roles and filter plugins only. The operational
playbooks that compose them live in the separate
[`ansible-playbooks-services`](https://github.com/ak1ra-lab/ansible-playbooks-services)
repository, together with their inventories and playbook-level variables.
See [Playbooks](docs/docsite/rst/playbooks.rst) for details.

## Communication

- Ansible Forum: use the [`ak1ra-lab` tag](https://forum.ansible.com/tag/ak1ra-lab)
  for questions and usage discussions.
- Bug reports and feature requests:
  <https://github.com/ak1ra-lab/ansible-collection-network/issues>
- Code of Conduct: [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md), which points to
  the [Ansible Community Code of Conduct](https://docs.ansible.com/ansible/latest/community/code_of_conduct.html).

## Development

```shell
just sync
just all
just molecule-test
```

`just all` covers lint, mypy, unit tests, ansible-lint, changelog lint, docs
lint, and the docs build. `just tox-list` shows the standard tox-ansible
ansible-core/Python matrix. Molecule runs separately with isolated
per-scenario containers; rootless Podman covers most scenarios and
`systemd_netns`/`tproxy` need rootful. See [CONTRIBUTING.md](CONTRIBUTING.md)
for the full workflow and release checklist.

## License

GPL-3.0-or-later. See [LICENSE](LICENSE).
