#!/usr/bin/env bash
# Copyright (c) Ansible Project
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

set -e

pushd "$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"; popd' EXIT
chmod 700 "$tmp"
antsibull-docs \
    --config-file antsibull-docs.cfg \
    collection \
    --cleanup everything \
    --use-current \
    --squash-hierarchy \
    --dest-dir "$tmp" \
    ak1ra_lab.network

for file in "$tmp"/*.rst; do
    if [ "$(basename "$file")" = index.rst ]; then
        cp "$file" rst/collection_index.rst
    else
        cp "$file" rst/
    fi
done

if ! head -n 1 rst/collection_index.rst | grep -q '^:orphan:'; then
    printf ':orphan:\n\n' | cat - rst/collection_index.rst > rst/.collection_index.tmp
    mv rst/.collection_index.tmp rst/collection_index.rst
fi

# The hand-written guide pages are already linked from rst/index.rst. Drop the
# docsite-prefixed copy of that toctree from the generated collection index;
# its paths assume the docs.ansible.com source root, not this docsite.
awk '
    /^User guide$/ { skip = 1 }
    /^\.\. _plugin_index_for_/ { skip = 0 }
    !skip { print }
' rst/collection_index.rst > rst/.collection_index.tmp
mv rst/.collection_index.tmp rst/collection_index.rst

sphinx-build -W -b html -c . rst _build/html
