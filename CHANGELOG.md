# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog, and this project does not currently guarantee stable backward compatibility.

## [Unreleased]

### Added

- Initial collection with three roles:
  - `tproxy` — engine-agnostic TPROXY transparent proxy plumbing (nftables
    marking, policy routing, sysctl), extracted from
    `ak1ra-lab/sing-box-tproxy` `roles/sing_box_tproxy` and renamed to the
    `tproxy_*` variable contract.
  - `flow_offload` — nftables flowtable offloading for forwarded traffic
    (opt-in, independent).
  - `proxy_guard` — per-client TCP abuse protection with throttle / auto-ban
    (opt-in, independent).
- Declarative state for every role: `<role>_state` (default `present`);
  `absent` atomically tears down the role's own artifacts via
  `tasks/reset.yaml`, leaving shared system files untouched.

### Changed

- `flow_offload` and `proxy_guard` honor their `*_enabled` master switch in
  `tasks/present.yaml`: the drop-in is only deployed while the switch is on,
  and a drop-in left behind by a previous run is removed when it is turned
  off (the removal notifies the nftables service restart).  Before, the
  documented switch was never read and applying either role always deployed
  the table.

### Fixed

- `tproxy` notified a `restart ansible-tproxy-routing.service` handler that
  did not exist (the handler was named `restart tproxy-routing.service` and
  pointed at the wrong unit), so the first application of the role failed
  while rendering `/etc/systemd/system/ansible-tproxy-routing.service`; the
  handler now matches the notification and restarts
  `ansible-tproxy-routing.service`.
- `proxy_guard` restores the guard parameter defaults its README documents -
  `proxy_guard_lan4_subnets` (the RFC 1918 trio) and
  `proxy_guard_lan6_subnets` (`[]`), the throttle set
  (`false` / `600` / `150` / `2m`) and the auto-ban set
  (`false` / `1200` / `300` / `5m`) - which the collection split dropped
  together with the switch gating.
