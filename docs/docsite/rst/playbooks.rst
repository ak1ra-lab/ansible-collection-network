.. _ansible_collections.ak1ra_lab.network.docsite.playbooks:

Playbooks
=========

The collection ships thin playbook entry points. They set privileges, gather
facts, and orchestrate roles; the variable contracts stay in the role argument
specs.

.. list-table::
   :header-rows: 1
   :widths: 28 72

   * - Playbook
     - Behavior
   * - ``ak1ra_lab.network.systemd_bridge``
     - Wrapper around the ``systemd_bridge`` role (root privileges, fact
       gathering). Drive it through the ``systemd_bridge_*`` contract.
   * - ``ak1ra_lab.network.systemd_netns``
     - Applies the host bridges declared for the run
       (``systemd_bridge_bridges``) first, flushes their handlers, then applies
       the namespace role. The ``systemd_netns_*`` contract drives the
       namespace.
   * - ``ak1ra_lab.network.cloud_init``
     - Wrapper around the ``cloud_init`` role (root privileges, fact
       gathering). The ``cloud_init_*`` contract drives it.
   * - ``ak1ra_lab.network.netplan_static``
     - Wrapper around the ``netplan_static`` role (root privileges, fact
       gathering). The playbook can change the network path, so target an
       explicit inventory group and keep console access.
   * - ``ak1ra_lab.network.systemd_resolved``
     - Wrapper around the ``systemd_resolved`` role (root privileges, fact
       gathering). The ``systemd_resolved_*`` contract drives it.
   * - ``ak1ra_lab.network.mihomo_install``
     - Installs or upgrades the binary only (root privileges, fact
       gathering). The ``mihomo_install_*`` contract drives it.
   * - ``ak1ra_lab.network.mihomo_client``
     - Applies ``mihomo_install`` first, then ``mihomo_client``. A binary
       upgrade restarts ``mihomo.service`` through the client role's handler.
   * - ``ak1ra_lab.network.mihomo_server``
     - Applies ``mihomo_install`` first, then the server role. TLS material is
       supplied externally.

Host selection
--------------

Each playbook targets a group by default and accepts ``playbook_hosts`` as an
override:

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Playbook
     - Default host group
   * - ``systemd_bridge``
     - ``localhost``
   * - ``systemd_netns``
     - ``localhost``
   * - ``cloud_init``
     - ``cloud-image-vms``
   * - ``netplan_static``
     - ``cloud-image-vms``
   * - ``systemd_resolved``
     - ``cloud-image-vms``
   * - ``mihomo_install``
     - ``localhost``
   * - ``mihomo_client``
     - ``mihomo-client``
   * - ``mihomo_server``
     - ``mihomo-server``

Examples
--------

.. code-block:: shell

   ansible-playbook ak1ra_lab.network.systemd_bridge \
     -e systemd_bridge_bridges='[{"name": "br_wan", "interface": "enp36s0"}]'

   ansible-playbook ak1ra_lab.network.systemd_netns \
     -e systemd_netns_name=qbittorrent

   ansible-playbook ak1ra_lab.network.cloud_init \
     -e playbook_hosts=cloud-image-vms

   ansible-playbook ak1ra_lab.network.netplan_static \
     -e playbook_hosts=cloud-image-vms \
     -e netplan_static_gateway=172.16.0.240 \
     -e '{"netplan_static_nameservers": ["172.16.0.240"]}'

   ansible-playbook ak1ra_lab.network.systemd_resolved \
     -e playbook_hosts=cloud-image-vms

   ansible-playbook ak1ra_lab.network.mihomo_client \
     -e mihomo_install_version=latest

   ansible-playbook ak1ra_lab.network.mihomo_server \
     -e mihomo_install_version=latest
