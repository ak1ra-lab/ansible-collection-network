# Show available recipes
default:
    @just --list --unsorted

# Lint all collection content with ansible-lint (production profile)
lint:
    ansible-lint

# Run every Molecule scenario (nested scenarios need the recursive glob)
molecule-test:
    MOLECULE_GLOB='extensions/molecule/**/molecule.yml' molecule test --all

# Run one Molecule scenario, e.g. `just molecule-test-one tproxy`
molecule-test-one scenario:
    MOLECULE_GLOB='extensions/molecule/**/molecule.yml' molecule test -s {{scenario}}

# List the Molecule scenarios
molecule-list:
    MOLECULE_GLOB='extensions/molecule/**/molecule.yml' molecule list

# Create the shared test containers used by every scenario
molecule-create:
    molecule create

# Remove the shared test containers
molecule-destroy:
    molecule destroy

# Install project-local Ansible collection
ansible-collection-install:
    mkdir -p .ansible/collections
    ansible-galaxy collection install --force --collections-path .ansible/collections .

# Build project-local Ansible collection
ansible-collection-build:
    mkdir -p .ansible/dist/
    ansible-galaxy collection build --force --output-path .ansible/dist/ .

# Remove build artifacts
clean:
    rm -rf .ansible/ .cache/
