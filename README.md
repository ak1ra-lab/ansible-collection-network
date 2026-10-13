# ansible-collection-network

Shared Ansible roles for network infrastructure, published as the
`ak1ra_lab.network` collection.

## Roles

| Role | Description |
| --- | --- |
| `ak1ra_lab.network.tproxy` | Engine-agnostic TPROXY transparent proxy plumbing: nftables marking, policy routing (`ip rule` / `ip route`), sysctl. Any proxy engine with a TPROXY inbound (sing-box, mihomo, ...) plugs in via variables. |
| `ak1ra_lab.network.flow_offload` | nftables flowtable offloading for forwarded traffic (opt-in). |
| `ak1ra_lab.network.proxy_guard` | Per-client TCP abuse protection (throttle / auto-ban) for transparent-proxy gateways (opt-in). |

## Engine contract

The `tproxy` role is decoupled from any specific proxy engine. The contract is
its variable set: `tproxy_listen_port` (where TPROXY and DNS interception
deliver packets), `tproxy_uid` / `tproxy_gid` (loop-prevention bypass mark),
marks and route table numbers, interfaces, and kernel-level bypass/reject
CIDRs. See `roles/tproxy/README.md` for the full table.

## Testing

Molecule scenarios live under `extensions/molecule/` (collection-testing
layout).  The `default` scenario owns the shared container lifecycle
(`shared_state: true`); the component scenarios (`tproxy`, `flow_offload`,
`proxy_guard`) reuse the same containers and each run prepare, converge,
idempotence, verify, the role's teardown (cleanup) and a teardown
verification.

The managed nodes are the systemd-enabled container images from
[ak1ra-lab/docker-systemd](https://github.com/ak1ra-lab/docker-systemd)
that these roles support: `debian:12`, `debian:13`, `ubuntu:24.04`,
`ubuntu:26.04`.

```shell
# First run only: the scenarios search the project-local collections path
# (ANSIBLE_COLLECTIONS_PATH in extensions/molecule/config.yml), and the
# default scenario creates the shared containers before Molecule installs
# anything itself.
just ansible-collection-install
ansible-galaxy collection install -r requirements.yml -p .ansible/collections

just molecule-test                  # every scenario (recursive glob)
just molecule-test-one tproxy       # one scenario
just molecule-list
```

Podman is required.  Run it rootful (as the CI does): the `tproxy`
containers load host kernel modules (`modprobe nft_tproxy`, `tcp_bbr`, ...),
which rootless Podman cannot do inside a user namespace; every container is
also created privileged (systemd needs the capabilities, and the shared
udev preparation needs a writable `/sys`).  The host kernel module tree is
bind-mounted read-only into the containers through the inventory's
`container_volumes`.  When iterating with `molecule create` plus `molecule
converge -s <scenario>`, pass `molecule prepare --force -s <scenario>` first
if the shared "prepared" state is already set.

A rootful Docker daemon is supported as an alternative to Podman: set
`MOLECULE_CONTAINER_RUNTIME=docker` for every molecule invocation.  The
containers are then managed through `community.docker` (installed by the
root `requirements.yml`; the `docker` Python SDK must be available to
Ansible) and run privileged, like the Podman path.

The `tproxy` scenario switches off the role's host-only facets, which the
shared containers cannot carry: the static `/etc/resolv.conf` (a
bind-mounted file, so the atomic replace of the template module fails) and
the `tcp_bbr` / `nf_conntrack` sysctl tuning (host-global or not writable
from a container network namespace, which would make the idempotence check
fail).

## Install

```shell
ansible-galaxy collection install git+https://github.com/ak1ra-lab/ansible-collection-network.git
```
