# AGENTS.md

## Project type

This repository is the `ak1ra_lab.network` Ansible collection: a library of
reusable networking roles and filter plugins, not a consumer or a playbook
project. Operational playbooks and inventories live in the separate
`ansible-playbooks-services` repository; this collection ships no runnable
playbooks.

## Skills

Actively use the `developing-ansible` skill for Ansible work; load it before
writing or reviewing playbooks, roles, plugins, inventory, Molecule, or
collection metadata.

Prefer a user-level installation of the skill. Agents that do not have it
installed may bootstrap from
`https://raw.githubusercontent.com/ak1ra-komj/agents-skills/refs/heads/master/skills/developing-ansible/SKILL.md`;
the URL is a fallback, not the normal workflow.

## Layout

- Roles under `roles/` include `mihomo_install`, `mihomo_client`,
  `mihomo_server`, `systemd_bridge`, `systemd_netns`, `systemd_resolved`,
  `netplan_static`, `cloud_init`, `tproxy`, `flow_offload`, and `proxy_guard`.
- Custom filters live under `plugins/filter/`; unit tests live in `tests/unit/`.
  Molecule scenarios are flat under `extensions/molecule/`.
- `network` does not depend on `ak1ra_lab.certificate`; TLS material is an
  input, and certificate issuance belongs to the playbook project.
- Role variables use the `<role>_*` prefix. Do not add a `kinds:` mapping to
  `.ansible-lint`, because remapping role defaults disables
  `var-naming[no-role-prefix]`.

## YAML and documentation

Use `.yml` for Ansible and repository YAML files. Unavoidable exceptions:

- `galaxy.yml` already uses `.yml`.
- `changelogs/config.yaml` is hardcoded by antsibull-changelog.
- `.pre-commit-config.yaml` stays `.yaml` because pre-commit 4.7 discovers only
  that name.
- Generated or upstream filenames such as `*.proxies.yaml`, `host_vars/*.yaml`,
  `50-cloud-init.yaml`, netplan files, and downloaded manifests keep their
  existing names.

`roles/<role>/meta/argument_specs.yml` is the canonical role variable
reference. Generated role docs come from argument specs; role READMEs are
concise narrative (purpose, requirements, artifacts, examples, teardown) and
must not duplicate variable tables. Plugin docs come from the plugin source
`DOCUMENTATION`, `EXAMPLES`, and `RETURN` blocks. Do not copy either into
`docs/` or edit generated pages by hand.

## Tooling and validation

- Use **uv** and **just**; never `pip` or `poetry`. `just sync` installs the
  `dev` group.
- Python: **ruff** and **mypy** via `just lint` and `just typecheck`.
  `ansible-test sanity` remains the authoritative gate.
- Ansible: `just ansible-lint` (production profile) and **tox-ansible**
  (`just tox-list`, `just tox <env>`, `just unit-test`).
- Molecule: `just molecule-test`, `just molecule-test-one <scenario>`, or
  `just molecule-syntax`. Rootless Podman covers most; `flow_offload`,
  `systemd_netns`, and `tproxy` need rootful Podman or Docker.
- Docs and changelog: `just docs-lint`, `just docs-build`, and
  `just changelog-lint`, using antsibull-docs/antsibull-changelog.
  `CHANGELOG.rst` is generated and must not be edited by hand.
- `just all` runs lint, typecheck, unit tests, ansible-lint, changelog lint,
  and docs; Molecule stays separate because it needs a container runtime.

## Workflow and safety

- Install the collection and its Galaxy dependencies with
  `just ansible-collection-install` before lint, mypy, or docs.
- Preserve public behavior unless the task explicitly changes it; keep changes
  consistent with the existing layout and naming.
- Do not add unpublished-dependency workarounds to CI, tests, docs, or release.
- Do not edit installed copies under `.ansible/`, `.tox/`, or `.venv/`.
- Release: `general 0.4.0`, then `network 0.4.0`; tag `vX.Y.Z` matches
  `galaxy.yml`. Build, run `galaxy-importer`, publish via the protected workflow.
