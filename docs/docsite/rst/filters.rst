.. _ansible_collections.ak1ra_lab.network.docsite.filters:

Filter plugins
==============

The collection ships filter plugins used by its roles and available to
consumer playbooks. Generated reference pages are built from each plugin's
``DOCUMENTATION`` block.

.. list-table::
   :header-rows: 1
   :widths: 48 52

   * - Filter
     - Purpose
   * - :doc:`mihomo_proxy_providers_filter`
     - Render mihomo proxy providers and self-hosted node files.
   * - :doc:`mihomo_selfhost_proxies_filter`
     - Normalize self-hosted proxy mappings for the client profile.
   * - :doc:`mihomo_server_client_proxies_filter`
     - Render clash-format client nodes from the server listener spec.
   * - :doc:`mihomo_server_config_filter`
     - Render the mihomo server configuration from the role contract.
   * - :doc:`netplan_static_interfaces_filter`
     - Select and normalize interfaces for the static netplan file.
   * - :doc:`netplan_static_default_routes_filter`
     - Select default routes for the static netplan file.
   * - :doc:`netplan_conflicts_filter`
     - Detect conflicting netplan configuration.
   * - :doc:`networkd_conflicts_filter`
     - Detect conflicting systemd-networkd configuration.
   * - :doc:`to_pretty_yaml_filter`
     - Render YAML with stable, readable formatting.

Most filters are implementation details of a role. Use the role argument specs
for the supported interface; the filter reference documents the underlying
functions for maintainers and advanced consumers.
