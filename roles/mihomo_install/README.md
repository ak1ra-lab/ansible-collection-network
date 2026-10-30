# ak1ra_lab.network.mihomo_install

> The canonical variable reference is generated from
> [`meta/argument_specs.yml`](meta/argument_specs.yml) in the
> [collection documentation](https://ak1ra-lab.github.io/ansible-collection-network/collection_index.html).
> This README keeps purpose, requirements, version policy,
> examples, and operational notes.

Installs the static [mihomo](https://github.com/MetaCubeX/mihomo) binary from
the `MetaCubeX/mihomo` GitHub releases:

- the official `mihomo-linux-<arch>[-<level>]-<version>.gz` archive is
  resolved with
  [`ak1ra_lab.general.github_releases_info`](https://github.com/ak1ra-lab/ansible-collection-general)
  (platform asset selection, GitHub asset digest passed to `get_url` as the
  download checksum), decompressed on the target and installed as
  `/usr/local/bin/mihomo`.  On `amd64` the microarchitecture build (`-v1-` /
  `-v2-` / `-v3-` variants next to the portable baseline) is picked from the
  level detected by
  [`ak1ra_lab.general.cpu_info`](https://github.com/ak1ra-lab/ansible-collection-general).

The archive payload is a **statically linked** ELF, so the role is
distribution-neutral on systemd-based Linux hosts: no `apt`/`dnf`, no package
manager bookkeeping, no `/etc` conffiles.  RPM-based families report the same
`mihomo-linux-<arch>...` asset names and are handled identically.

The role deliberately does **not** manage the service identity, the
configuration, the systemd unit or service restarts: the service roles
(`ak1ra_lab.network.mihomo_client` / `mihomo_server`) own the `mihomo` user
and their own unit.  Consumer playbooks pass
`mihomo_install_restart_handler: systemctl restart mihomo.service` to have the
service role's handler notified after an install/upgrade.

## Requirements

- A systemd-based Linux host with `gzip` and a writable `/usr/local/bin`
  (facts gathered: the release lookup uses the target architecture).
- `ak1ra_lab.general` (>= 0.4.0) installed on the control node for
  `github_releases_info` and `cpu_info`; Galaxy resolves it from the
  collection dependencies.
- The release metadata query goes directly to `api.github.com` and
  authenticates with the controller's `GITHUB_TOKEN` environment variable
  when present (rate limits); there is no variable - export `GITHUB_TOKEN`
  for the playbook run.  The asset download uses the release URL unchanged;
  when GitHub is unreachable, point `mihomo_install_package_src` at a local
  `.gz` file or a mirror URL instead.

## Version policy

The generated role reference lists every option; the tables below describe the
version and microarchitecture policies that need more than a one-line option
description.

| `mihomo_install_version` | Behavior |
| --- | --- |
| `present` (default) | install the latest release when the binary is missing; repeated runs do nothing (no network access) |
| `latest` | converge to the latest release (upgrade or downgrade) |
| `1.19.32` / `v1.19.32` | converge to that release; re-pinned versions download a new archive and reinstall |

`mihomo_install_package_src` overrides the release lookup with an explicit
`.gz` archive: a controller-local file path (copied to the target) or an
`http(s)`/`ftp` URL (fetched with `get_url`); the value shape picks the
transport.  The policy then degrades to "install when the binary is
missing" (the version cannot be compared) - the escape hatch when the
GitHub download is unreachable.

## Microarchitecture builds (amd64)

mihomo publishes `mihomo-linux-amd64-v1-...`, `-v2-...` and `-v3-...` archive
variants next to the portable baseline.  With the default
`mihomo_install_microarch: auto`, the role runs
`ak1ra_lab.general.cpu_info` on the target and asks the release lookup for
the detected x86-64 psABI level; the release does not provide every level
(`v4` is not published), in which case the baseline build is used.  The
detection is skipped on architectures without a level table
(`arm64`, `armv7`, ...) and when `mihomo_install_package_src` is set.

Because the installed version probe cannot tell which variant is running,
switching `mihomo_install_microarch` on an already-installed host requires
one forced reinstall:

```shell
ansible-playbook ... -e mihomo_install_force=true
```

| `mihomo_install_microarch` | Behavior |
| --- | --- |
| `auto` (default) | detect with `cpu_info`; fall back to the baseline |
| `none` / `baseline` / empty | always the portable baseline build |
| `v1`..`v4` / `x86-64-vN` | force that level (amd64 only; requires a forced reinstall to take effect on an existing installation) |

Architectures whose archives carry an extra flavour token (`loong64`
`abi1`/`abi2`, `mips` `hardfloat`/`softfloat`) are not auto-selected; pass
`mihomo_install_package_src` for those.

## Example playbook

The consumer playbooks in `ansible-playbooks-services` apply this role before
the `mihomo_client` and `mihomo_server` service roles:
`https://github.com/ak1ra-lab/ansible-playbooks-services`.

Standalone (binary only, no service):

```yaml
- name: mihomo host
  hosts: gateway
  become: true
  gather_facts: true
  handlers:
    - name: systemctl restart mihomo.service
      ansible.builtin.systemd_service:
        name: mihomo.service
        state: restarted
  tasks:
    - name: install mihomo
      ansible.builtin.include_role:
        name: ak1ra_lab.network.mihomo_install
      vars:
        mihomo_install_version: latest
        # Offline/mirror override: a controller-local .gz or a URL, e.g.
        # mihomo_install_package_src: /var/tmp/mihomo-linux-amd64-v3-v1.19.32.gz
        mihomo_install_restart_handler: systemctl restart mihomo.service
```

## Companion roles

- `ak1ra_lab.network.mihomo_client` and
  `ak1ra_lab.network.mihomo_server` consume the binary; the consumer
  compositions in `ansible-playbooks-services` apply this role first. The
  service roles never install it themselves.
