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
all: lint typecheck unit-test ansible-lint

# Sync development dependencies (may update uv.lock if pyproject.toml changed)
sync *ARGS:
    uv sync {{ARGS}} --group dev

# Lint and format collection Python (plugins and tests)
lint:
    uv run ruff check --fix plugins/ tests/
    uv run ruff format plugins/ tests/

# Run static type checks with Astral ty
typecheck:
    uv run ty check plugins/ tests/

# Run the plugin unit tests (filters + lookups)
unit-test:
    uv run pytest tests/unit -q

# Install project-local Ansible collection
# (the collection under test plus the ak1ra_lab.general local checkout)
ansible-collection-install:
    mkdir -p .ansible/collections
    ansible-galaxy collection install --force --collections-path .ansible/collections .
    ansible-galaxy collection install --force --collections-path .ansible/collections "{{GENERAL_COLLECTION}}"

# Install the collections required by the Molecule scenarios
ansible-requirements-install:
    mkdir -p .ansible/collections
    ansible-galaxy collection install -r requirements.yaml -p .ansible/collections

# Lint all Ansible content with ansible-lint (production profile)
ansible-lint:
    ansible-lint

# Run every Molecule scenario (nested scenarios need the recursive glob)
molecule-test: ansible-collection-install ansible-requirements-install
    MOLECULE_GLOB='extensions/molecule/**/molecule.yml' molecule test --all

# Run one Molecule scenario, e.g. `just molecule-test-one systemd_netns`
molecule-test-one scenario: ansible-collection-install ansible-requirements-install
    MOLECULE_GLOB='extensions/molecule/**/molecule.yml' molecule test -s {{scenario}}

# List the Molecule scenarios
molecule-list:
    MOLECULE_GLOB='extensions/molecule/**/molecule.yml' molecule list

# Create the shared test containers used by every scenario
molecule-create: ansible-collection-install ansible-requirements-install
    molecule create

# Remove the shared test containers
molecule-destroy:
    molecule destroy

# Remove build artifacts
clean:
    rm -rf .ansible/ .molecule/ .cache/ .pytest_cache/ .ruff_cache/
    find plugins/ -type f -name "*.pyc" -delete
    find plugins/ -type d -name "__pycache__" -delete
