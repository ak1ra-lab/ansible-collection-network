# ansible-collection-network

Shared Ansible roles for network infrastructure, published as the
`ak1ra_lab.network` collection.

## Roles

| Role | Description |
| --- | --- |
| `ak1ra_lab.network.tproxy` | Engine-agnostic TPROXY transparent proxy plumbing: nftables marking, policy routing (`ip rule` / `ip route`), sysctl. Any proxy engine with a TPROXY inbound (sing-box, mihomo, ...) plugs in via variables. |
| `ak1ra_lab.network.flow_offload` | nftables flowtable offloading for forwarded traffic (opt-in). |
| `ak1ra_lab.network.proxy_guard` | Per-client TCP abuse protection (throttle / auto-ban) for transparent-proxy gateways (opt-in). |
| `ak1ra_lab.network.cloud_init` | cloud-init drop-ins under `/etc/cloud/cloud.cfg.d`: network ownership (`network: {config: disabled}`, optional `disable_network_activation`), stable SSH host keys (`ssh_deletekeys: false`), `/etc/hosts`/hostname preservation and a raw `cloud_init_extra_config` escape hatch. Defaults are no-ops. |
| `ak1ra_lab.network.netplan_static` | Captures the live IPv4 state of the physical ethernet interfaces into a static netplan file (primary + `ipv4_secondaries`, one default gateway, optional nameservers), backs up/removes cloud-init's `50-cloud-init.yaml`, and validates/applies with netplan. A merge-aware conflict policy (`strict` / `overlap` / `none`) allows complementary split files such as a separate `mtu` file while failing on later key overrides or duplicate device claims. IPv4-only and fail-closed on IPv6; advanced netplan features use the custom-template escape hatch. |
| `ak1ra_lab.network.systemd_resolved` | systemd-resolved host resolver: global DNS/FallbackDNS/Domains, DoT, stub listener and the `/etc/resolv.conf` `stub`/`uplink`/`static`/`unmanaged` mode. No static-file mode; `tproxy` and `mihomo_client` own their respective static resolver files. |
| `ak1ra_lab.network.systemd_bridge` | Declarative host-level Linux bridges (one per dedicated physical interface) via systemd-networkd: `.netdev` + enslave `.network` files, NetworkManager unmanaged-devices drop-ins. Stable shared infrastructure (opt-in). |
| `ak1ra_lab.network.systemd_netns` | Dedicated-segment egress isolation: bridged network namespaces for per-service egress over the shared host-level bridges of `systemd_bridge` - namespace veth legs with real segment addresses and an arbitrary per-service next-hop gateway (e.g. a TPROXY gateway when only the hooked service should be proxied). No host-side routing/NAT (opt-in). |
| `ak1ra_lab.network.mihomo_install` | Shared mihomo binary installer: the official statically linked `.gz` archive from the MetaCubeX/mihomo GitHub releases (resolved with `ak1ra_lab.general.github_releases_info`: platform + amd64 microarchitecture asset selection, digest checksum) decompressed to `/usr/local/bin/mihomo`. Distribution-neutral on systemd-based Linux; no package manager, no service identity. Version policy `present` / `latest` / pinned. |
| `ak1ra_lab.network.mihomo_client` | mihomo TUN transparent-proxy client (LAN gateway or host-only), based on the hand-written [mihomo-setup](https://github.com/ak1ra-lab/mihomo-setup) deployment with the sing-box-tproxy group topology: service identity, profile and unit (the binary comes from `mihomo_install` via the playbook), the rule-set bundle from GitHub releases (resolved with `ak1ra_lab.general.github_releases_info`), two hand-maintained profile templates (plain and selfhost-tier; static TUN/DNS/sniffer/rule-set YAML plus a handful of rendered values; copy one to customize) with an explicit rule-set DNS split, region-based proxy groups, inline custom rule sets driven by payload lists, the systemd-resolved/`:53` handover, `tun` module persistence, the gateway sysctl drop-in and an optional controller-local profile mirror. |
| `ak1ra_lab.network.mihomo_server` | mihomo proxy server for the VPS side: `listeners:` for shadowsocks/trojan/hysteria2/vless/tuic/anytls with auto-generated (and re-runnable/idempotent) credentials and manual TLS paths, optional AnyTLS JLS outer TLS with a destination fallback, plus the clash-format client artifact (`config/client_outbounds/<host>.proxies.yaml`) and host_vars credentials consumed by `mihomo_client`. |

## Cloud-image network takeover

`cloud_init`, `netplan_static` and `systemd_resolved` are independent roles;
compose them in a site playbook in that order when a cloud image should stop
letting cloud-init own its network configuration:

```yaml
- hosts: cloud-image-vms
  become: true
  gather_facts: true
  tasks:
    - import_role:
        name: ak1ra_lab.network.cloud_init
      vars:
        cloud_init_network: disabled
        cloud_init_ssh_deletekeys: false
    - import_role:
        name: ak1ra_lab.network.netplan_static
    - meta: flush_handlers
    - import_role:
        name: ak1ra_lab.network.systemd_resolved
```

Scenario values (direct gateway, TPROXY gateway, per-host address/prefix
exceptions) belong in `group_vars`/`host_vars`, not in copied playbooks.
`netplan_static` backs up cloud-init's `50-cloud-init.yaml` and refuses to
remove its own file without a restoreable backup; the handback order is
documented in `roles/netplan_static/README.md`.

Only one role may own `/etc/resolv.conf` on a host: `systemd_resolved` (keeps
resolved running), `tproxy` (advisory static file for a TPROXY gateway) or
`mihomo_client` (stops resolved and points the file at the mihomo DNS
listener). Do not combine those owners.

## Backup convention

Role-managed rollback backups live under:

```text
/var/lib/ansible/<namespace>/<collection>/<role>/<absolute-path-without-leading-slash>
```

For example:

```text
/var/lib/ansible/ak1ra_lab/network/netplan_static/etc/netplan/50-cloud-init.yaml
/var/lib/ansible/ak1ra_lab/network/systemd_resolved/etc/resolv.conf
```

`/var/lib` is the FHS location for application state. `/var/backups` is a
Debian-specific convention and is not part of the FHS or XDG; XDG covers
per-user directories, not system-wide role state. The backup path is fixed
(first backup wins), so it stays bounded and is easy to restore. It is not a
timestamped history. `ansible.builtin.copy` / `template` with
`backup: true` writes timestamped files next to the destination and has no
backup-directory option, so the roles use an explicit copy to the fixed path
instead.

## Engine contract

The `tproxy` role is decoupled from any specific proxy engine. The contract is
its variable set: `tproxy_listen_port` (where TPROXY and DNS interception
deliver packets), `tproxy_uid` / `tproxy_gid` (loop-prevention bypass mark),
marks and route table numbers, interfaces, and kernel-level bypass/reject
CIDRs. See `roles/tproxy/README.md` for the full table.

`mihomo_client` deliberately does **not** consume the `tproxy` contract: it
reproduces the `mihomo-setup` TUN design (`auto-route` + `auto-redirect` +
`auto-detect-interface` + `dns-hijack`), which needs no nftables marking and
no policy-routing service.  The `tproxy` role remains the engine-agnostic
plumbing for engines with a TPROXY inbound (sing-box, ...).

## Control-node requirements

The `systemd_bridge` and `systemd_netns` roles use `ansible.utils` filters
(`ipaddr`, `in_network`) for validation on the control node:

```shell
ansible-galaxy collection install ansible.utils
python -m pip install netaddr   # required by the ansible.utils.ipaddr filter
```

`ansible.utils` itself is installed automatically as a collection
dependency.

The `mihomo_install` / `mihomo_client` / `mihomo_server` roles resolve GitHub
release assets with the `ak1ra_lab.general.github_releases_info` module and
detect the amd64 microarchitecture level with
`ak1ra_lab.general.cpu_info`.
The optional certbot orchestration in `mihomo_server` also needs the
`ak1ra_lab.general.certbot` role (general >= 0.3.0).

`ak1ra_lab.general` is not published to Galaxy yet; consumers add it to their
requirements and install it from git:

```yaml
collections:
  - name: git+https://github.com/ak1ra-lab/ansible-collection-general.git
    version: master
```

For development in this repository, `just ansible-collection-install`
installs the collection from the local `../ansible-collection-general`
checkout instead, so the roles can be tested against unpushed changes;
override the path with `GENERAL_COLLECTION=/path/to/checkout` when working
from a git worktree.

## Playbooks

| Playbook | Description |
| --- | --- |
| `ak1ra_lab.network.cloud_init` | Thin wrapper around the `cloud_init` role (root privileges, fact gathering); the `cloud_init_*` contract drives it. |
| `ak1ra_lab.network.netplan_static` | Thin wrapper around the `netplan_static` role (root privileges, fact gathering); the playbook can change the network path, so target an explicit inventory group and keep console access. |
| `ak1ra_lab.network.systemd_resolved` | Thin wrapper around the `systemd_resolved` role (root privileges, fact gathering); the `systemd_resolved_*` contract drives it. |
| `ak1ra_lab.network.systemd_bridge` | Thin wrapper around the `systemd_bridge` role (root privileges, fact gathering); drive it entirely through the `systemd_bridge_*` variable contract. |
| `ak1ra_lab.network.systemd_netns` | Entry point for the `systemd_netns` role: applies the host bridges declared for the run (`systemd_bridge_bridges`) first, then the namespace (root privileges, fact gathering); the `systemd_netns_*` contract drives the namespace. |
| `ak1ra_lab.network.mihomo_install` | Thin wrapper around the `mihomo_install` role (binary only, root privileges, fact gathering); the `mihomo_install_*` contract drives it. |
| `ak1ra_lab.network.mihomo_client` | Entry point for the `mihomo_client` role: applies `mihomo_install` (the `mihomo_install_*` contract) first, then the client role (`mihomo_client_*`); a binary upgrade restarts `mihomo.service` through the client role's handler. |
| `ak1ra_lab.network.mihomo_server` | Entry point for the `mihomo_server` role: applies `mihomo_install` first, optionally applies `ak1ra_lab.general.certbot` (`mihomo_server_tls_certbot_enabled`), then the server role (root privileges, fact gathering; the `mihomo_server_*` contract). |

```shell
ansible-playbook ak1ra_lab.network.cloud_init -e playbook_hosts=cloud-image-vms
ansible-playbook ak1ra_lab.network.netplan_static -e playbook_hosts=cloud-image-vms
ansible-playbook ak1ra_lab.network.systemd_resolved -e playbook_hosts=cloud-image-vms
ansible-playbook ak1ra_lab.network.systemd_bridge -e systemd_bridge_bridges='[{"name": "br_wan", "interface": "enp36s0"}]'
ansible-playbook ak1ra_lab.network.systemd_netns -e systemd_netns_name=qbittorrent
ansible-playbook ak1ra_lab.network.mihomo_client -e mihomo_install_version=latest
ansible-playbook ak1ra_lab.network.mihomo_server -e mihomo_install_version=latest
```

## Testing

Molecule scenarios live under `extensions/molecule/` (collection-testing
layout).  The `default` scenario owns the shared container lifecycle
(`shared_state: true`); the component scenarios (`flow_offload`,
`proxy_guard`, `systemd_bridge`, `systemd_netns`, `tproxy`, `mihomo_client`,
`mihomo_server`, `mihomo_server_certbot`, `cloud_init`, `netplan_static`,
`systemd_resolved`) reuse the same containers and each run prepare, converge,
idempotence, verify, the role's teardown (cleanup) and a teardown
verification.  `mihomo_server_certbot` runs on the Debian images only
(Pebble comes from the Debian archive); it issues from a local Pebble ACME
server and verifies the certbot -> role copy -> renewal hook flow.  The
`netplan_static` scenario sets `netplan_static_apply: false`, validates
the rendered file with `netplan generate`, and keeps a complementary
`10-mtu.yaml` file to exercise the merge-aware conflict policy; applying a
real network change and the reboot/handback behaviour are VM-level checks,
not container checks.

Development tooling is uv-managed (`pyproject.toml`, `ruff.toml`): `just
sync` creates the environment, `just lint` runs ruff (check + format) over
`plugins/` and `tests/`, and `just typecheck` runs ty over both.  The filter
and lookup plugins have plain pytest unit tests under `tests/unit/`
(`plugins/filter/` and `plugins/lookup/` are put on `sys.path` by
`tests/unit/conftest.py`; no collection install required):

```shell
just unit-test              # uv run pytest tests/unit -q
```

The managed nodes are the systemd-enabled container images from
[ak1ra-lab/docker-systemd](https://github.com/ak1ra-lab/docker-systemd)
that these roles support: `debian:12`, `debian:13`, `ubuntu:24.04`,
`ubuntu:26.04`.  The systemd roles require `systemd-networkd`, which is not
available on the RHEL family; Fedora would additionally need the separate
`systemd-networkd` package and `iproute` package name.

The molecule recipes install the collection under test, the scenario
requirements (`requirements.yaml`) and the local `ak1ra_lab.general`
checkout into `.ansible/collections` before every run.  The scenarios search
that project-local path (`ANSIBLE_COLLECTIONS_PATH` in
`extensions/molecule/config.yml`), and the shared `default` scenario creates
the containers before Molecule installs anything itself.

```shell
just molecule-test                   # every scenario (recursive glob)
just molecule-test-one systemd_netns # one scenario
just molecule-list
```

Podman is required.  Run it rootful (as the CI does): the `systemd_netns`
unit uses `ip netns exec`, whose recursive `/sys` bind mount is not
permitted inside the rootless user namespace, and the `tproxy` scenario
loads host kernel modules (`modprobe nft_tproxy`, `tcp_bbr`, ...), which
rootless Podman cannot do inside a user namespace either.  Every container
is also created privileged (systemd needs the capabilities, and the shared
udev preparation needs a writable `/sys`), and the host kernel module tree
is bind-mounted read-only into the containers through the inventory's
`container_volumes`.  When iterating with `molecule create` plus `molecule
converge -s <scenario>`, pass `molecule prepare --force -s <scenario>` first
if the shared "prepared" state is already set.

A rootful Docker daemon is supported as an alternative to Podman: set
`MOLECULE_CONTAINER_RUNTIME=docker` for every molecule invocation.  The
containers are then managed through `community.docker` (installed from the
root `requirements.yaml`; the `docker` Python SDK must be available to
Ansible) and run privileged, like the Podman path: systemd needs the
capabilities, and a privileged container also gets a writable `/sys` for
the shared udev net-event trigger.

The `tproxy` scenario switches off the role's host-only facets, which the
shared containers cannot carry: the static `/etc/resolv.conf` (a
bind-mounted file, so the atomic replace of the template module fails) and
the `tcp_bbr` / `nf_conntrack` sysctl tuning (host-global or not writable
from a container network namespace, which would make the idempotence check
fail).  The `mihomo_client` scenario switches off
`mihomo_client_dns_manage_resolv_conf` for the same bind-mount reason; it
still exercises the systemd-resolved handover (the `prepare` installs and
starts the service, the role stops/disables it, teardown restores it).  The
`flow_offload` and `proxy_guard` scenarios deploy the minimal base nftables
config (the include glob) that a real host gets from
`ak1ra_lab.network.tproxy`, so their tables can be asserted live.

## Install

```shell
ansible-galaxy collection install git+https://github.com/ak1ra-lab/ansible-collection-network.git
```
