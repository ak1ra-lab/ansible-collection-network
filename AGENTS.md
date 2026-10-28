# AGENTS.md

This repository is the `ak1ra_lab.network` Ansible collection (`galaxy.yml`
namespace/name), not a consumer. It ships reusable roles under `roles/`,
custom filter and lookup plugins under `plugins/`, and collection playbook
entry points under `playbooks/`. Role contracts belong in
`roles/<role>/README.md`; plugin docs belong in the `DOCUMENTATION`,
`EXAMPLES`, and `RETURN` constants in the plugin source. `README.md` is the
consumer landing page; `docs/` is the MkDocs site source and must not
duplicate role or plugin docs.

## Tooling

- Environment: **uv** (`pyproject.toml`, `uv.lock`). `just sync` installs the
  `dev` group (lint, test, docs). Do not use `pip` or `poetry` to manage this
  repository's environment.
- Python lint/format: **ruff** over `plugins/` and `tests/` (`just lint`).
  Typecheck: **ty** over the same paths (`just typecheck`). Do not use
  `black`, `isort`, `flake8`, or `mypy`.
- Ansible lint: `just ansible-lint` (`profile: production`).
- Unit tests: `just unit-test` (`uv run pytest tests/unit -q`).
- Molecule: `just molecule-test`, `just molecule-test-one <scenario>`, or
  `just molecule-list`; scenarios live under `extensions/molecule/`. Run
  Molecule with rootful Podman, or rootful Docker with
  `MOLECULE_CONTAINER_RUNTIME=docker`; rootless Podman cannot run the
  `systemd_netns` and `tproxy` scenarios.
- Docs: `just docs-serve` and `just docs-build` (MkDocs Material, config
  `mkdocs.yaml`). The recipes install the collection first because
  `mkdocs-ansible-collection` reads it through `ansible-doc`.
- Local gate: `just all` runs lint, typecheck, unit tests, ansible-lint, and
  the docs build. Molecule is separate because it needs a container runtime.

## Ansible layout

`ansible.cfg` pins `roles_path=./roles` and
`collections_path=./.ansible/collections`; user-level paths are not used.
Playbooks and templates reference FQCNs, so install the collection into
itself before running playbooks or ansible-lint:

```shell
just ansible-collection-install
```

That recipe also installs the sibling `ak1ra_lab.general` checkout (required
by the `mihomo_*` roles) from `../ansible-collection-general`; override
`GENERAL_COLLECTION=/path/to/checkout` in a worktree. `requirements.yaml`
holds the extra collections used by Molecule and linting, not the collection's
runtime dependencies; those belong in `galaxy.yml`.

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
  the docs nav/index, and `CHANGELOG.md` in the same change.
- Role documentation: edit `roles/<role>/README.md`; do not copy it into
  `docs/`. The role pages include it through Markdown snippets.
- Plugin documentation: edit the `DOCUMENTATION`/`EXAMPLES`/`RETURN` blocks
  in `plugins/<type>/<name>.py`; the docs site generates the pages from them.

## References

- `CONTRIBUTING.md` for the full development and Molecule workflow.
- `docs/` for user guides, the role index, and the generated plugin reference.
- `CHANGELOG.md` and `galaxy.yml` for release state.
