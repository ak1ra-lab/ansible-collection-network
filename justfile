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

# Install project-local Ansible collection
# (the collection under test plus the ak1ra_lab.general local checkout)
ansible-collection-install:
    mkdir -p .ansible/collections
    uv run ansible-galaxy collection install --force --collections-path .ansible/collections .
    uv run ansible-galaxy collection install --force --collections-path .ansible/collections "{{GENERAL_COLLECTION}}"

# Install the collections required by the Molecule scenarios
ansible-requirements-install:
    mkdir -p .ansible/collections
    uv run ansible-galaxy collection install -r requirements.yaml -p .ansible/collections

# Lint all Ansible content with ansible-lint (production profile)
ansible-lint:
    uv run ansible-lint

# Run every Molecule scenario
molecule-test: ansible-collection-install ansible-requirements-install
    uv run molecule test --all

# Run one Molecule scenario, e.g. `just molecule-test-one systemd_netns`
molecule-test-one scenario: ansible-collection-install ansible-requirements-install
    uv run molecule test -s {{scenario}}

# List the Molecule scenarios
molecule-list:
    uv run molecule list

# Serve the documentation site locally
docs-serve: ansible-collection-install
    ANSIBLE_COLLECTIONS_PATH="$PWD/.ansible/collections" NO_MKDOCS_2_WARNING=1 uv run mkdocs serve

# Build the documentation site into site/
docs-build: ansible-collection-install
    ANSIBLE_COLLECTIONS_PATH="$PWD/.ansible/collections" NO_MKDOCS_2_WARNING=1 uv run mkdocs build --strict

# Create the shared test containers used by every scenario
molecule-create: ansible-collection-install ansible-requirements-install
    uv run molecule create

# Remove the shared test containers
molecule-destroy:
    uv run molecule destroy

# Remove build artifacts
clean:
    rm -rf .ansible/ .molecule/ .cache/ .pytest_cache/ .ruff_cache/ site/
    find plugins/ -type f -name "*.pyc" -delete
    find plugins/ -type d -name "__pycache__" -delete
