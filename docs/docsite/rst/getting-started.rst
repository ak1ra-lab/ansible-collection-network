.. _ansible_collections.ak1ra_lab.network.docsite.getting-started:

Getting started
===============

Install the collection
----------------------

.. code-block:: shell

   ansible-galaxy collection install git+https://github.com/ak1ra-lab/ansible-collection-network.git

The ``mihomo_*`` roles also need ``ak1ra_lab.general``, which is not published
to Galaxy yet. Add it to the consuming repository's ``requirements.yaml`` and
install from Git:

.. code-block:: yaml

   collections:
     - name: git+https://github.com/ak1ra-lab/ansible-collection-general.git
       version: master

For development in this repository, ``just ansible-collection-install``
installs the collection under test plus the local
``../ansible-collection-general`` checkout into ``.ansible/collections``.
Override the path with ``GENERAL_COLLECTION=/path/to/checkout`` when working
from a git worktree.

Control-node requirements
-------------------------

- ``ansible-core >= 2.19.0`` (``meta/runtime.yml``) and controller Python
  ``>= 3.11``.
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
installs the collection under test and the local general checkout for
lint/mypy/docs. Molecule installs the collection under test and the test
collections from ``tests/molecule/requirements.yml`` itself.

Managed-node requirements
-------------------------

The roles target systemd-based Linux. The Molecule images used by this
repository are:

- ``debian:12``
- ``debian:13``
- ``ubuntu:24.04``

The ``systemd_bridge`` and ``systemd_netns`` roles require
``systemd-networkd``, which is not available on the RHEL family. Fedora would
additionally need the separate ``systemd-networkd`` package and the
``iproute`` package name.

Next steps
----------

- :doc:`architecture` for how the role families fit together.
- :doc:`playbooks` for collection entry points and host defaults.
- :doc:`filters` for the generated filter reference.
- :doc:`collection_index` for the generated role reference.
