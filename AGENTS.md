# AGENTS.md

This repository is the `ak1ra_lab.network` Ansible collection (`galaxy.yml`
namespace/name), not a consumer. It ships reusable roles under `roles/`,
custom filter plugins under `plugins/`, and collection playbook entry points
under `playbooks/`. Role contracts belong in
`roles/<role>/meta/argument_specs.yml`; role READMEs keep narrative and
deployed-artifact details. Plugin docs belong in the `DOCUMENTATION`,
`EXAMPLES`, and `RETURN` constants in the plugin source. `README.md` is the
consumer landing page; `docs/docsite/` is the Sphinx site source and must not
duplicate role or plugin docs.

## Tooling

- Environment: **uv** (`pyproject.toml`, `uv.lock`). `just sync` installs the
  `dev` group (lint, test, docs, molecule). Do not use `pip` or `poetry` to
  manage this repository's environment.
- Python lint/format: **ruff** over `plugins/` and `tests/` (`just lint`).
  Typecheck: **mypy** over the same paths (`just typecheck`; pragmatic config
  in `pyproject.toml`). Do not use `black`, `isort`, or `flake8`;
  `ansible-test sanity` remains the authoritative gate.
- Ansible lint: `just ansible-lint` (`profile: production`).
- Unit tests: **tox-ansible** (`just tox-list`, `just unit-test` =
  `unit-py3.13-2.21`). The tests import plugins through the
  `ansible_collections.ak1ra_lab.network...` namespace, so run them through
  `ansible-test units`, not plain pytest without an installed collection.
- Molecule: `just molecule-test`, `just molecule-test-one <scenario>`,
  `just molecule-syntax`, or `just molecule-list`; scenarios live flat under
  `extensions/molecule/` and each one owns its containers. Rootless Podman
  covers most scenarios; `flow_offload`, `systemd_netns` and `tproxy` need
  rootful Podman (or rootful Docker with `MOLECULE_CONTAINER_RUNTIME=docker`).
- Docs: `just docs-lint`, `just docs-build`, and `just docs-serve`
  (antsibull-docs plus Sphinx, config `docs/docsite/conf.py`). The recipes
  install the collection first because antsibull-docs reads it through
  `ansible-doc`.
- Changelog: `just changelog-lint`, `just changelog-release X.Y.Z`, and
  `just changelog-generate`. `CHANGELOG.rst` is generated from
  `changelogs/fragments/` and must not be edited by hand.
- Local gate: `just all` runs lint, typecheck, unit tests, ansible-lint,
  changelog lint, and the docs build. Molecule is separate because it needs a
  container runtime.

## Ansible layout

`ansible.cfg` pins `roles_path=./roles` and
`collections_path=./.ansible/collections`; user-level paths are not used.
Playbooks and templates reference FQCNs, so install the collection into
itself before running playbooks or ansible-lint:

```shell
just ansible-collection-install
```

The recipe installs the collection and its Galaxy dependencies, including
`ak1ra_lab.general`, which the `mihomo_*` roles require. Test-only collections
live in `tests/molecule/requirements.yml`, not the collection's runtime
dependencies; those belong in `galaxy.yml` and `requirements.yml` (consumed by
`meta/execution-environment.yml`).

Role variables use the `<role>_*` prefix. Do not add a `kinds:` mapping to
`.ansible-lint`: remapping role defaults silently disables
`var-naming[no-role-prefix]`.

## Change rules

- Python changes MUST pass `just lint` and `just typecheck`.
- Ansible changes MUST pass `just ansible-lint` and the relevant Molecule
  scenario; report the scenario you ran.
- Do not edit generated artifacts or installed copies: `.ansible/`, `config/`,
  `playbooks/host_vars/`, `playbooks/group_vars/`, and `site/` are ignored
  generated data.
- When adding a role, plugin, or playbook, update the relevant role README,
  the docs index, and add a `changelogs/fragments/*.yml` entry in the same
  change.
- Role documentation: edit `roles/<role>/meta/argument_specs.yml` and the role
  README; do not copy either into `docs/`. The generated role pages come from
  the argument specs.
- Plugin documentation: edit the `DOCUMENTATION`/`EXAMPLES`/`RETURN` blocks
  in `plugins/<type>/<name>.py`; the docs site generates the pages from them.

## Releases

Release order: `ak1ra_lab.general 0.4.0`, then `ak1ra_lab.network 0.4.0`.
The Git tag is `vX.Y.Z` and must match `galaxy.yml`.

Before tagging: run `just all`, the supported sanity/unit environments, the
release-scope Molecule scenarios, and `just docs-build`; build the artifact and
run `galaxy-importer`; confirm `meta/runtime.yml` is in the tarball. The
`Release` workflow publishes only from a published GitHub release in the
protected `release` environment, using `ANSIBLE_GALAXY_API_KEY`; it does not
create tags or releases. Never publish to Galaxy from a local shell.

## References

- `CONTRIBUTING.md` for the full development and Molecule workflow.
- `docs/docsite/` for user guides, the generated role index, and the generated plugin reference.
- `CHANGELOG.rst` (generated), `CHANGELOG-LEGACY.md` (pre-Galaxy history), and
  `galaxy.yml` for release state.
