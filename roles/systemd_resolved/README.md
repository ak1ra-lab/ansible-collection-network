# ak1ra_lab.network.systemd_resolved

Manages `systemd-resolved` as the host resolver:

- the global DNS drop-in (`DNS=`, optional `FallbackDNS=`, `Domains=`,
  `DNSOverTLS=`, `DNSStubListener=`);
- the `/etc/resolv.conf` symlink mode (`stub`, `uplink`, `static`) or leaves
  the file unmanaged;
- a backup/restore path for a pre-role regular `/etc/resolv.conf`.

The role deliberately has **no static-file mode**. Hosts that need to stop
systemd-resolved and replace `/etc/resolv.conf` with a plain file are served
by `ak1ra_lab.network.mihomo_client` (mihomo DNS listener) or
`ak1ra_lab.network.tproxy` (advisory static resolver for a transparent-proxy
gateway). A host must have exactly one owner of `/etc/resolv.conf`.

## Requirements

- systemd-based Debian/Ubuntu host; the role installs the
  `systemd-resolved` package when missing.
- Root privileges.
- Do not combine this role with `tproxy_etc_resolv_conf: true` or
  `mihomo_client_dns_manage_resolv_conf: true` unless one side is set to
  `unmanaged`/disabled.

## What it deploys

| Artifact | Purpose |
| --- | --- |
| `/etc/systemd/resolved.conf.d/90-ansible-resolved.conf` | Global DNS, FallbackDNS, Domains, DoT and stub listener settings. |
| `/etc/resolv.conf` | Symlink to the selected systemd-resolved view; `unmanaged` leaves it alone. |
| `/var/lib/ansible/ak1ra_lab/network/systemd_resolved/etc/resolv.conf` | Backup of a pre-role regular resolver file (when enabled). |

A pre-role regular resolver file is copied below `systemd_resolved_backup_dir`
with its absolute path mirrored, and the first backup wins. The path is a
fixed rollback snapshot, not a timestamped history. Symlinks are replaced in
place and do not need a backup.

## Variable contract

| Variable | Default | Description |
| --- | --- | --- |
| `systemd_resolved_state` | `present` | `present` configures and starts resolved; `absent` removes the drop-in and restores the distro stub or the pre-role backup. |
| `systemd_resolved_nameservers` | `[]` | Global DNS servers (`IP` or `IP#server-name`). Empty removes the role drop-in and leaves distro DNS untouched. |
| `systemd_resolved_fallback_nameservers` | `[]` | Optional `FallbackDNS=` entries; empty omits the key. |
| `systemd_resolved_domains` | `["~."]` | `Domains=` entries; `~.` makes the global servers the default route for unmatched queries. |
| `systemd_resolved_dns_over_tls` | `false` | `DNSOverTLS=yes`; strict DoT requires `#server-name` on every nameserver. |
| `systemd_resolved_resolv_conf_mode` | `stub` | `stub`, `uplink`, `static` or `unmanaged`. |
| `systemd_resolved_stub_listener` | `true` | `DNSStubListener=` value. |
| `systemd_resolved_resolv_conf_path` | `/etc/resolv.conf` | Path managed by the role; unusual chroots/tests may point it elsewhere. |
| `systemd_resolved_backup_dir` | `/var/lib/ansible/ak1ra_lab/network/systemd_resolved` | Backup root; the absolute resolver path is mirrored below it. The first backup wins. |
| `systemd_resolved_backup_resolv_conf` | `true` | Keep the backup before replacing a regular file. |

### `resolv.conf` modes

| Mode | Target |
| --- | --- |
| `stub` | `/run/systemd/resolve/stub-resolv.conf` (local stub, recommended) |
| `uplink` | `/run/systemd/resolve/resolv.conf` (upstream view) |
| `static` | `/usr/lib/systemd/resolv.conf` (static fallback) |
| `unmanaged` | Leave `/etc/resolv.conf` untouched; another owner manages it |

`Domains=~.` marks the global DNS servers as the default route for queries
that do not match a more specific per-link domain. Without it, a per-link
`Domains=~.` can take over the default route and the global servers are
ignored for those queries.

## Example playbook

```yaml
- hosts: cloud-image-vms
  become: true
  gather_facts: true
  roles:
    - role: ak1ra_lab.network.systemd_resolved
      vars:
        systemd_resolved_nameservers:
          - 1.1.1.1#cloudflare-dns.com
          - 8.8.4.4#dns.google
        systemd_resolved_fallback_nameservers:
          - 9.9.9.9#dns.quad9.net
        systemd_resolved_dns_over_tls: true
        systemd_resolved_resolv_conf_mode: stub
```

## Declarative teardown: `systemd_resolved_state: absent`

Removes the role drop-in and restores the resolver file:

- a pre-role regular `/etc/resolv.conf` backup wins;
- otherwise the distro stub symlink is restored;
- the package and the service are left enabled; the drop-in removal restarts
  resolved when it was running.

A custom `/etc/resolv.conf` that predates the role cannot be restored when no
backup was kept; set `systemd_resolved_backup_resolv_conf: true` (the default)
for regular files.

## Interaction with other resolver owners

| Host shape | Resolver owner |
| --- | --- |
| Normal cloud-image VM | `ak1ra_lab.network.systemd_resolved` |
| mihomo TUN gateway | `ak1ra_lab.network.mihomo_client` (stops resolved, writes `127.0.0.1`) |
| TPROXY gateway | `ak1ra_lab.network.tproxy` (`tproxy_etc_resolv_conf`) |

If `systemd_resolved_resolv_conf_mode: unmanaged` is set, the role only
manages the resolved drop-in/service and another role may own the file.
