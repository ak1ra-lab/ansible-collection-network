# Show available recipes
default:
    @just --list --unsorted

# Run all available recipes
all: lint typecheck unit-test ansible-lint changelog-lint docs-lint docs-build

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

# Install the collection and its Galaxy dependencies into the project-local
# path for lint, mypy and docs only. Molecule installs the collection under
# test and its test requirements itself.
ansible-collection-install:
    mkdir -p .ansible/collections
    uv run ansible-galaxy collection install --force --collections-path .ansible/collections .

# Lint all Ansible content with ansible-lint (production profile)
ansible-lint:
    uv run ansible-lint

# Lint the antsibull-changelog fragments
changelog-lint:
    uv run --group lint antsibull-changelog lint

# Add a release to changelogs/changelog.yml, consuming the fragments
changelog-release version:
    uv run --group lint antsibull-changelog release --version {{version}}

# Regenerate CHANGELOG.rst from changelogs/changelog.yml
changelog-generate:
    uv run --group lint antsibull-changelog generate

# Build the Galaxy artifact into dist/
build:
    uv run --group lint ansible-galaxy collection build --force --output-path dist

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

# Remove generated Sphinx output and antsibull-docs reference pages
docs-clean:
    rm -rf docs/docsite/_build
    rm -f docs/docsite/rst/collection_index.rst docs/docsite/rst/environment_variables.rst
    rm -f docs/docsite/rst/*_role.rst docs/docsite/rst/*_module.rst docs/docsite/rst/*_lookup.rst docs/docsite/rst/*_filter.rst

# Lint collection documentation with antsibull-docs
docs-lint: ansible-collection-install docs-clean
    uv run --group docs antsibull-docs lint-collection-docs --plugin-docs --validate-collection-refs self .

# Regenerate the role/filter reference pages and build the Sphinx site into
# docs/docsite/_build/html
docs-build: ansible-collection-install docs-clean
    ANSIBLE_COLLECTIONS_PATH="$PWD/.ansible/collections" uv run --group docs bash docs/docsite/build.sh

# Serve the last Sphinx build locally on http://127.0.0.1:8000
docs-serve: docs-build
    uv run --group docs python -m http.server 8000 -d docs/docsite/_build/html

# Remove build artifacts
clean:
    rm -rf .ansible/ .molecule/ .cache/ .pytest_cache/ .ruff_cache/ dist/ site/ docs/docsite/_build/
    find plugins/ -type f -name "*.pyc" -delete
    find plugins/ -type d -name "__pycache__" -delete
