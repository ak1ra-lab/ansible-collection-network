# Contributing

## Setup

Prerequisites: `uv`, a rootful Podman daemon (or a rootful Docker daemon),
and a sibling checkout of `ak1ra_lab.general` at
`../ansible-collection-general`. The collection is not published to Galaxy
yet, and the development recipes test against that checkout so unpushed
changes can be used. Override the path with `GENERAL_COLLECTION` when working
from a git worktree.

```shell
just sync
just ansible-collection-install
just ansible-requirements-install
```

`just sync` installs the `dev` dependency group (ruff, ty, ansible-core,
pytest, MkDocs). `just ansible-collection-install` installs this collection
and the local `ak1ra_lab.general` checkout into `.ansible/collections`;
`just ansible-requirements-install` installs the collections listed in
`requirements.yaml`.

## Checks

```shell
just lint          # ruff check --fix + ruff format over plugins/ and tests/
just typecheck     # ty check over plugins/ and tests/
just unit-test     # uv run pytest tests/unit -q
just ansible-lint  # ansible-lint (profile: production)
```

`just all` runs lint, typecheck, unit tests, ansible-lint, and the docs build.
Molecule is separate because it needs a container runtime.

## Testing with Molecule

Molecule scenarios live under `extensions/molecule/` (collection-testing
layout). The `default` scenario owns the shared container lifecycle
(`shared_state: true`); the component scenarios (`flow_offload`,
`proxy_guard`, `systemd_bridge`, `systemd_netns`, `tproxy`, `cloud_init`,
`netplan_static`, `systemd_resolved`, `mihomo_client`, `mihomo_server`,
`mihomo_server_certbot`) reuse the same containers and each run prepare,
converge, idempotence, verify, the role's teardown (cleanup), and a teardown
verification. `mihomo_server_certbot` runs on the Debian images
only (Pebble comes from the Debian archive); it issues from a local Pebble
ACME server and verifies the certbot -> role copy -> renewal hook flow.

```shell
just molecule-test                   # every scenario (recursive glob)
just molecule-test-one systemd_netns # one scenario
just molecule-list
```

The managed nodes are the systemd-enabled container images from
[ak1ra-lab/docker-systemd](https://github.com/ak1ra-lab/docker-systemd) that
these roles support: `debian:12`, `debian:13`, `ubuntu:24.04`, and
`ubuntu:26.04`. The systemd roles require `systemd-networkd`, which is not
available on the RHEL family; Fedora would additionally need the separate
`systemd-networkd` package and the `iproute` package name.

The Molecule recipes install the collection under test, the scenario
requirements (`requirements.yaml`), and the local `ak1ra_lab.general`
checkout into `.ansible/collections` before every run. The scenarios search
that project-local path (`ANSIBLE_COLLECTIONS_PATH` in
`extensions/molecule/config.yml`), and the shared `default` scenario creates
the containers before Molecule installs anything itself.

### Container runtime

Run Podman rootful, as CI does. The `systemd_netns` unit uses `ip netns
exec`, whose recursive `/sys` bind mount is not permitted inside the rootless
user namespace, and the `tproxy` scenario loads host kernel modules
(`modprobe nft_tproxy`, `tcp_bbr`, ...), which rootless Podman cannot do
inside a user namespace either. Every container is also created privileged
(systemd needs the capabilities, and the shared udev preparation needs a
writable `/sys`), and the host kernel module tree is bind-mounted read-only
into the containers through the inventory's `container_volumes`.

A rootful Docker daemon is supported as an alternative: set
`MOLECULE_CONTAINER_RUNTIME=docker` for every molecule invocation. The
containers are then managed through `community.docker` (installed from the
root `requirements.yaml`; the `docker` Python SDK must be available to
Ansible) and run privileged, like the Podman path.

When iterating with `molecule create` plus `molecule converge -s <scenario>`,
pass `molecule prepare --force -s <scenario>` first if the shared "prepared"
state is already set.

### Scenario caveats

The `tproxy` scenario switches off the role's host-only facets, which the
shared containers cannot carry: the static `/etc/resolv.conf` (a bind-mounted
file, so the atomic replace of the template module fails) and the `tcp_bbr` /
`nf_conntrack` sysctl tuning (host-global or not writable from a container
network namespace, which would make the idempotence check fail).

The `mihomo_client` scenario switches off
`mihomo_client_dns_manage_resolv_conf` for the same bind-mount reason; it
still exercises the systemd-resolved handover (the `prepare` installs and
starts the service, the role stops/disables it, teardown restores it).

The `netplan_static` scenario sets `netplan_static_apply: false`, validates
the rendered file with `netplan generate`, and keeps a complementary
`10-mtu.yaml` file to exercise the merge-aware conflict policy. Applying a
real network change and the reboot/handback behaviour are VM-level checks,
not container checks. The `systemd_resolved` scenario manages a temporary
resolver path because the container's `/etc/resolv.conf` is a bind mount.

The `flow_offload` and `proxy_guard` scenarios deploy the minimal base
nftables config (the include glob) that a real host gets from
`ak1ra_lab.network.tproxy`, so their tables can be asserted live.

## Documentation

The docs site is built with MkDocs Material. Configuration lives in
`mkdocs.yaml`; hand-written guides live in `docs/`. Role pages are Markdown
snippets that include the canonical `roles/<role>/README.md`; do not copy role
READMEs into `docs/`. Plugin pages are generated from the plugin's
`DOCUMENTATION`, `EXAMPLES`, and `RETURN` constants by
`mkdocs-ansible-collection`, so the collection must be installed in
`.ansible/collections` before building.

```shell
just docs-serve   # http://127.0.0.1:8000
just docs-build   # writes site/
```

The docs workflow publishes `site/` to GitHub Pages from `master`.

## Repository layout

- `roles/` - role implementations and their canonical READMEs.
- `playbooks/` - collection playbook entry points; they orchestrate roles but
  keep role contracts in the roles.
- `plugins/filter/`, `plugins/lookup/` - Python plugins and their docs.
- `extensions/molecule/` - Molecule scenarios.
- `tests/unit/` - pytest tests for plugins and the client profile template.
- `docs/`, `mkdocs.yaml` - documentation site source and configuration.
- `justfile` - the canonical task runner; use its recipes instead of
  reproducing the underlying commands.

## Releases

Releases are tagged `vX.Y.Z`. The collection version lives in `galaxy.yml`,
and notable changes are tracked in `CHANGELOG.md` under `[Unreleased]`.
