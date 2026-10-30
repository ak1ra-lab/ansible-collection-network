.. _ansible_collections.ak1ra_lab.network.docsite.playbooks:

Playbooks
=========

This collection ships roles and filter plugins only; it does not bundle
operational playbooks.

Playbooks that compose these roles live in the separate
`ansible-playbooks-services <https://github.com/ak1ra-lab/ansible-playbooks-services>`_
repository. Use that repository for deployment entry points, inventories, and
playbook-level variables. The role variable contracts stay in this
collection's ``meta/argument_specs.yml`` files and are rendered in the
generated role reference; role READMEs keep purpose, deployed artifacts,
examples, and operational notes.

The collection remains independent of certificate issuance. Compositions that
combine these roles with certificate automation, such as
``mihomo_server_certbot.yml``, also live in ``ansible-playbooks-services``.
