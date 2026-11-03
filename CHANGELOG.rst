===========================================
ak1ra\_lab.network Collection Release Notes
===========================================

.. contents:: Topics

v0.4.0
======

Release Summary
---------------

First Galaxy release of the reorganized network collection. The collection
now depends on ``ak1ra_lab.general >= 0.4.0`` and no longer contains the
``random_*`` lookups. ``flow_offload`` and ``proxy_guard`` remain part of the
active collection, including their Molecule scenarios and documentation.
``tproxy`` remains experimental.

The hand-maintained history for 0.1.0 through 0.3.0 is preserved in
``CHANGELOG-LEGACY.md``; the generated changelog starts with this release.

Minor Changes
-------------

- A local-only ``just collections-install-local`` overlay installs the unpublished sibling ``ak1ra_lab.general`` checkout for lint, mypy, docs and Molecule. tox-ansible and CI continue to resolve the published general from Galaxy.
- Added a protected release workflow that builds, imports and publishes the collection from the ``vX.Y.Z`` GitHub release tag matching ``galaxy.yml``.
- Added the tox-ansible matrix for ansible-core 2.19/2.20/2.21 and the weekly devel/milestone environments, plus mypy alongside ruff and ansible-lint.
- CI and the release workflow now run ``galaxy-importer`` against the tarball produced by the build step instead of rebuilding the collection, so the artifact that is tested is the artifact that is published.
- CI installs ansible-lint, antsibull-changelog and Molecule from the uv dependency groups and runs every Python tool through ``uv run``, matching the local just recipes. The Docs workflow grants Pages write access only to the deploy job.
- Flattened the Molecule scenarios, limited each role to its supported Debian/Ubuntu images, and gave each scenario its own containers instead of a shared lifecycle or ``MOLECULE_GLOB``.
- Migrated release notes to antsibull-changelog. ``CHANGELOG.rst`` is now the canonical changelog, generated from ``changelogs/fragments/``; the pre-Galaxy 0.1.0-0.3.0 history is kept in ``CHANGELOG-LEGACY.md``.
- Migrated the documentation site to Sphinx and antsibull-docs. Role reference pages are generated from ``meta/argument_specs.yml`` and filter reference pages from the plugin documentation, replacing MkDocs.
- Moved the shared test-only collection requirements from ``tests/molecule/requirements.yml`` to ``tests/requirements.yml`` so ansible-lint and every tox-ansible test environment use the same file.
- Prepared the collection for Galaxy with GPL-3.0-or-later licensing, an ansible-core 2.19.0 minimum, the ``ak1ra_lab.general >= 0.4.0``, ``ansible.posix``, ``community.general`` and ``ansible.utils`` dependencies, ``build_ignore`` instead of ``manifest``, controller-side ``requirements.txt`` (``netaddr``) and ``meta/execution-environment.yml``.
- Removed the hard-coded collection version, license and dependency assertions from CI. The release workflow already checks the release tag against ``galaxy.yml``, and ``galaxy-importer`` validates the metadata.
- The ``just ansible-collection-install`` recipe now also installs the shared test-only collections, and the lint and Molecule recipes keep Ansible data under the repository's ``.ansible/`` directory.
- The ``tproxy`` role is marked **experimental**. The role name is unchanged, but its variable contract and deployed artifacts may still change without a deprecation cycle until the role is promoted.
- The build step now asserts that exactly one collection artifact exists and exposes its path to the importer, smoke test and publish steps.
- The new ``netplan_static_default_interface`` option selects the physical interface that carries the static default route. The new ``netplan_static_default_routes`` filter reads the kernel main table (``/proc/net/route``), and ``netplan_static_gateway`` defaults to ``auto`` so the gateway is captured from that interface.
- The operational playbooks moved to the separate ``ansible-playbooks-services`` repository; the collection is now the network role and plugin library only. The mihomo certbot composition (``mihomo_server_certbot.yaml``) lives in that repository, not in the collection.

Breaking Changes / Porting Guide
--------------------------------

- The ``random_password``, ``random_base64_key`` and ``random_uuid`` lookup plugins moved to ``ak1ra_lab.general`` 0.4.0. Use the ``ak1ra_lab.general.random_*`` FQCNs; the network-namespaced plugins are removed in this release.

Bugfixes
--------

- CI action pins were refreshed to ``actions/setup-python`` 7.1.0, ``astral-sh/setup-uv`` 10.3.1 and ``actions/upload-pages-artifact`` 5.0.0.
- Excluded ``AGENTS.md`` and the generated ``dist`` directory from the Galaxy artifact.
- Molecule filters the container's loopback resolver stub and reads the systemd-resolved uplink view before configuring the test resolver, so the resolver scenarios no longer break package downloads in later scenarios. The ``tproxy`` prepare also retries a transient package-download failure.
- Removed the unused ``distlib`` development dependency. It is only required by the legacy ``manifest`` key in ``galaxy.yml``, which this collection does not use.
- The Molecule job authenticates its GitHub release lookups with the workflow ``GITHUB_TOKEN``, so the ``mihomo_install`` and ``mihomo_client`` scenarios no longer fail when the shared runner IP reaches the unauthenticated ``api.github.com`` rate limit.
- The ``flow_offload`` role now asserts a non-empty interface list before rendering the flowtable when the master switch is on, instead of writing a drop-in with an empty ``devices`` set.
- The ``flow_offload`` role resolves an empty ``flow_offload_interfaces`` default when facts are not gathered, so the ``absent`` state (and the Molecule cleanup play) works on hosts that disable fact gathering.
- The ``mihomo_client`` Molecule verify play checks the controller-local profile mirrors only for the scenario's own images, so it no longer expects a mirror for an image the limited converge never touched.
- The ``netplan_static`` role no longer fails when a TUN client such as ``mihomo_client`` owns ``ansible_facts.default_ipv4`` through policy routing. The TUN (``mihomo0``) is never rendered; the role selects the captured ethernet interface and gateway from the kernel main table instead.
- The ``netplan_static`` role treats an empty ``ansible_facts.default_ipv6`` mapping as "no IPv6 default route" instead of failing the IPv6-loss gate on hosts with IPv6 disabled.
