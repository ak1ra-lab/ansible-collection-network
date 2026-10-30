# Contributing

## Setup

Prerequisites: `uv` and a Podman daemon (rootless covers most scenarios; CI
uses rootful).

```shell
just sync
just ansible-collection-install
```

`just sync` installs the `dev` dependency group (ruff, mypy, ansible-core,
ansible-lint, tox-ansible, pytest, Molecule, antsibull-docs, Sphinx).
`just ansible-collection-install` installs this collection and its Galaxy
dependencies, including `ak1ra_lab.general`, into `.ansible/collections` for
lint, mypy, and docs. Test-only collections come from
`tests/molecule/requirements.yml` and are installed by Molecule/ade.

## Checks

```shell
just lint          # ruff check --fix + ruff format over plugins/ and tests/
just typecheck     # mypy over plugins/ and tests/
just unit-test     # ansible-test units in the tox-ansible unit-py3.13-2.21 env
just tox-list      # show the tox-ansible ansible-core/Python matrix
just ansible-lint  # ansible-lint (profile: production)
just changelog-lint # antsibull-changelog fragment lint
```

`just all` runs lint, typecheck, unit tests, ansible-lint, changelog lint,
docs lint, and the docs build. Molecule is separate because it needs a
container runtime.

Tox-ansible defines the ansible-core 2.19/2.20/2.21 plus weekly
devel/milestone matrix in `[tool.tox]`/`[tool.tox-ansible]`; run one entry with
`just tox sanity-py3.13-2.21`. Test-only collections come from
`tests/molecule/requirements.yml` and are installed by `ade`; do not
pre-install them into `.ansible/collections` for test runs.

## Testing with Molecule

Molecule scenarios live flat under `extensions/molecule/<name>/`. Each
scenario owns its containers: the shared `create.yml`/`destroy.yml` playbooks
build names from the scenario name and a checkout hash, so scenarios and
parallel checkouts cannot collide. There is no shared `default` lifecycle
scenario and no `shared_state`.

The inventory declares every supported image and one group per scenario with
only the images that role supports; `--limit=<scenario>,localhost` keeps the
plays and the create/destroy loops on that subset. No role runs on every image.

| Scenario | Images | Notes |
| --- | --- | --- |
| `cloud_init` | Debian 12/13 | |
| `netplan_static` | Debian 12/13 | render-only (`netplan_static_apply: false`) |
| `systemd_bridge` | Debian 12, Ubuntu 24.04 | |
| `systemd_netns` | Debian 12, Ubuntu 24.04 | rootful Podman only |
| `systemd_resolved` | Debian 12, Ubuntu 24.04 | manages a temporary resolver path |
| `tproxy` | Debian 12/13 | rootful Podman only (modprobe) |
| `flow_offload` | Debian 12/13 | rootful Podman only (host flowtable) |
| `proxy_guard` | Debian 12/13 | |
| `mihomo_client` | Debian 12/13 | |
| `mihomo_server` | Debian 12/13 | |
| `mihomo_server_jls` | Debian 12/13 | |

Ubuntu 26.04 is not in the matrix: the role metadata declares Ubuntu
22.04/24.04 and Debian 12/13.

```shell
just molecule-test                   # every scenario
just molecule-test-one systemd_bridge
just molecule-syntax
just molecule-list
```

Molecule's dependency action installs `tests/molecule/requirements.yml`;
ansible-compat's prerun installs the collection under test and its `galaxy.yml`
dependencies, including `ak1ra_lab.general`, from Galaxy. Do not pre-install
the collection or test collections into `.ansible/collections` for Molecule.

### Container runtime

Rootless Podman works for `cloud_init`, `mihomo_client`, `mihomo_server`,
`mihomo_server_jls`, `netplan_static`, `proxy_guard`, `systemd_bridge`, and
`systemd_resolved`. The `flow_offload`, `systemd_netns` and `tproxy` scenarios
need rootful Podman: `flow_offload` touches the host flowtable offload path,
`ip netns exec`'s recursive `/sys` bind mount is not permitted inside a
rootless user namespace, and `tproxy` loads host kernel modules. CI uses
rootful Podman for the whole suite.

Every container is created privileged (systemd needs the capabilities, and
the shared udev preparation needs a writable `/sys`), and the host kernel
module tree is bind-mounted read-only into the containers through the
inventory's `container_volumes`.

A Docker daemon is supported as an alternative: set
`MOLECULE_CONTAINER_RUNTIME=docker` for every molecule invocation. The
containers are then managed through `community.docker` (from
`tests/molecule/requirements.yml`; the `docker` Python SDK must be available to
Ansible) and run privileged, like the Podman path.

Molecule caches scenario state, so a changed `molecule.yml` needs
`molecule reset` (or `destroy`).

### Scenario caveats

The `tproxy` scenario switches off the role's host-only facets, which the
containers cannot carry: the static `/etc/resolv.conf` (a bind-mounted file,
so the atomic replace of the template module fails) and the `tcp_bbr` /
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

## Changelog

`CHANGELOG.rst` is the canonical changelog and is generated by
`antsibull-changelog`. Do not edit it by hand.

- Add a YAML fragment under `changelogs/fragments/` for every user-visible
  change. Use the section names from `changelogs/config.yaml`
  (`minor_changes`, `breaking_changes`, `bugfixes`, ...); use
  `release_summary` only for release-level prose.
- Run `just changelog-lint` before committing.
- At release time, run `just changelog-release X.Y.Z`, then
  `just changelog-generate`, and commit `changelogs/changelog.yaml`,
  `CHANGELOG.rst`, and the retained fragments. `keep_fragments` is enabled, so
  the released fragments stay in the tree for audit; antsibull-changelog
  records them and does not reuse them for the next release.
- The pre-Galaxy 0.1.0-0.3.0 history remains in `CHANGELOG-LEGACY.md`; the
  generated changelog starts at 0.4.0.

## Documentation

The docs site is built with Sphinx and antsibull-docs. Configuration lives in
`docs/docsite/conf.py`; hand-written guides live in `docs/docsite/rst/`. Role
pages are generated from `roles/<role>/meta/argument_specs.yml`. Plugin pages
are generated from the plugin's `DOCUMENTATION`, `EXAMPLES`, and `RETURN`
constants, so the collection must be installed in `.ansible/collections`
before building (the just recipes do that).

```shell
just docs-lint    # antsibull-docs lint-collection-docs
just docs-build   # regenerate reference pages + sphinx-build -W
just docs-serve   # http://127.0.0.1:8000
```

The docs workflow publishes `docs/docsite/_build/html` to GitHub Pages from
`master`.

## Repository layout

- `roles/` - role implementations and their canonical READMEs.
- `plugins/filter/` - Python filter plugins and their docs.
- `extensions/molecule/` - Molecule scenarios.
- `tests/unit/` - pytest tests for plugins and the client profile template.
- `docs/docsite/` - Sphinx documentation source and configuration.
- `justfile` - the canonical task runner; use its recipes instead of
  reproducing the underlying commands.

Operational playbooks that compose these roles live in the separate
`ansible-playbooks-services` repository, not in this collection.

## Releases

Release order for the `ak1ra_lab` collections:

1. `ak1ra_lab.general 0.4.0`
2. `ak1ra_lab.network 0.4.0` (requires general `>=0.4.0`)

Per release:

1. Update `version` in `galaxy.yml` and run
   `just changelog-release X.Y.Z` plus `just changelog-generate`.
2. Run the full local gate: `just all`, the supported `ansible-test
   sanity`/unit environments, the release-scope Molecule scenarios, and
   `just docs-build`.
3. Build and inspect the artifact: `just build`, verify `meta/runtime.yml` is
   in the tarball, and run `galaxy-importer`.
4. Commit the release and tag it `vX.Y.Z`. The tag must match `galaxy.yml`.
5. Publish a GitHub release from that tag. The `Release` workflow runs in the
   protected `release` environment, builds the collection, verifies the tag,
   runs `galaxy-importer`, and publishes with `ANSIBLE_GALAXY_API_KEY`.
   Do not publish from a local shell or a non-tag commit.

The Galaxy API key is stored only as an environment secret on the protected
`release` environment. The workflow does not push tags or create releases.
