# ak1ra_lab.network.mihomo_client

> The canonical variable reference is generated from
> [`meta/argument_specs.yml`](meta/argument_specs.yml) in the
> [collection documentation](https://ak1ra-lab.github.io/ansible-collection-network/collection_index.html).
> This README keeps purpose, requirements, deployed artifacts,
> profile behavior, examples, and operational notes.

Deploys [mihomo](https://github.com/MetaCubeX/mihomo) as a TUN
transparent-proxy client, based on the hand-written
[mihomo-setup](https://github.com/ak1ra-lab/mihomo-setup) deployment:

- the TUN inbound (`auto-route` + `auto-redirect` + `auto-detect-interface`
  + `dns-hijack`) captures both local and LAN-forwarded traffic, so a LAN
  client only needs this host as its gateway/DNS - no nftables marking, no
  policy-routing service and no `ak1ra_lab.network.tproxy` dependency;
- the profiles are hand-maintained templates (static mihomo YAML plus a
  handful of rendered values): top-level selectors (`PROXY` / `FINAL` /
  application / `SSH`) over per-region selector / url-test tiers (plus the
  optional self-hosted tier for chain-proxy deployments), an explicit
  `default-selected` on `PROXY` and `DIRECT` escape hatches in the top-level
  members;
- DNS stays `redir-host` (real answers) with a static rule-set split:
  `nameserver-policy` sends the direct-routed domain sets to domestic DoH,
  the custom internal set to its own resolvers, and everything else leaves
  through the foreign DoH `#RULES` pair - no `fallback`/`fallback-filter`,
  no GeoIP/GeoSite data file;
- providers are hot-reloaded: overwriting `providers/*.yaml` does not
  restart the service; only `config.yaml` changes do.

The role owns the service identity (`mihomo` user/group), the profile, the
systemd unit and the service.  It does **not** install the binary: the
consumer composition in `ansible-playbooks-services` applies
`ak1ra_lab.network.mihomo_install` before this role, and the role only
asserts that the binary exists.  It also provisions the data file the profile
depends on (`BundleMRS.7z`, resolved from the MetaCubeX/meta-rules-dat
release and verified with the GitHub asset digest).

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
  `/etc/resolv.conf` (see [DNS](#dns)).
- For gateway mode the host must be the LAN's gateway (or be advertised as
  one); the role only sets `net.ipv4.ip_forward=1` and
  `net.ipv4.conf.all.rp_filter=0`.  Switching back to local mode removes the
  drop-in, but the runtime sysctl values stay in effect until reboot.
- Control node: `ak1ra_lab.general` (>= 0.4.0) for `github_releases_info`;
  Galaxy resolves it from the collection dependencies.

## What it deploys

| Artifact | Purpose |
| --- | --- |
| `/usr/local/bin/mihomo` | mihomo binary, deployed by `mihomo_install` (consumer playbook) |
| `/etc/mihomo/config.yaml` | the rendered profile (`mihomo_client_config_template`) |
| `/etc/mihomo/providers/selfhost.yaml` | self-hosted nodes (inline + `mihomo_server` artifacts), mode 0640 |
| `/etc/mihomo/providers/` | airport subscription caches (role-created directory, contents user-managed) |
| `/etc/mihomo/BundleMRS.7z` | rule-set bundle, the mandatory data file (release download or explicit `*_src` file/URL) |
| `/etc/systemd/system/mihomo.service` | service unit (`ExecStartPre` config test, capabilities for TUN + :53) |
| `/etc/resolv.conf` | static `nameserver 127.0.0.1` while deployed (`mihomo_client_dns_manage_resolv_conf`); teardown restores the distro stub symlink |
| `/etc/modules-load.d/ansible-mihomo-client.conf` | `tun` module at boot |
| `/etc/sysctl.d/90-ansible-mihomo-client-gateway.conf` | `ip_forward` / `rp_filter` (gateway mode only) |
| `<local artifacts dir>/<host>.config.yaml` | optional controller-local profile mirror (`mihomo_client_local_artifacts_dir`) |
| `inventory/host_vars/<host>/mihomo_client.yaml` (or the configured `mihomo_client_host_vars_file`) | generated Clash API secret (0600, auto-loaded on later runs) |

## How it works

`tasks/present.yml` ensures the service identity, asserts the binary
deployed by `mihomo_install`, fetches the data file, generates the Clash
API secret (persisted to host_vars) when it was not provided, renders the
profile and the selfhost provider, frees the resolver port
(`systemd-resolved`) and takes over `/etc/resolv.conf` before the service
starts, persists the `tun` module, applies (or removes) the gateway sysctl
drop-in, then validates the config with `mihomo -t -d /etc/mihomo` before
enabling and starting the service.  The service unit runs the same config
test as `ExecStartPre`, and `Restart=on-failure` recovers from a crashed
engine.

## Profile templates

`mihomo_client_config_template` is rendered to `/etc/mihomo/config.yaml`.
Two hand-maintained templates ship:

- `templates/etc/mihomo/config.yaml.j2` - the default plain profile
  (`mihomo_client_selfhost_tier: false`).  Two tiers per region; self-hosted
  nodes are matched by the same region filters and merged into the normal
  selector / url-test groups, so there is no separate `*-自建` tier.
- `templates/etc/mihomo/config.selfhost.yaml.j2` - the selfhost-tier profile
  (`mihomo_client_selfhost_tier: true`).  Three tiers per region; the
  self-hosted nodes stay in their own tier, which is what chain-proxy
  deployments need when a direct and a chained variant of the same node must
  coexist.  The self-hosted tier only covers US/SG/JP; self-hosted nodes in
  any other region remain in `🚀 所有节点 - 自建`.

Both files are hand-maintained: the group topology, rule providers, rules and
DNS split are plain mihomo YAML in those files, and only the necessary values
are rendered into them - the mixed port, the API secret, the optional
dashboard URL, the provider mapping and the custom rule-set payloads.
Anything else (a different listen port, extra regions, different DNS
servers, ...) is a template edit: copy the file, adjust it and point the
variable at the copy.

The plain topology (19 groups) uses five regions (SG/HK/TW/JP/US) plus the
`🚀 所有节点` catch-all: `<region>` selects from the full pool matching the
region regex, `<region> - AUTO` is a url-test over the same pool (`interval`
300, `tolerance` 50), and `🚀 所有节点` / `🚀 所有节点 - AUTO` cover the
full pool.  The selfhost topology (23 groups) keeps the same five region
tiers with self-hosted nodes excluded, adds `*-自建` selectors for US/SG/JP
(nodes carrying both the `selfhost|自建` tag and the region token), and a
`🚀 所有节点 - 自建` catch-all for every tagged node.

`PROXY` lists the available tiers plus `DIRECT`, and pins
`default-selected: 🚀 所有节点` - the default path is explicit and the
latency AUTO tier is only a manual choice.  `FINAL` and the application
groups (`AI`, `Steam`, `Telegram`, `Entertainment`) follow the same tier list
with `PROXY` / `DIRECT` on top; `SSH` leads with `PROXY` / `DIRECT`.  No
group-level fallback exists: a node set that is present but dead fails
closed, and the escape hatch is selecting `DIRECT` (or stopping the service).

### Custom rule sets

The profile pre-fills eight inline rule providers; each one (and its rule)
only exists when the matching `mihomo_client_custom_*_payload` list is
non-empty:

- `custom-internal-rule-set` -> `DIRECT` and the internal resolvers
  (`mihomo_client_custom_internal_nameservers`; set both together, the play
  fails otherwise);
- `custom-rejected-rule-set` and `custom-rejected-rule-set-ip` -> `REJECT`;
- `custom-direct-rule-set` and `custom-direct-rule-set-ip` -> `DIRECT` (the
  domain set resolves through the domestic DoH pair);
- `custom-proxied-rule-set` and `custom-proxied-rule-set-ip` -> `PROXY`.

Domain sets take clash wildcard domains (`ads.example` matches exactly,
`.ads.example` the subdomains, `+.ads.example` both), the `*_ip` sets take
CIDRs (`10.20.0.0/16`).  The two lists are separate because mihomo's
rule-set `behavior` is the payload type, not a hint: `dns.nameserver-policy`
rejects an `ipcidr` rule-set at config load ("rule provider type error,
expect domain") and accepts a `classical` set only with a warning that just
its domain rules are matched, so the internal/direct domain sets stay
`domain` behavior.  The custom rules render before the geo rules, so they
override them; the internal set routes its domains `DIRECT` and resolves
them through the internal nameservers, while the direct set resolves through
the domestic DoH pair, mirroring its route.  Arbitrary rule syntax
(`PROCESS-NAME`, ...) belongs in a copied template's `rules:` block.

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
and a region token (the region regexes live in the profile templates, so
they match at load time).  In the plain profile the region token merges the
node into the normal region groups; in the selfhost profile the tag
additionally selects the `*-自建` tier.  At least one node source must exist,
otherwise the role fails the play.

For a chain-proxy deployment, set `mihomo_client_selfhost_tier: true` and
declare `dialer-proxy` on the self-hosted node entries (inline or in the
files named by `mihomo_client_selfhost_files`).  The target can be a region
selector or its `- AUTO` group; the selector gives a predictable path while
AUTO follows the airport latency.  SS nodes are the safe baseline for
chaining: UDP-based protocols (hysteria2, tuic) and TLS-camouflage protocols
(VLESS REALITY, AnyTLS) may not relay through an airport node.

## DNS

The DNS split is static in the profile templates and rule-set based.
`nameserver-policy` (evaluated first) routes the direct-routed domain sets
to the domestic DoH pair:

- `geosite-private` - router portals (`tplogin.cn`, ...), special-use
  domains (`.lan`, `.home.arpa`, ...), private PTR zones and local-service
  names (`.ts.net`, ...).  Public DoH neither resolves nor should see
  those, so point the entry at the internal resolver where one exists by
  editing the template (e.g. `["192.168.1.1", "100.100.100.100"]`);
- `geosite-cn`;
- `geosite-steam@cn` - the Steam CDN/download domains used by the Steam
  client (`csgo.com.cn`, `dl.steam.clngaa.com`, `st.dl.bscstorage.net`,
  `alibaba.cdn.steampipe.steamcontent.com`, ...).  They route `DIRECT` and
  resolve nearby; the store/community domains stay in `geosite-steam` and
  leave through the `Steam` group;
- `custom-direct-rule-set` (only when its payload is set);
- `custom-internal-rule-set` (only when its payload and the internal
  nameservers are set) - intranet domains resolved by their own resolvers,
  e.g. `["192.168.1.1"]`.

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
the service and replaces the symlink with a static `nameserver 127.0.0.1`
(the two switches stay separate for environments where the file is not
writable, e.g. a bind mount), so local resolution goes through the mihomo
DNS module.  Hosts without systemd-resolved are left untouched.

## Data files

`BundleMRS.7z` is resolved with `ak1ra_lab.general.github_releases_info`
only when the destination is missing (or forced), and downloaded with the
asset digest as the checksum; an explicit `mihomo_client_bundle_src`
(controller-local file or URL) skips the release lookup entirely.  mihomo
extracts each `path-in-bundle` member from the bundle on first use (e.g.
`geo/geosite/steam@cn.mrs`), so no GeoIP/GeoSite data file is involved. The
release lookups authenticate with the controller's `GITHUB_TOKEN` environment
variable when present (rate limits); export it for the playbook run.

## Customizing the profile

1. Copy the closest shipped template - `templates/etc/mihomo/config.yaml.j2`
   for the plain profile or `templates/etc/mihomo/config.selfhost.yaml.j2`
   for the selfhost-tier profile (e.g. into `templates/mihomo-custom.yaml.j2`
   next to the playbook).
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

## Example playbook

The operational composition lives in `ansible-playbooks-services`
(`mihomo_client.yaml`), which installs the binary first and then applies this
role:
`https://github.com/ak1ra-lab/ansible-playbooks-services`.

Applying the roles directly (install first, as that composition does):

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
        # a value. Secrets stay out of the repository.
        mihomo_client_proxy_providers:
          airport-a:
            type: http
            url: "https://sub.example/api/v1/client/subscribe?token=..."
            proxy: DIRECT
            interval: 86400
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
goes back to the distro stub symlink.  The takeover is only reversible where
systemd-resolved exists - a custom `/etc/resolv.conf` content that predates
the deploy is not restored.

Deliberately left in place: the binary, the subscription/provider data under
`/etc/mihomo/providers/`, `cache.db`, the downloaded `BundleMRS.7z` /
`rules/` extraction cache, the runtime ip rules/routes (mihomo removes
those when it stops) and the controller-local credentials artifact
(`host_vars/<host>/mihomo_client.yaml`) - remove it manually when the secret
is no longer needed.

## Companion roles

- `ak1ra_lab.network.mihomo_install` deploys the binary (applied first by the
  consumer composition in `ansible-playbooks-services`);
- `ak1ra_lab.network.mihomo_server` generates the VPS-side listeners and the
  clash-format client nodes consumed through `mihomo_client_selfhost_files`;
- `ak1ra_lab.network.tproxy` is the TPROXY plumbing for engines that need it
  (sing-box, ...) - this role intentionally does not use it.
