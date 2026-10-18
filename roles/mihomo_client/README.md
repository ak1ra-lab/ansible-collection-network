# ak1ra_lab.network.mihomo_client

Deploys [mihomo](https://github.com/MetaCubeX/mihomo) as a TUN
transparent-proxy client, based on the hand-written
[mihomo-setup](https://github.com/ak1ra-lab/mihomo-setup) deployment:

- the TUN inbound (`auto-route` + `auto-redirect` + `auto-detect-interface`
  + `dns-hijack`) captures both local and LAN-forwarded traffic, so a LAN
  client only needs this host as its gateway/DNS - no nftables marking, no
  policy-routing service and no `ak1ra_lab.network.tproxy` dependency;
- the profile is a hand-maintained template (static mihomo YAML plus a
  handful of rendered values): top-level selectors (`PROXY` / `FINAL` /
  application / `SSH`) over per-region selector / url-test / self-hosted
  tiers, an explicit `default-selected` on `PROXY` (no latency auto or
  fallback group on the default path) and `DIRECT` escape hatches in the
  top-level members;
- DNS stays `redir-host` (real answers) with a static rule-set split:
  `nameserver-policy` sends the direct-routed domain sets (private, CN, the
  Steam-CN download set and the custom direct set) to domestic DoH, the
  custom internal set to its own resolvers, everything else leaves through
  the foreign DoH `#RULES` pair - no `fallback`/`fallback-filter`, no
  GeoIP/GeoSite data file - and the interface sniffer completes the
  picture;
- providers are hot-reloaded: overwriting `providers/*.yaml` does not
  restart the service; only `config.yaml` changes do.

The role owns the service identity (`mihomo` user/group), the profile, the
systemd unit and the service.  It does **not** install the binary:
`playbooks/mihomo_client.yaml` applies `ak1ra_lab.network.mihomo_install`
(the `mihomo_install_*` contract: version policy `present` / `latest` /
pinned version, optional GitHub proxy, amd64 microarchitecture-aware asset
selection) before this role.  The role only asserts that the binary exists.

It also provisions the data file the profile depends on (`BundleMRS.7z`,
resolved from the MetaCubeX/meta-rules-dat release with
`ak1ra_lab.general.github_releases_info` and verified with the GitHub asset
digest).

It does **not** manage a firewall, the host's default route outside mihomo's
own policy routing, or subscription credentials (keep those in uncommitted
group_vars).

## Requirements

- A systemd-based Linux host with a writable `/dev/net/tun` and the `tun`
  kernel module (loaded at boot through the role's `modules-load.d` entry);
  the mihomo binary is deployed by `ak1ra_lab.network.mihomo_install`
  (systemd Linux, static `.gz` archive).  The default TUN `auto-redirect`
  needs kernel nftables support (Debian/Ubuntu stock kernels have it;
  kernels without it need `DISABLE_NFTABLES=true` plus `iptables`, set
  through a unit drop-in).
- A host resolver that can be freed for `dns.listen`: on Debian/Ubuntu
  cloud images the role stops/disables systemd-resolved and takes over
  `/etc/resolv.conf` (see the DNS section below).
- For `mihomo_client_mode: gateway` the host must be the LAN's gateway (or
  be advertised as one); the role only sets `net.ipv4.ip_forward=1` and
  `net.ipv4.conf.all.rp_filter=0`.  Switching back to `local` removes the
  drop-in, but the runtime sysctl values stay in effect until reboot.
- Control node: `ak1ra_lab.general` (>= 0.2.0) for `github_releases_info`
  (installed from git, not published to Galaxy; see the collection README).

## What it deploys

| Artifact | Purpose |
| --- | --- |
| `/usr/local/bin/mihomo` | mihomo binary, deployed by `mihomo_install` (playbook) |
| `/etc/mihomo/config.yaml` | the rendered profile (`mihomo_client_config_template`) |
| `/etc/mihomo/providers/selfhost.yaml` | self-hosted nodes (inline + `mihomo_server` artifacts), mode 0640 |
| `/etc/mihomo/providers/` | airport subscription caches (role-created directory, contents user-managed) |
| `/etc/mihomo/BundleMRS.7z` | rule-set bundle, the mandatory data file (release download or explicit `*_src` file/URL) |
| `/etc/systemd/system/mihomo.service` | service unit (`ExecStartPre` config test, capabilities for TUN + :53) |
| `/etc/resolv.conf` | static `nameserver 127.0.0.1` while deployed (`mihomo_client_dns_manage_resolv_conf`); teardown restores the distro stub symlink |
| `/etc/modules-load.d/ansible-mihomo-client.conf` | `tun` module at boot |
| `/etc/sysctl.d/90-ansible-mihomo-client-gateway.conf` | `ip_forward` / `rp_filter` (gateway mode only) |
| `<local artifacts dir>/<host>.config.yaml` | optional controller-local profile mirror (`mihomo_client_local_artifacts_dir`) |
| `<playbook>/host_vars/<host>/mihomo_client.yaml` | generated Clash API secret (0600, auto-loaded on later runs) |

## How it works

`tasks/present.yaml` ensures the service identity, asserts the binary
deployed by `mihomo_install`, fetches the data file, generates the Clash
API secret (persisted to host_vars) when it was not provided, renders the
profile and the selfhost provider, frees the resolver port
(`systemd-resolved`) and takes over `/etc/resolv.conf` before the service
starts, persists the `tun` module, applies (or removes) the gateway sysctl
drop-in, then validates the config with `mihomo -t -d /etc/mihomo` before
enabling and starting the service.  The service unit runs the same config
test as `ExecStartPre`, and `Restart=on-failure` recovers from a crashed
engine.

### The profile template

`mihomo_client_config_template` (default
`templates/etc/mihomo/config.yaml.j2`) is rendered to
`/etc/mihomo/config.yaml`.  It is a hand-maintained template: the group
topology, rule providers, rules and DNS split are plain mihomo YAML in that
file, and only the necessary values are rendered into it - the mixed port,
the API secret, the optional dashboard URL, the provider mapping and the
custom rule-set payloads.  Anything else (a different listen port, extra
regions, different DNS servers, ...) is a template edit: copy the file,
adjust it and point the variable at the copy (see "Customizing the profile"
below).

The topology: 31 proxy groups in three tiers per region (seven regions plus
the `🚀 所有节点` catch-all):

- `<region>` - selector over the all-provider pool matching the region
  regex, self-hosted nodes excluded;
- `<region> - AUTO` - url-test over the same pool (`interval` 300,
  `tolerance` 50);
- `<region> - 自建` - selector matching nodes that carry the
  `selfhost|自建` tag *and* the region token.

`🚀 所有节点` is the plain include-all selector (self-hosted nodes
included, so it stays populated on self-hosted-only deployments).
`PROXY` lists the three tiers (self-hosted first, then AUTO, then the
selector tier) plus `DIRECT`, and pins `default-selected: 🚀 所有节点` -
the default path is explicit and the latency AUTO tier is only a manual
choice.  `FINAL` and the application groups (`AI`, `Steam`, `Telegram`,
`Entertainment`) list all three tiers with `PROXY` / `DIRECT` on top;
`SSH` leads with `PROXY` / `DIRECT`.

In one of the region selectors or `PROXY`, no group-level fallback exists:
a node set that is present but dead fails closed, and the escape hatch is
selecting `DIRECT` (or stopping the service).

### Inline custom rule sets

The profile pre-fills eight inline rule providers; each one (and its rule)
only exists when the matching payload list is non-empty:

| Variable | Provider / rule |
| --- | --- |
| `mihomo_client_custom_internal_rule_set_payload` | `custom-internal-rule-set` -> `DIRECT` (+ `mihomo_client_custom_internal_nameservers`) |
| `mihomo_client_custom_rejected_rule_set_payload` | `custom-rejected-rule-set` -> `REJECT` |
| `mihomo_client_custom_rejected_rule_set_ip_payload` | `custom-rejected-rule-set-ip` -> `REJECT` |
| `mihomo_client_custom_direct_rule_set_payload` | `custom-direct-rule-set` -> `DIRECT` (+ domestic DNS) |
| `mihomo_client_custom_direct_rule_set_ip_payload` | `custom-direct-rule-set-ip` -> `DIRECT` |
| `mihomo_client_custom_proxied_rule_set_payload` | `custom-proxied-rule-set` -> `PROXY` |
| `mihomo_client_custom_proxied_rule_set_ip_payload` | `custom-proxied-rule-set-ip` -> `PROXY` |

Domain sets take clash wildcard domains (`ads.example` matches exactly,
`.ads.example` the subdomains, `+.ads.example` both), the `*_ip` sets take
CIDRs (`10.20.0.0/16`).  The two lists are separate because mihomo's
rule-set `behavior` is the payload type, not a hint: `dns.nameserver-policy`
rejects an `ipcidr` rule-set at config load ("rule provider type error,
expect domain") and accepts a `classical` set only with a warning that just
its domain rules are matched, so the internal/direct domain sets stay
`domain` behavior.  The custom rules render before the geo rules, so they
override them: the internal set routes its domains `DIRECT` and resolves
them through `mihomo_client_custom_internal_nameservers` (set both
together - the play fails otherwise, since those domains would otherwise
resolve through the foreign DoH pair); the direct set resolves through the
domestic DoH pair, mirroring its route.  Arbitrary rule syntax
(`PROCESS-NAME`, ...) still belongs into a copied template's `rules:`
block.

### Providers and self-hosted nodes

`mihomo_client_proxy_providers` holds the airport subscriptions keyed by
name; a `type: http` provider without an explicit `path` gets
`./providers/<name>.yaml`.  The reserved `selfhost` file provider
(`./providers/selfhost.yaml`, hot-reloaded by mihomo) is always injected
last; its node list is the concatenation of `mihomo_client_selfhost_proxies`
(inline clash mappings) and the artifacts named by
`mihomo_client_selfhost_files` (the `mihomo_server` role writes
`config/client_outbounds/<host>.proxies.yaml`).

The artifact entries go through Ansible's file lookup, so a relative path
resolves against the role/playbook directories, not the working directory:
anchor it with `{{ playbook_dir }}`-based or absolute paths.  Every node
name must carry the `selfhost|自建` tag (the role fails the play otherwise)
and a region token (the region regexes live in the profile template, so
they match at load time).  At least one node source must exist
(`mihomo_client_proxy_providers`, `mihomo_client_selfhost_proxies` or
`mihomo_client_selfhost_files`), otherwise the role fails the play.

### DNS

The DNS split is static in the profile template and rule-set based.
`nameserver-policy` (evaluated first) routes the direct-routed domain sets
to the domestic DoH pair:

- `geosite-private` - router portals (`tplogin.cn`, ...), special-use
  domains (`.lan`, `.home.arpa`, ...), private PTR zones and local-service
  names (`.ts.net`, ...).  Public DoH neither resolves nor should see
  those, so point the entry at the internal resolver where one exists by
  editing the template (e.g. `["192.168.1.1", "100.100.100.100"]`);
- `geosite-cn`;
- `geosite-steam@cn` - the Steam CDN/download domains (the CN CDN used by
  the Steam client: `csgo.com.cn`, `dl.steam.clngaa.com`,
  `st.dl.bscstorage.net`, `alibaba.cdn.steampipe.steamcontent.com`, ...).
  They route `DIRECT` and resolve nearby; the store/community domains stay
  in `geosite-steam` and leave through the `Steam` group;
- `custom-direct-rule-set` (only when its payload is set);
- `custom-internal-rule-set` (only when its payload and
  `mihomo_client_custom_internal_nameservers` are set) - intranet domains
  resolved by their own resolvers, e.g. `["192.168.1.1"]`; the private
  entry above can also be repointed at those while editing a copied
  template.

Everything else falls through to `nameserver`, the `1.1.1.1`/`8.8.8.8` DoH
pair with `#RULES`: the queries follow the routing rules and leave through
the proxy (the DNS server address itself matches `MATCH,FINAL`), so proxied
domains cannot be poisoned.  Node hostnames resolve through
`proxy-server-nameserver` (domestic DoH, direct - routing it through the
proxy would loop).

On Debian/Ubuntu cloud images systemd-resolved owns `127.0.0.53:53` (the
kernel refuses to bind mihomo's wildcard `0.0.0.0:53` next to it - mihomo
logs `Start DNS server error` and keeps running) and manages
`/etc/resolv.conf` through a symlink into `/run`.  The role stops/disables
the service (`mihomo_client_dns_manage_resolved`) and replaces the symlink
with a static `nameserver 127.0.0.1` (`mihomo_client_dns_manage_resolv_conf`,
kept separate for environments where the file is not writable, e.g. a bind
mount), so local resolution goes through the mihomo DNS module.  Hosts
without systemd-resolved are left untouched.

### Data files

`BundleMRS.7z` is resolved with `ak1ra_lab.general.github_releases_info`
only when the destination is missing (or `*_force` is set), and downloaded
with the asset digest as the checksum; an explicit
`mihomo_client_bundle_src` (controller-local file or URL) skips the release
lookup entirely.  mihomo extracts each `path-in-bundle` member from the
bundle on first use (e.g. `geo/geosite/steam@cn.mrs`), so no GeoIP/GeoSite
data file is involved.

## Customizing the profile

1. Copy `templates/etc/mihomo/config.yaml.j2` (e.g. into
   `templates/mihomo-custom.yaml.j2` next to the playbook).
2. Edit the static YAML: change a region regex, add a proxy group, change
   the DNS servers, add raw rules, ...
3. Point `mihomo_client_config_template` at the copy.  The rendered result
   is validated with `mihomo -t` before the service is (re)started.

## When every node is unavailable

The default path carries no group-level escape hatch: `PROXY` starts on the
explicitly pinned `🚀 所有节点`, and a node set that is present but dead
fails closed (connections fail, and the foreign DoH `#RULES` pair has no
path either) instead of leaking traffic direct.  Two operational escape
hatches remain:

- select `DIRECT` in the dashboard - `PROXY`, `FINAL`, the application
  groups and `SSH` carry it as a member for exactly this case (switching
  `PROXY` covers every rule that targets it, and the DNS `#RULES` pair
  follows);
- `systemctl stop mihomo` - TUN mode owns its interception state (the TUN
  device, the table-2022 routes and the `inet mihomo` nftables table holding
  auto-redirect + dns-hijack), so stopping the service restores the normal
  route for the host and the LAN.  The resolver is not restored by a plain
  stop though: `/etc/resolv.conf` still points at `127.0.0.1` and
  systemd-resolved stays disabled (`mihomo_client_state: absent` restores
  both), so the host and gateway-DNS clients need a resolver until then.  A
  hard `SIGKILL` cannot run the nftables cleanup; `nft delete table inet
  mihomo` removes a leftover table.

Group emptiness is a separate, softer case: mihomo's default
`empty-fallback` (`COMPATIBLE`, documented as equivalent to `DIRECT`) makes
a selected group whose filter resolves to no member behave like a direct
connection, so a lapsed subscription degrades to direct instead of
black-holing.

## Variable contract

| Variable | Default | Description |
| --- | --- | --- |
| `mihomo_client_state` | `present` | `present` applies, `absent` tears the role-managed artifacts down |
| `mihomo_client_mode` | `gateway` | `gateway` deploys the LAN sysctl drop-in; `local` removes it again (host-only shape) |
| `mihomo_client_config_template` | `etc/mihomo/config.yaml.j2` | Profile template to render (point at a copy to customize) |
| `mihomo_client_mixed_port` | `7890` | HTTP/SOCKS mixed port |
| `mihomo_client_api_secret` | `""` | Clash API secret; generated with `random_password` when empty and persisted to `mihomo_client_host_vars_file` (an explicit value wins; the controller listens on `0.0.0.0:9090`) |
| `mihomo_client_external_ui_url` | `""` | Optional dashboard archive URL, fetched by mihomo into `external-ui` (`ui`) at startup |
| `mihomo_client_dns_manage_resolved` | `true` | Stop/disable systemd-resolved when present (frees `127.0.0.53:53`) |
| `mihomo_client_dns_manage_resolv_conf` | `true` | Replace `/etc/resolv.conf` with `nameserver 127.0.0.1` (a symlink is removed, not written through) |
| `mihomo_client_proxy_providers` | `{}` | Airport subscriptions keyed by name (http paths can be derived; `selfhost` is reserved) |
| `mihomo_client_selfhost_proxies` | `[]` | Inline clash nodes for `providers/selfhost.yaml` |
| `mihomo_client_selfhost_files` | `[]` | Controller-local `mihomo_server` artifacts merged after the inline nodes (relative paths resolve against the role/playbook directories; anchor with `{{ playbook_dir }}`) |
| `mihomo_client_custom_*_payload` | `[]` | Inline custom rule-set payloads (see the table above); empty keeps the set out of the profile |
| `mihomo_client_custom_internal_nameservers` | `[]` | Internal resolvers for `custom-internal-rule-set` (required when its payload is set) |
| `mihomo_client_data_repo` | `MetaCubeX/meta-rules-dat` | Release repository of the rule-set bundle |
| `mihomo_client_bundle_src` | `""` | Rule-set bundle source: controller-local path (copy) or `http(s)`/`ftp` URL (get_url); takes precedence over the release download |
| `mihomo_client_bundle_asset` | `BundleMRS.7z` | Release asset name |
| `mihomo_client_bundle_force` | `false` | Re-download the bundle on every run |
| `mihomo_client_local_artifacts_dir` | `""` | When set, also render `<dir>/<host>.config.yaml` on the controller (backup/diff); empty disables |
| `mihomo_client_host_vars_file` | `<playbook>/host_vars/<host>/mihomo_client.yaml` | Controller-local generated-credentials file (0600; auto-loaded on later runs when playbook-adjacent) |
| `mihomo_client_sysctl_ip_forward` / `_rp_filter` | `true` / `false` | Gateway-mode sysctl values (booleans map to 1/0; `rp_filter` is off by default because strict reverse-path filtering drops the asymmetric proxy path) |

At least one of `mihomo_client_proxy_providers`,
`mihomo_client_selfhost_proxies` and `mihomo_client_selfhost_files` must be
non-empty when `state=present`.

The service identity and paths (`mihomo_client_user` / `_group` / `_etc_dir`
/ `_binary`, the same names on `mihomo_server`) and internal derived values
(role-owned file names, enumeration lists) live in `vars/main.yaml` as role
conventions - override them with role params or `-e` if they really must
differ.  The release lookups authenticate with the controller's
`GITHUB_TOKEN` environment variable when present (rate limits); there is no
variable - export `GITHUB_TOKEN` for the playbook run.

## Example playbook

The supported entry point is the collection playbook, which installs the
binary first and then applies this role:

```shell
ansible-playbook ak1ra_lab.network.mihomo_client -e mihomo_install_version=latest
```

Applying the roles directly (install first, as the playbook does):

```yaml
- name: mihomo TUN transparent gateway
  hosts: tproxy-gateway-01
  become: true
  gather_facts: true
  roles:
    - role: ak1ra_lab.network.mihomo_install
      vars:
        mihomo_install_restart_handler: systemctl restart mihomo.service
    - role: ak1ra_lab.network.mihomo_client
      vars:
        mihomo_client_mode: gateway
        # The Clash API secret is generated and persisted to host_vars when
        # omitted; set it explicitly (vault / uncommitted group_vars) to pin
        # a value.
        # Secrets stay out of the repository.
        mihomo_client_proxy_providers:
          airport-a:
            type: http
            url: "https://sub.example/api/v1/client/subscribe?token=..."
            proxy: DIRECT
            interval: 86400
            health-check:
              enable: true
              url: "https://www.gstatic.com/generate_204"
              interval: 300
        mihomo_client_selfhost_files:
          - "{{ playbook_dir }}/../config/client_outbounds/node01.proxies.yaml"
        mihomo_client_selfhost_proxies:
          - name: selfhost-US-molecule-node01-ss
            type: ss
            server: 203.0.113.10
            port: 8388
            cipher: 2022-blake3-aes-128-gcm
            password: "..."
            udp: true
        mihomo_client_custom_proxied_rule_set_payload:
          - force-via-proxy.example
```

## Declarative teardown: `mihomo_client_state: absent`

Removed: the profile, the role-managed selfhost provider, the unit, the
`tun` modules-load entry and the gateway sysctl drop-in (the runtime sysctl
values stay until reboot).

Restored: systemd-resolved is re-enabled and started, and `/etc/resolv.conf`
goes back to the distro stub symlink (`mihomo_client_dns_manage_resolved` /
`mihomo_client_dns_manage_resolv_conf`).  The takeover is only reversible
where systemd-resolved exists - a custom `/etc/resolv.conf` content that
predates the deploy is not restored.

Deliberately left in place: the binary, the subscription/provider data under
`/etc/mihomo/providers/`, `cache.db`, the downloaded `BundleMRS.7z` /
`rules/` extraction cache, the runtime ip rules/routes (mihomo removes
those when it stops) and the controller-local credentials artifact
(`host_vars/<host>/mihomo_client.yaml`) - remove it manually when the secret
is no longer needed.

## Companion roles

- `ak1ra_lab.network.mihomo_install` deploys the binary (applied by
  `playbooks/mihomo_client.yaml`);
- `ak1ra_lab.network.mihomo_server` generates the VPS-side listeners and the
  clash-format client nodes consumed through `mihomo_client_selfhost_files`;
- `ak1ra_lab.network.tproxy` is the TPROXY plumbing for engines that need it
  (sing-box, ...) - this role intentionally does not use it.
