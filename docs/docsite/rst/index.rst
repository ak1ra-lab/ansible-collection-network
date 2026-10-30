ak1ra_lab.network
=================

Shared Ansible roles for network infrastructure. The collection covers
transparent-proxy plumbing, systemd-networkd host networking, and cloud-image
network takeover.

.. toctree::
   :maxdepth: 2
   :caption: User guide

   getting-started
   architecture
   playbooks
   filters
   contributing
   changelog

The generated role and plugin reference is available at
:doc:`collection_index`.

Role documentation is generated from each role's
``meta/argument_specs.yml``, which is the canonical variable reference. Role
READMEs are narrative companions: purpose, requirements, deployed artifacts,
examples, and operational notes.

.. note::

   Install the released collection from Ansible Galaxy; see
   :doc:`getting-started`. The generated role pages use the Galaxy FQCN.
   ``tproxy`` is experimental: the role name is stable, but its contract may
   still change until it is promoted.
