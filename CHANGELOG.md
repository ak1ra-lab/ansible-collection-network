# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog, and this project does not currently guarantee stable backward compatibility.

## [Unreleased]

### Added

- `ak1ra_lab.network.cloud_init`: cloud-init drop-ins under
  `/etc/cloud/cloud.cfg.d` - network ownership (`network: {config:
  disabled}`, optional `disable_network_activation`), stable SSH host keys
  (`ssh_deletekeys: false`), `/etc/hosts`/hostname preservation and a raw
  `cloud_init_extra_config` escape hatch.  The defaults are no-ops, so the
  role only changes cloud-init behavior when explicitly opted in.  `absent`
  removes every role-managed drop-in.
- `ak1ra_lab.network.netplan_static`: capture the live IPv4 state of the
  physical ethernet interfaces (primary + `ipv4_secondaries`) into
  `/etc/netplan/90-ansible-static.yaml`, with per-interface CIDR overrides,
  one default gateway, optional nameservers and a MAC-matched `set-name`.
  The role validates the config with `netplan generate`, applies it through a
  handler, backs up/removes cloud-init's `50-cloud-init.yaml` only after the
  cloud-init network drop-in is disabled, runs a merge-aware conflict
  preflight against `/lib/netplan`, `/usr/lib/netplan`, `/etc/netplan` and
  `/run/netplan`
  (`strict` / `overlap` / `none`), and hands the network back to cloud-init on
  `netplan_static_state: absent` (restoring the backup, or failing closed
  without one).  IPv4-only and fail-closed on an existing IPv6 default
  route/global address unless `netplan_static_allow_ipv6_loss: true`.
  Advanced netplan features use `netplan_static_config_template`.
- `ak1ra_lab.network.systemd_resolved`: manage systemd-resolved as the host
  resolver - global `DNS=`, `FallbackDNS=`, `Domains=`, `DNSOverTLS=`,
  `DNSStubListener=` and the `/etc/resolv.conf` `stub`/`uplink`/`static`/
  `unmanaged` mode, with a backup/restore path for a pre-role regular
  resolver file.  No static-file mode: `tproxy` and `mihomo_client` keep
  their own static resolver files, and a host must have exactly one
  `/etc/resolv.conf` owner.
- Unified rollback backup convention for the cloud-image roles:
  `/var/lib/ansible/<namespace>/<collection>/<role>/<absolute-path-without-leading-slash>`,
  with `netplan_static` writing
  `/var/lib/ansible/ak1ra_lab/network/netplan_static/etc/netplan/50-cloud-init.yaml`
  and `systemd_resolved` writing
  `/var/lib/ansible/ak1ra_lab/network/systemd_resolved/etc/resolv.conf`.  The
  path is fixed (first backup wins), not timestamped; `ansible.builtin.copy`
  `backup: true` is not used because it writes next to the destination and
  offers no backup directory.
- Playbook entry points `ak1ra_lab.network.cloud_init`,
  `ak1ra_lab.network.netplan_static` and
  `ak1ra_lab.network.systemd_resolved`; the roles are independent and
  compose in a site playbook (cloud_init -> netplan_static ->
  systemd_resolved) for a cloud-image network takeover.
- Filter plugins for `netplan_static`: `netplan_static_interfaces`
  normalizes Ansible interface facts into the minimal address/MAC model and
  validates IPv4 CIDR overrides; `netplan_conflicts` classifies foreign
  netplan files against the role-managed interfaces.  The merge-aware
  `overlap` policy allows complementary split configuration (for example a
  separate `mtu` file), warns about earlier shadowed keys and hard-fails on
  later key overrides, different IDs matching the same device, or a
  same-named `/run/netplan` file shadowing the role file.  Unit tests cover
  the normalization, merge-order and conflict paths.
- Molecule scenarios `cloud_init`, `netplan_static` and `systemd_resolved`,
  sharing the existing containers.  `netplan_static` runs with `apply:
  false` and validates the rendered file with `netplan generate`; the real
  network change and the cloud-init handback/reboot flow remain VM-level
  checks.
- `ak1ra_lab.network.mihomo_install`: shared mihomo binary installer - the
  official **statically linked** `.gz` archive from the MetaCubeX/mihomo
  GitHub releases, resolved with `ak1ra_lab.general.github_releases_info`
  (platform asset selection and the GitHub asset digest as the `get_url`
  checksum), decompressed on the target and installed as
  `/usr/local/bin/mihomo`.  Distribution-neutral on systemd-based Linux: no
  `apt`/`dnf`, no package-manager bookkeeping, no service identity.  Version
  policy `present` (install only when the binary is missing, repeated runs
  need no network), `latest`, or a pinned version such as `1.19.32`, with a
  controller-local `mihomo_install_package_src` (file or URL) archive
  override.  On amd64 the
  microarchitecture build (`-v1-`/`-v2-`/`-v3-` variants) is selected from
  the level detected by `ak1ra_lab.general.cpu_info` (baseline fallback, a
  forced level, or `none` to disable), and `mihomo_install_force` reinstalls
  a matching version when needed.  The mihomo roles now require the
  `ak1ra_lab.general` collection (not on Galaxy yet; see `README.md`).
- `ak1ra_lab.network.mihomo_client`: mihomo TUN transparent-proxy client
  (LAN gateway or host-only), reproducing the hand-written
  [mihomo-setup](https://github.com/ak1ra-lab/mihomo-setup) profile.  The
  role owns the service identity (`mihomo` user/group), the generated profile
  and the systemd unit (the binary comes from `mihomo_install`, applied by
  the playbook), provisions the data file the profile depends on
  (`BundleMRS.7z`) from the MetaCubeX/meta-rules-dat release with the asset
  digest as the checksum (a controller-local `*_src` override skips the
  lookup; the release lookup authenticates with the controller's
  `$GITHUB_TOKEN` when present), renders the profile
  (TUN `auto-route`/`auto-redirect`, an explicit rule-set DNS split instead
  of the deprecated `fallback`/`fallback-filter`, interface sniffer),
  persists the `tun` module at boot, frees `:53` from systemd-resolved
  (stopped/disabled when present, `/etc/resolv.conf` replaced with the
  mihomo listener) and (in `gateway` mode) deploys the `ip_forward` /
  `rp_filter` sysctl drop-in; `absent` removes the role-managed artifacts,
  restores systemd-resolved and the distro `/etc/resolv.conf` stub symlink,
  and keeps providers, caches and the data file.  At least one node source
  (`mihomo_client_proxy_providers`, `mihomo_client_selfhost_proxies`,
  `mihomo_client_selfhost_files`) is required when applying, and an optional
  `mihomo_client_local_artifacts_dir` mirrors the rendered profile on the
  controller for backup/diff.  The profile itself ships as two
  hand-maintained templates (static proxy-group topology, rule providers,
  rules and DNS split; only a handful of `mihomo_client_*` values are
  rendered into them): the default plain profile has two tiers and merges
  self-hosted nodes into the normal region groups, while the selfhost-tier
  profile keeps a separate `*-自建` tier (US/SG/JP plus the catch-all) for
  chain-proxy deployments (`mihomo_client_selfhost_tier`).  Both reproduce
  the mihomo-setup deployment shape with the sing-box-tproxy group topology
  (top-level selectors, per-region selector / url-test tiers, explicit
  default selection, no group-level fallback on the default path) and
  pre-filled inline custom rule sets driven by payload lists.
- `ak1ra_lab.network.mihomo_server`: mihomo proxy server on the VPS side
  (`listeners:` schema, shadowsocks/trojan/hysteria2/vless/tuic/anytls,
  TLS paths that are either operator-managed or copied from an external
  source because mihomo has no built-in ACME) with
  the credential workflow reused from `sing_box_server`: the first N names of
  a user pool get generated passwords/UUIDs when the `*_users` lists are
  empty, every reference (server address, region token, user mapping) is
  reused by the client artifacts, and the run persists the credentials to
  `playbooks/host_vars/<host>/mihomo_server.yaml` (mode 0600, auto-loaded by
  Ansible on later runs) plus clash-format client nodes to
  `config/client_outbounds/<host>.proxies.yaml` for the client's
  `providers/selfhost.yaml`; an optional external-controller secret and a
  configurable client-node prefix are available.
- `mihomo_server`: optional AnyTLS **JLS** outer TLS mode
  (`mihomo_server_anytls_security_mode: jls`) with `jls-config` on the server,
  `jls-opts` on the generated client nodes, independent per-user JLS
  credentials persisted to host_vars, and unauthenticated-probe fallback to
  `mihomo_server_anytls_jls_dest`.  The generated node uses the JLS SNI/ALPN
  instead of the server hostname and is mihomo-only (mihomo >= 1.19.29).
  Certificate mode remains the default and its output is unchanged.  AnyTLS
  padding schemes are now syntax-validated before rendering because
  `mihomo -t` does not validate listener runtime parameters.
- `mihomo_server` can consume an externally managed TLS pair:
  `mihomo_server_tls_source_certificate_path` / `_key_path` are copied into
  `mihomo_server_tls_dir` (`0640 root:mihomo`) on every apply, and
  `mihomo_server_tls_renewal_hook_enabled` installs an independent certbot
  deploy hook (`renewal-hooks/deploy/mihomo-server.sh`) that re-copies the
  pair and reloads mihomo after a renewal.  The role still owns the initial
  copy; the hook only covers `certbot renew`, and it does not replace the
  certbot role's own deploy hooks.
- The `ak1ra_lab.network.mihomo_server` playbook can orchestrate
  `ak1ra_lab.general.certbot` before the server role
  (`mihomo_server_tls_certbot_enabled`): it leaves the certificate list and
  challenge/provider configuration to the normal `certbot_*` contract,
  derives the role's source paths from `live/<lineage>` and enables the
  independent renewal hook.  The default remains manual TLS paths.
- Molecule scenario `mihomo_server_certbot`: a local Pebble ACME server
  (HTTP-01 standalone, EAB) exercises the certbot-backed playbook end to
  end - issuance, the role's initial copy and permissions, the independent
  renewal hook, idempotence and teardown.  Debian-only because Pebble comes
  from the Debian archive.
- Playbook entry points `ak1ra_lab.network.mihomo_install`,
  `ak1ra_lab.network.mihomo_client` and `ak1ra_lab.network.mihomo_server`:
  the mihomo roles never call each other, the client/server playbooks apply
  `mihomo_install` first and wire its restart hook to the service role's
  handler.
- Custom filter plugins shared by the mihomo roles: `mihomo_providers`
  normalizes the subscription providers (derived cache paths, the reserved
  `selfhost` provider) and validates the self-hosted node naming contract
  (tag, unique names, optional region check), `mihomo_server` generates the
  per-protocol listener user shapes and the clash-format client nodes, and
  `to_pretty_yaml` renders the YAML with the pure-Python emitter so the
  astral-plane emoji stay literal (libyaml escapes them) and block
  sequences are indented like the hand-written files.  Contract violations
  raise `AnsibleFilterError` instead of producing a broken profile.
- Custom lookup plugins for the credential generation used by
  `mihomo_server`: `random_password` (`secrets.choice` over an
  ASCII-alphanumeric alphabet), `random_base64_key`
  (`secrets.token_bytes` base64 key material for the shadowsocks 2022
  ciphers) and `random_uuid` (`uuid.uuid4()`).
- Unit tests for the filter and lookup plugins and the profile template
  (`tests/unit/`, run by a new `unit` CI job with pytest) covering the
  template rendering (the plain and selfhost-tier topologies, the
  conditional inline custom rule sets, the rule order and the DNS policy),
  the provider normalization, the self-hosted naming contract, the six
  listener shapes, the client-node naming contract and the switch/null-input
  hardening, plus
  Molecule scenarios for both mihomo roles that converge the real binary
  and data files on the shared containers (the `mihomo_client` scenario
  proves the TUN device, the table-2022 policy routes, the live nftables
  `auto-redirect` table, the DNS `:53` takeover from systemd-resolved, the
  gateway sysctl drop-in and the live Clash API, including the artifact
  merge path and the region-group membership of the self-hosted nodes).
- `systemd_netns` per-netns sysctls (`systemd_netns_sysctl_params`),
  re-applied after every namespace (re)creation through the unit's
  `ExecStart`, documented with evidence-driven BitTorrent tuning
  candidates; only per-netns keys are isolated to the namespace,
  host-global keys are documented as such.
- Molecule test scenarios (`extensions/molecule/`, collection-testing
  layout) for `systemd_bridge`, `systemd_netns`, `tproxy`, `flow_offload`
  and `proxy_guard`, running the roles against the systemd-enabled
  container images of
  [ak1ra-lab/docker-systemd](https://github.com/ak1ra-lab/docker-systemd)
  (debian-12/13, ubuntu-24.04/26.04) over the `containers.podman.podman`
  or `community.docker.docker` connection, with `shared_state` making the
  `default` scenario the lifecycle manager of the shared containers.
  Component scenarios run prepare, converge, idempotence, verify, the
  role's teardown via `cleanup.yml` and a post-cleanup verification; root
  `requirements.yaml` and justfile recipes cover the control-node setup,
  the container runtime is selectable via `MOLECULE_CONTAINER_RUNTIME`
  (Podman default, rootful Docker opt-in), the host kernel module tree is
  bind-mounted read-only into the containers for the `tproxy` modprobe
  calls, and the shared preparation refreshes the images' apt index.  A
  GitHub Actions workflow runs ansible-lint and every scenario (rootful
  Podman) on pull requests and pushes to `master`/`dev`, with Dependabot
  keeping the SHA-pinned actions current.
- `mihomo_install_package_src`: a `.gz` archive override for
  `ak1ra_lab.network.mihomo_install`, given as a controller-local file
  (copied to the target) or an `http(s)`/`ftp` URL (fetched with get_url) -
  the value shape picks the transport.  It takes precedence over the release
  download, the escape hatch when the GitHub asset download is unreachable;
  `mihomo_client_bundle_src` accepts the same two shapes.
- `mihomo_server`: VLESS REALITY support
  (`mihomo_server_vless_reality_enabled`).  The server listener uses
  `reality-config` (borrowed `dest`, X25519 keypair, short ID, server names)
  instead of a certificate, the generated client node uses `reality-opts` and
  the first server name as its SNI, and the keypair/short ID are generated on
  the target and persisted to host_vars when left empty.
- `mihomo_server`: AnyTLS client nodes now set a configurable uTLS
  `client-fingerprint` (default `chrome`) and expose the idle-session check,
  timeout and minimum-idle knobs (defaults `30`/`30`/`0`).

### Changed

- `mihomo_server` default profile now enables shadowsocks, hysteria2,
  anytls and vless with REALITY + XTLS Vision (trojan and tuic are opt-in)
  and moves the listener ports to `9442-9447`; the filter fallback defaults,
  README and Molecule scenario follow the same values.  Hysteria2 server
  bandwidth stays unset, so the generated clients use BBR unless they
  explicitly opt into Brutal.
- `mihomo_client` profile reworked around two hand-maintained templates
  (`mihomo_client_config_template`, shipped as
  `templates/etc/mihomo/config.yaml.j2` and
  `templates/etc/mihomo/config.selfhost.yaml.j2`): the static mihomo YAML
  (group topology, rule providers, rules, DNS split) is no longer generated
  from role variables, and only the necessary values are rendered - mixed
  port, API secret, the TUN/DNS switches, the provider mapping and the
  custom rule-set payloads; copying either template is the customization
  path.  The default plain profile has 19 groups in two tiers and merges
  self-hosted nodes into the normal region groups; setting
  `mihomo_client_selfhost_tier: true` selects the 23-group selfhost-tier
  profile (three tiers, `*-自建` limited to US/SG/JP plus the catch-all) for
  chain-proxy deployments.  Both keep the sing-box-tproxy topology (no
  fallback / include-all auto group on the default path, `PROXY` pinned to
  `🚀 所有节点` through `default-selected`); `TELEGRAM` was renamed
  `Telegram`.  The bundled rule providers gain the
  `geosite-steam@cn` split (the Steam CDN/download domains route `DIRECT`
  and resolve through the domestic DoH pair while the store/community
  domains keep the `Steam` group), and the pre-filled inline rule providers
  (`custom-internal` / `custom-rejected` / `custom-direct` / `custom-proxied`;
  the internal set renders with `mihomo_client_custom_internal_nameservers`,
  the others have a domain and an `-ip` variant) render from
  `mihomo_client_custom_*_payload` lists only when non-empty.
- The mihomo install contract moved out of the service roles:
  `mihomo_install` is a standalone, distribution-neutral binary installer
  (static `.gz` archive to `/usr/local/bin/mihomo`), `mihomo_client` /
  `mihomo_server` own their service identity and systemd unit, and the new
  playbook entry points orchestrate them.  The service roles' install
  variables (`mihomo_client_install` / `_version` / `_package_url` and the
  matching `mihomo_server_*` set) were replaced by the `mihomo_install_*`
  contract.
- `mihomo_*` enumeration lists (`mihomo_install_version_available`,
  `mihomo_client_state_available` / `_mode_available`,
  `mihomo_server_state_available`) moved from `defaults/main.yaml` into
  `vars/main.yaml`, keeping the overridable contract short (same convention
  as `systemd_netns`).
- Renamed the scenario collection requirements file from `requirements.yml`
  to `requirements.yaml`; `ak1ra_lab.general` is not listed there (it is not
  on Galaxy yet) and is installed from git instead - the justfile dev
  recipes use the local `GENERAL_COLLECTION` sibling checkout to test
  unpushed changes, and CI installs the git source.
- Simplified `.ansible-lint` to `profile`, `exclude_paths` and `skip_list`;
  dropping the explicit `kinds:` mapping restores the default kind detection,
  which had been silently disabling `var-naming[no-role-prefix]` for role
  defaults (and lints the Molecule playbooks as playbooks again).
- Added the uv-managed development tooling (`pyproject.toml`, `ruff.toml`):
  `just sync`, `just lint` (ruff check + format on `plugins/` and `tests/`),
  `just typecheck` (ty) and `just unit-test` (pytest).  `ruff.toml` keeps
  the ruff default rule set with `line-length = 120`.  The justfile `lint`
  recipe now runs ansible-lint as `just ansible-lint`.
- Collection filters and tests are written with their `ansible.builtin.`
  prefix in the `mihomo_*` roles and scenarios (`bool`, `to_json`,
  `from_yaml`, `b64decode`, `type_debug`, `search`, ...), while Jinja2
  builtins (`default`, `trim`, `indent`, `map`, `list`, ...) stay bare.
- `systemd_netns` convention values and derived names (enumeration lists,
  verification URL, veth prefix/service names) move from
  `defaults/main.yaml` into `vars/main.yaml`, keeping the overridable
  public contract short; `systemd_netns_name` defaults to `qbittorrent`
  (the role's reference workload) instead of `dedicated_net`.
- `ak1ra_lab.network.systemd_netns` applies the host bridges declared for
  the run (`systemd_bridge_bridges`) before the namespace: the playbook
  chains `systemd_bridge` and flushes its handlers before `systemd_netns`
  validates the namespace, so one run can also bring up a fresh host.  The
  role itself still never calls other roles.
- `flow_offload` and `proxy_guard` honor their `*_enabled` master switch in
  `tasks/present.yaml`: the drop-in is only deployed while the switch is on,
  and a drop-in left behind by a previous run is removed when it is turned
  off (the removal notifies the nftables service restart).  Before, the
  documented switch was never read and applying either role always deployed
  the table.
- `mihomo_client` / `mihomo_server` service identity defaults are now
  `mihomo`/`mihomo` (was `proxy`/`proxy`), and both systemd units pin
  `LimitNOFILE=1000000`, following the upstream mihomo service file:
  `infinity` resolves to an excessive 2^30 soft+hard limit since systemd
  v240 (the same reason the AOSC OS package overrides the value).
- `mihomo_client` fetches both profile data files from the single
  `mihomo_client_data_repo` variable (the per-file
  `mihomo_client_geoip_repo` / `mihomo_client_bundle_repo` overrides are
  gone - the assets ship in the same release).
- `mihomo_server` relies on Ansible's host_vars auto-loading instead of
  reading the stored credential artifact back (`stat` + `slurp` + merge):
  the role generates only the values that are still empty, and a custom
  `mihomo_server_host_vars_file` outside the auto-load locations (next to
  the playbook or the inventory) is treated as absent and regenerated every
  run.
- `mihomo_client` generates `mihomo_client_api_secret` with the
  `random_password` lookup when it is empty and persists it to
  `mihomo_client_host_vars_file` (default
  `playbooks/host_vars/<host>/mihomo_client.yaml`, mode 0600, auto-loaded on
  later runs) - the same workflow as the `mihomo_server` credentials; an
  explicit non-empty value always wins.
- The per-tier rule-set behavior documented for `dns.nameserver-policy`
  (an `ipcidr` rule-set is rejected at load, a `classical` set matches only
  its domain rules) keeps the `mihomo_client` custom domain/IP payload
  lists separate.
- The mihomo release lookups authenticate with the controller's
  `GITHUB_TOKEN` environment variable when present (rate limits); export it
  for the playbook run instead of setting a role variable.
- `mihomo_client` / `mihomo_server`: the service identity and paths
  (`*_user` / `*_group` / `*_etc_dir` / `*_binary`) moved from
  `defaults/main.yaml` into `vars/main.yaml` as role conventions, keeping
  the overridable contract short (override with role params or `-e`).

### Removed

- The mihomo profile-generation filter plugins (`mihomo_proxy_groups`,
  `mihomo_rule_providers` / `mihomo_rules` and the `mihomo_dns`
  `mihomo_nameserver_policy`) with the `mihomo_client_profile` spec, and the
  per-field profile variables that became template content
  (`mihomo_client_log_level`, `mihomo_client_allow_lan` /
  `_bind_address`, `mihomo_client_ipv6`, `mihomo_client_store_selected`,
  `mihomo_client_external_ui`, the TUN detail variables, the DNS detail
  variables and the sniffer variables).  `mihomo_client_proxy_providers` and
  the `mihomo_client_selfhost_*` flow stay;
  `mihomo_selfhost_proxies`' region check is now optional (the region
  regexes live in the template).
- The `🇪🇺 欧洲节点` and `🇰🇷 韩国节点` region tiers from the
  `mihomo_client` profile: neither the current airport nor the self-hosted
  node set has nodes in those regions.  Nodes that appear there later still
  reach `🚀 所有节点` / `🚀 所有节点 - AUTO`; the region blocks can be
  re-added when a dedicated group is actually needed.
- `mihomo_server_client_proxies_dialer_proxy`: whether to chain a node is a
  client routing decision, and a fixed front-group name baked into every
  generated node cannot express it (nor keep the direct variant); clients
  can declare `dialer-proxy` on their own inline nodes instead.
- The GitHub-proxy download prefixes `mihomo_install_github_proxy` /
  `mihomo_client_github_proxy` (they only prefixed the asset download - the
  release metadata query was always direct - and a broken proxy made the
  download fail) and the `mihomo_install_github_token` /
  `mihomo_client_github_token` variables (the lookups read the
  `GITHUB_TOKEN` environment variable directly); use
  `mihomo_install_package_src` / `mihomo_client_bundle_src` (a local file or
  a URL) for an offline download.
- `mihomo_client_tun_enable` / `mihomo_client_dns_enable`: the profile
  template always renders the TUN and DNS sections and the matching host
  state (the `tun` modules-load entry and the resolver takeover) always
  applies; the takeover keeps its `mihomo_client_dns_manage_resolved` /
  `_manage_resolv_conf` controls.

### Fixed

- Jinja2 builtins are no longer written with the `ansible.builtin.` prefix
  in the `systemd_bridge` / `systemd_netns` tasks, the `mihomo_*` role
  tasks/templates and throughout the Molecule playbooks: the FQCN form of a
  Jinja2 builtin (`ansible.builtin.default`, `ansible.builtin.trim`,
  `ansible.builtin.list`, `ansible.builtin.int`, ...) only resolves on
  ansible-core 2.19+, so the roles would fail to render on the declared
  minimum (2.18).  Collection plugins are qualified in the same sweep
  (`ansible.builtin.bool`, `ansible.builtin.search`,
  `ansible.builtin.type_debug`, `ansible.builtin.b64decode`, `is
  ansible.builtin.version`, ...) in the roles and the Molecule verifies.
- `mihomo_client` reads the `mihomo_client_selfhost_files` artifacts in a
  dedicated task: the file lookup ran inside the node-list expression, so a
  missing/mistyped entry failed with ansible-core's opaque
  `CapturedExceptionMarker` concat error instead of naming the file.  The
  read now surfaces the lookup error (with the file path and the failing
  item), and the variable documentation spells out that relative entries
  resolve against the role/playbook directories, not the working directory
  (anchor them with `{{ playbook_dir }}`-based or absolute paths).
- `mihomo_server` generates the credentials with the new
  `ak1ra_lab.network.random_password` / `random_base64_key` / `random_uuid`
  lookup plugins (control-node CSPRNG) instead of inline Jinja: the
  shadowsocks 2022 key is base64 key material from `secrets.token_bytes`
  (full entropy per byte, decoded length equal to the cipher key length),
  and the vless/tuic identifiers are real `uuid.uuid4()` values - the inline
  `ansible.builtin.password` + `regex_replace` chain produced 36 random hex
  digits reformatted as a UUID without the RFC 4122 version/variant bits.
- `mihomo_server` no longer copies the hysteria2 `up`/`down` server caps
  into the generated client nodes.  The same pair was interpreted as
  server-side caps by the listener and as client-side hints by the client,
  so an asymmetric client link could not be represented, and the old
  `1000`/`1000` default put every client on Brutal at an arbitrary rate.
  Client nodes now omit bandwidth (mihomo falls back to BBR), and the
  server-side variables default to `0` (omitted); set them only when
  clients opt into Brutal and the server should enforce a per-client cap.
- `mihomo_client` gateway mode deployed `net.ipv4.conf.all.rp_filter=1` (the
  `mihomo_client_sysctl_rp_filter` default was `true`, meaning the value 1)
  while its documentation, the mihomo-setup baseline and the Molecule
  scenario all expect `0`: strict reverse-path filtering drops the
  asymmetric policy-routed proxy path.  The default now writes 0 (the
  booleans map to the sysctl values 1/0).
- `mihomo_client` downloaded the profile data files (`geoip.metadb`,
  `BundleMRS.7z`) with the wrong loop item reference (`item.item` while the
  release lookup loop had renamed its variable to `data_file`), so the first
  run on a host without the data files failed while rendering the download
  destination; the download task now reads its `release` loop variable
  (`release.data_file.dest` / `release.data_file.name`).
- `mihomo_install` no longer rewrites the shared `/var/tmp` directory (the
  old "ensure the deb cache directory exists" task forced `mode: 0755`
  root:root onto the public path, stripping the sticky bit and the world
  write permission); the archive now downloads into a role-owned
  `ansible.builtin.tempfile` directory (mode 0700) that is removed after
  every run.
- `systemd_bridge` detects an actual NetworkManager installation by probing
  the unit file instead of `ansible_facts['services']`: on Debian-family
  hosts the packaged apt-daily units reference NetworkManager.service in
  their `After=` lines, which makes systemd instantiate a not-found unit and
  service_facts report NetworkManager.service even where NetworkManager is
  not installed - the role then wrote unmanaged-devices drop-ins and the
  reload handler failed hard on hosts without NetworkManager.
- `systemd_bridge` renders `RequiredForOnline=` in the `[Link]` section for
  interface-less bridges carrying an address instead of `[Network]`, where
  systemd-networkd ignores the key: such a bridge never has carrier on its
  own (its veth legs attach at run time, after network-online.target), so it
  stayed required-for-online and systemd-networkd-wait-online could wait for
  it forever - blocking network-online.target at boot.
- `systemd_netns` validates the bridged topology (links, referenced bridges)
  only when applying (`systemd_netns_state: present`): teardown (`absent`)
  needs only the namespace name.  Referenced bridges must now carry at least
  one enslaved member interface - a bridge without any uplink is an L2
  island the namespace cannot exit through; the defaults documented this
  contract but the check was missing.
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
- `ansible-galaxy collection build` ships controller-local
  `playbooks/host_vars/` and `playbooks/group_vars/` content: `graft
  playbooks` overrides `.gitignore`, so generated credentials and inventory
  data could enter the artifact.  The manifest now excludes the local
  vars, scripts and templates directories (the same convention as
  `ak1ra_lab.general`).

## [v0.2.0] - 2026-09-09

### Added

- `systemd_bridge` — declarative host-level Linux bridges, each optionally
  enslaving one dedicated physical interface, managed entirely by
  `systemd-networkd` (`.netdev` files, enslave `.network` files,
  NetworkManager `unmanaged-devices` drop-ins when NetworkManager is
  running).  Bridges without an `interface` are pure L2 private segments
  (no uplink).  Bridges are shared, stable infrastructure; STP, forward
  delay, FDB ageing time, multicast snooping and VLAN filtering are
  configurable per bridge, and an optional `address` gives the bridge (and
  thereby the host) an L3 presence on the segment.  `RequiredForOnline=` is
  scoped to links that actually carry host connectivity (address-carrying
  bridges and teardown release files keep the default; enslaved ports and
  address-less bridges are excluded), so `systemd-networkd-wait-online`
  neither stalls on never-online devices nor loses its only required link.
- `systemd_netns` — dedicated-segment egress isolation (opt-in,
  independent): a network namespace attaching veth legs to the host-level
  bridges of `systemd_bridge` (or any existing bridge), carrying real
  segment addresses and its default route via the leg that declares a
  gateway - the host does no routing, NAT or filtering for this traffic.
  `systemd_netns_links` entries are one veth leg per segment
  (`{bridge, address, gateway?, mac?}`), with at most one gateway leg owning
  the default route; bridge existence and gateway subnet membership are
  validated at run time.
- Collection dependency on `ansible.utils >= 6.0.0` for `systemd_netns` link
  validation (`ipaddr` / `in_network` filters on the control node).
- Egress verification (`systemd_netns_verify`) uses `curl` consistently for
  the namespace and the host against a configurable exit-IP echo service
  (`systemd_netns_verify_url`, default `https://ip.sb`); the namespace
  resolv.conf defaults to AliDNS `223.5.5.5` and DNSPod `119.29.29.29`.
- Collection playbooks `ak1ra_lab.network.systemd_bridge` and
  `ak1ra_lab.network.systemd_netns`: thin entry points running the roles on
  `localhost` by default with root privileges; the built artifact ships
  `playbooks/` (`galaxy.yml` manifest graft).

### Changed

- `systemd_bridge` networkd artifacts are named after the device they
  configure with numeric prefixes encoding the load order: `10-<name>.netdev`
  (bridge definition), `15-<interface>.network` (uplink enslave) and
  `20-<name>.network` (bridge configuration, always rendered - a bridge
  without a matching `.network` file is not managed by networkd at all;
  `address`/`gateway`/`dns` are added when declared).  Every rendered file
  embeds an ownership marker comment
  (`# ... managed by ak1ra_lab.network.systemd_bridge ...`), and the networkd
  conflict preflight (`systemd_bridge_conflict_check`) evaluates `Name=`
  patterns semantically instead of grepping: a file only conflicts when one
  of its shell-glob patterns actually matches a managed device (marker-carrying
  files are this role's own), so distro-packaged wildcard defaults such as
  `80-container-*.network` or `80-vm-vt.network` are ignored unless they
  really claim a managed interface or bridge.
- `systemd_bridge` enslave file places `Bridge=` under `[Network]`; the
  previous `[Bridge]` section made systemd-networkd ignore the enslave
  (`Unknown key 'Bridge' in section [Bridge]`), leaving the uplink
  unconfigured and the host unreachable after a reload.
- `systemd_bridge` teardown release files now take over the regular
  `15-<interface>.network` path instead of a separate file of their own.
- `systemd_netns` teardown discovers leftover veth legs by naming prefix
  instead of relying on the declared link list.
- `systemd_netns` teardown stops namespace-joined services discovered from
  the namespace's own processes via cgroup attribution
  (`ip netns pids` + `/proc/<pid>/cgroup`) instead of deriving unit names
  from drop-in paths - this also handles template-unit instances
  (`foo@bar.service` hooked through a `foo@.service` drop-in).
- `systemd_bridge` bridges may carry an optional `gateway` and `dns` next to
  their `address` (host-uplink style; at most one gateway-carrying bridge
  per host, gateway must lie inside the address network).
- `systemd_bridge` teardown is connectivity-safe when requested: per-bridge
  `absent_release_mode: static|dhcp` writes a release `.network` file so the
  freed physical interface keeps the former address (or uses DHCP) in the
  same networkd restart that drops the bridge; address-carrying bridges
  removed without a release mode are reported.
- `systemd_bridge` preflights the networkd configuration directories
  (`systemd_bridge_conflict_check`) and fails when other `.network` files
  already match the interfaces or bridges it manages.
- The `systemd_netns` documentation now describes per-service next-hop
  gateway selection in both directions: host proxied with a service direct,
  or host direct with a single service proxied through a TPROXY gateway on
  the same bridged segment.

## [v0.1.0] - 2026-09-07

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
