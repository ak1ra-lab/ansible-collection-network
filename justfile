# Show available recipes
default:
    @just --list --unsorted

# Lint all collection content with ansible-lint (production profile)
lint:
    ansible-lint

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
