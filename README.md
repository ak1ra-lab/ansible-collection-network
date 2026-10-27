# ansible-collection-network

Shared Ansible roles for network infrastructure, published as the
`ak1ra_lab.network` collection.

## Roles

| Role | Description |
| --- | --- |
| `ak1ra_lab.network.tproxy` | Engine-agnostic TPROXY transparent proxy plumbing: nftables marking, policy routing (`ip rule` / `ip route`), sysctl. Any proxy engine with a TPROXY inbound (sing-box, mihomo, ...) plugs in via variables. |
| `ak1ra_lab.network.flow_offload` | nftables flowtable offloading for forwarded traffic (opt-in). |
| `ak1ra_lab.network.proxy_guard` | Per-client TCP abuse protection (throttle / auto-ban) for transparent-proxy gateways (opt-in). |
| `ak1ra_lab.network.systemd_bridge` | Declarative host-level Linux bridges (one per dedicated physical interface) via systemd-networkd: `.netdev` + enslave `.network` files, NetworkManager unmanaged-devices drop-ins. Stable shared infrastructure (opt-in). |
| `ak1ra_lab.network.systemd_netns` | Dedicated-segment egress isolation: bridged network namespaces for per-service egress over the shared host-level bridges of `systemd_bridge` - namespace veth legs with real segment addresses and an arbitrary per-service next-hop gateway (e.g. a TPROXY gateway when only the hooked service should be proxied). No host-side routing/NAT (opt-in). |
| `ak1ra_lab.network.mihomo_install` | Shared mihomo binary installer: the official statically linked `.gz` archive from the MetaCubeX/mihomo GitHub releases (resolved with `ak1ra_lab.general.github_releases_info`: platform + amd64 microarchitecture asset selection, digest checksum) decompressed to `/usr/local/bin/mihomo`. Distribution-neutral on systemd-based Linux; no package manager, no service identity. Version policy `present` / `latest` / pinned. |
| `ak1ra_lab.network.mihomo_client` | mihomo TUN transparent-proxy client (LAN gateway or host-only), based on the hand-written [mihomo-setup](https://github.com/ak1ra-lab/mihomo-setup) deployment with the sing-box-tproxy group topology: service identity, profile and unit (the binary comes from `mihomo_install` via the playbook), the rule-set bundle from GitHub releases (resolved with `ak1ra_lab.general.github_releases_info`), two hand-maintained profile templates (plain and selfhost-tier; static TUN/DNS/sniffer/rule-set YAML plus a handful of rendered values; copy one to customize) with an explicit rule-set DNS split, region-based proxy groups, inline custom rule sets driven by payload lists, the systemd-resolved/`:53` handover, `tun` module persistence, the gateway sysctl drop-in and an optional controller-local profile mirror. |
| `ak1ra_lab.network.mihomo_server` | mihomo proxy server for the VPS side: `listeners:` for shadowsocks/trojan/hysteria2/vless/tuic/anytls with auto-generated (and re-runnable/idempotent) credentials and manual TLS paths, plus the clash-format client artifact (`config/client_outbounds/<host>.proxies.yaml`) and host_vars credentials consumed by `mihomo_client`. |

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
| `ak1ra_lab.network.systemd_bridge` | Thin wrapper around the `systemd_bridge` role (root privileges, fact gathering); drive it entirely through the `systemd_bridge_*` variable contract. |
| `ak1ra_lab.network.systemd_netns` | Entry point for the `systemd_netns` role: applies the host bridges declared for the run (`systemd_bridge_bridges`) first, then the namespace (root privileges, fact gathering); the `systemd_netns_*` contract drives the namespace. |
| `ak1ra_lab.network.mihomo_install` | Thin wrapper around the `mihomo_install` role (binary only, root privileges, fact gathering); the `mihomo_install_*` contract drives it. |
| `ak1ra_lab.network.mihomo_client` | Entry point for the `mihomo_client` role: applies `mihomo_install` (the `mihomo_install_*` contract) first, then the client role (`mihomo_client_*`); a binary upgrade restarts `mihomo.service` through the client role's handler. |
| `ak1ra_lab.network.mihomo_server` | Entry point for the `mihomo_server` role: applies `mihomo_install` first, optionally applies `ak1ra_lab.general.certbot` (`mihomo_server_tls_certbot_enabled`), then the server role (root privileges, fact gathering; the `mihomo_server_*` contract). |

```shell
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
`mihomo_server`, `mihomo_server_certbot`) reuse the same containers and each
run prepare, converge, idempotence, verify, the role's teardown (cleanup) and
a teardown verification.  `mihomo_server_certbot` runs on the Debian images
only (Pebble comes from the Debian archive); it issues from a local Pebble
ACME server and verifies the certbot -> role copy -> renewal hook flow.

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
