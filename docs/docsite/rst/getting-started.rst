.. _ansible_collections.ak1ra_lab.network.docsite.getting-started:

Getting started
===============

Install the collection
----------------------

Install the released collection from Ansible Galaxy:

.. code-block:: shell

   ansible-galaxy collection install ak1ra_lab.network

Or pin it in a consumer ``requirements.yml``:

.. code-block:: yaml

   ---
   collections:
     - name: ak1ra_lab.network
       version: ">=0.4.0"

.. code-block:: shell

   ansible-galaxy collection install -r requirements.yml

Galaxy resolves ``ak1ra_lab.general >= 0.4.0``, ``ansible.posix``,
``community.general``, and ``ansible.utils`` from ``galaxy.yml``
automatically. The ``0.4.0`` release is the first Galaxy release.

For development in this repository, ``just ansible-collection-install``
installs the collection under test and its Galaxy dependencies into
``.ansible/collections`` for lint, mypy, and docs.

Control-node requirements
-------------------------

- ``ansible-core >= 2.19.0`` (``meta/runtime.yml``); tested with 2.19, 2.20,
  and 2.21 plus the weekly ``devel``/``milestone`` builds.
- Controller Python ``>= 3.11``; tested with 3.11, 3.12, and 3.13.
  ansible-core 2.20 and 2.21 additionally support Python 3.12-3.14.
- ``ansible.utils >= 6.0.0`` (a ``galaxy.yml`` dependency) for the ``ipaddr``
  and ``in_network`` filters used by the ``systemd_bridge`` and
  ``systemd_netns`` roles.
- ``netaddr`` for the ``ansible.utils.ipaddr`` filter; the repository ships it
  in ``requirements.txt``:

  .. code-block:: shell

     python -m pip install -r requirements.txt

- ``ak1ra_lab.general >= 0.4.0`` for the ``mihomo_install``,
  ``mihomo_client``, and ``mihomo_server`` roles (``github_releases_info``,
  ``cpu_info``, and the ``random_*`` lookups). Certificate issuance is not
  part of this collection; the consumer supplies the TLS material.

The development environment uses ``uv``; ``just ansible-collection-install``
installs the collection under test and its Galaxy dependencies for
lint/mypy/docs. Molecule installs the collection under test and the test
collections from ``tests/molecule/requirements.yml`` itself.

Managed-node requirements
-------------------------

The roles target systemd-based Linux. The Molecule images used by this
repository are Debian 12 (target Python 3.11), Debian 13 (target Python
3.13), and Ubuntu 24.04 (target Python 3.12). The roles use the managed
node's ``/usr/bin/python3``.

The ``systemd_bridge`` and ``systemd_netns`` roles require
``systemd-networkd``, which is not available on the RHEL family. Fedora would
additionally need the separate ``systemd-networkd`` package and the
``iproute`` package name.

Release order
-------------

``ak1ra_lab.general 0.4.0`` is published first; ``ak1ra_lab.network 0.4.0``
depends on it. See :doc:`changelog` for release notes.

Next steps
----------

- :doc:`architecture` for how the role families fit together.
- :doc:`playbooks` for collection entry points and host defaults.
- :doc:`filters` for the generated filter reference.
- :doc:`collection_index` for the generated role reference.
