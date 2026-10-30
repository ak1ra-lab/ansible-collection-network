.. _ansible_collections.ak1ra_lab.network.docsite.architecture:

Architecture
============

The collection is a set of independent roles with explicit, narrow contracts.
Playbooks orchestrate the roles; roles do not call each other, with the
exception of the collection playbooks documented in :doc:`playbooks`.

The roles fall into four groups:

- Transparent proxy: ``tproxy`` (experimental).
- mihomo: ``mihomo_install``, ``mihomo_client``, ``mihomo_server``.
- Host networking: ``systemd_bridge``, ``systemd_netns``.
- Cloud-image network takeover: ``cloud_init``, ``netplan_static``,
  ``systemd_resolved``.

Transparent proxy: TPROXY versus TUN
------------------------------------

``tproxy`` is the engine-agnostic plumbing for engines that expose a TPROXY
inbound. It owns nftables marking, policy routing (``ip rule`` / ``ip route``),
sysctl tuning, and kernel module loading. The contract is its variable set:
``tproxy_listen_port`` (where TPROXY and DNS interception deliver packets),
``tproxy_uid`` / ``tproxy_gid`` (loop-prevention bypass mark), marks and route
table numbers, interfaces, and kernel-level bypass/reject CIDRs.

``mihomo_client`` deliberately does not consume the ``tproxy`` contract. It
reproduces the mihomo-setup TUN design (``auto-route``, ``auto-redirect``,
``auto-detect-interface``, and ``dns-hijack``), which needs no nftables marking
and no policy-routing service. The ``tproxy`` role remains the plumbing for
engines with a TPROXY inbound, such as sing-box.

mihomo client and server
------------------------

``mihomo_install`` owns only the static binary. It has no service identity, no
configuration, and no unit. The service roles own their own ``mihomo`` user,
unit, and configuration, and the collection playbooks apply the installer
first and wire its restart hook to the service role's handler.

``mihomo_server`` generates the VPS-side listeners and two controller-local
artifacts:

- ``playbooks/host_vars/<host>/mihomo_server.yaml`` - generated credentials,
  mode ``0600``, auto-loaded by Ansible on later runs.
- ``config/client_outbounds/<host>.proxies.yaml`` - clash-format client nodes
  ready for the client's ``providers/selfhost.yaml`` through
  ``mihomo_client_selfhost_files``.

``mihomo_client`` consumes those nodes, or inline nodes and airport
subscriptions, and renders the TUN profile. The profile templates are
hand-maintained; only a small set of values is rendered into them.

Bridges and namespaces
----------------------

``systemd_bridge`` owns shared host-level bridges. They are stable
infrastructure with one owner: bridges are declared once, and other roles or
playbooks attach ports (namespace veth legs, VM taps, further physical ports)
at run time. A bridge may have no uplink at all; it is then a pure L2 segment
island.

``systemd_netns`` consumes those bridges for per-service egress isolation. It
creates a network namespace with veth legs on one or more bridges, configures
the namespace addresses and default route, and joins selected systemd units
through drop-ins. It never creates or deletes bridges.

Cloud-image network takeover
----------------------------

``cloud_init``, ``netplan_static``, and ``systemd_resolved`` move a cloud image
from cloud-init-managed networking to a static netplan configuration and a
systemd-resolved host resolver:

- ``cloud_init`` writes the drop-in that disables cloud-init network
  configuration.
- ``netplan_static`` captures the live IPv4 state, renders the role-owned
  netplan file, and optionally removes cloud-init's netplan file after taking a
  backup.
- ``systemd_resolved`` manages the global resolver drop-in, DoT, domains, and
  the ``/etc/resolv.conf`` symlink mode.

Documentation contract
----------------------

Role argument specs in ``roles/<role>/meta/argument_specs.yml`` are the
canonical variable reference. Role READMEs keep narrative and deployed-artifact
details. Filter pages are generated from the plugins' ``DOCUMENTATION``
blocks.
