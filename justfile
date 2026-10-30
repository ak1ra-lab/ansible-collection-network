# Path to the ak1ra_lab.general collection checkout.  The collection is not
# on Galaxy yet (install it from git, see README.md), and the dev recipes use
# this sibling checkout to test against unpushed changes; override it from
# worktrees or other layouts:
#   just GENERAL_COLLECTION=/path/to/ansible-collection-general \
#     ansible-collection-install
GENERAL_COLLECTION := env_var_or_default('GENERAL_COLLECTION', '../ansible-collection-general')

# Show available recipes
default:
    @just --list --unsorted

# Run all available recipes
all: lint typecheck unit-test ansible-lint docs-build

# Sync development dependencies (may update uv.lock if pyproject.toml changed)
sync *ARGS:
    uv sync {{ARGS}} --group dev

# Lint and format collection Python (plugins and tests)
lint:
    uv run ruff check --fix plugins/ tests/
    uv run ruff format plugins/ tests/

# Run static type checks with mypy (the collection must be installed first)
typecheck: ansible-collection-install
    uv run mypy plugins/ tests/

# Run the filter plugin and template unit tests through tox-ansible
unit-test:
    uv run tox -e unit-py3.13-2.21 --ansible

# Show the tox-ansible environment matrix
tox-list:
    uv run tox list --ansible

# Run one tox-ansible environment, e.g. `just tox sanity-py3.13-2.21`
tox env='sanity-py3.13-2.21':
    uv run tox -e {{env}} --ansible

# Install project-local Ansible collection for lint, mypy and docs only
# (the collection under test plus the ak1ra_lab.general local checkout).
# Molecule installs the collection under test and its test requirements itself.
ansible-collection-install:
    mkdir -p .ansible/collections
    uv run ansible-galaxy collection install --force --collections-path .ansible/collections .
    uv run ansible-galaxy collection install --force --collections-path .ansible/collections "{{GENERAL_COLLECTION}}"

# Lint all Ansible content with ansible-lint (production profile)
ansible-lint:
    uv run ansible-lint

# Run every Molecule scenario.  Scenarios are flat, each one owns its
# containers, and the inventory limits each role to its supported images.
molecule-test:
    uv run molecule test --all

# Run one Molecule scenario, e.g. `just molecule-test-one systemd_netns`
molecule-test-one scenario:
    uv run molecule test -s {{scenario}}

# Syntax-check every scenario's converge playbook
molecule-syntax:
    uv run molecule syntax --all

# List the Molecule scenarios
molecule-list:
    uv run molecule list

# Serve the documentation site locally
docs-serve: ansible-collection-install
    ANSIBLE_COLLECTIONS_PATH="$PWD/.ansible/collections" NO_MKDOCS_2_WARNING=1 uv run mkdocs serve

# Build the documentation site into site/
docs-build: ansible-collection-install
    ANSIBLE_COLLECTIONS_PATH="$PWD/.ansible/collections" NO_MKDOCS_2_WARNING=1 uv run mkdocs build --strict

# Remove build artifacts
clean:
    rm -rf .ansible/ .molecule/ .cache/ .pytest_cache/ .ruff_cache/ site/
    find plugins/ -type f -name "*.pyc" -delete
    find plugins/ -type d -name "__pycache__" -delete
