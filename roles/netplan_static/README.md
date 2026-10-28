# ak1ra_lab.network.netplan_static

Captures the live IPv4 state of the physical ethernet interfaces into a
static netplan file, optionally takes the interface configuration away from
cloud-init, and applies the result.

This role is a **narrow capture/policy layer**, not an Ansible abstraction of
the whole netplan schema. It handles the common cloud-image VM shape:

- physical ethernet interfaces matched by MAC with `set-name`;
- one primary IPv4 address plus `ipv4_secondaries` per interface;
- one default gateway on the interface that currently carries the default
  IPv4 route;
- optional nameservers on that interface;
- optional per-interface address overrides.

Bonds, bridges, VLANs, policy routing, multiple default routes, MTU tuning and
other advanced netplan features belong in a copied template
(`netplan_static_config_template`) or a dedicated role.

## Requirements

- A systemd-based Debian/Ubuntu host with `netplan.io` (the role installs it
  when missing) and a live IPv4 default route.
- The selected interfaces must be physical ethernet interfaces (`type:
  ether`) with a MAC address.
- The role is IPv4-only. It fails closed when a default IPv6 route or a global
  IPv6 address exists on a selected interface unless
  `netplan_static_allow_ipv6_loss: true` is set explicitly.
- The host's network path can change: keep console/out-of-band access for the
  first run and review the gateway/DNS overrides.

## What it deploys

| Artifact | Purpose |
| --- | --- |
| `/etc/netplan/90-ansible-static.yaml` | Role-rendered static netplan configuration (mode `0600`). |
| `/var/lib/ansible/ak1ra_lab/network/netplan_static/etc/netplan/50-cloud-init.yaml` | Pre-takeover backup of cloud-init's netplan file. |
| `/etc/netplan/50-cloud-init.yaml` | Removed after the backup when `netplan_static_takeover_cloud_init: true`. |

The role also runs `netplan generate` after every change and `netplan apply`
unless `netplan_static_apply: false`.

## Variable contract

| Variable | Default | Description |
| --- | --- | --- |
| `netplan_static_state` | `present` | `present` renders/applies; `absent` restores the cloud-init backup (when present) and removes the role file. |
| `netplan_static_config_file` | `/etc/netplan/90-ansible-static.yaml` | Role-owned netplan file; must be a distinct `/etc/netplan/*.yaml` path. |
| `netplan_static_config_template` | `""` | Optional custom template. Empty uses the shipped capture template; the template receives `_netplan_static_interfaces`. |
| `netplan_static_takeover_cloud_init` | `true` | Back up and remove `50-cloud-init.yaml`; requires the cloud-init network drop-in by default. |
| `netplan_static_cloud_init_file` | `/etc/netplan/50-cloud-init.yaml` | cloud-init's generated netplan file. |
| `netplan_static_backup_dir` | `/var/lib/ansible/ak1ra_lab/network/netplan_static` | Backup root; the absolute source path is mirrored below it. The first backup wins. |
| `netplan_static_allow_absent_without_backup` | `false` | Allow `state: absent` to remove the role file without a restoreable backup. |
| `netplan_static_apply` | `true` | Run `netplan apply`; `false` only runs `netplan generate` (container tests). |
| `netplan_static_conflict_check` | `overlap` | Merge-aware conflict policy: `strict`, `overlap` or `none` (see below). |
| `netplan_static_gateway` | live default gateway | Default route on the current default interface; empty renders no default route. |
| `netplan_static_nameservers` | `[]` | Optional plain IPv4 resolvers rendered on the default interface. |
| `netplan_static_addresses` | `{}` | Per-interface CIDR overrides; a listed interface uses exactly this list instead of the captured primary + secondaries. |
| `netplan_static_allow_ipv6_loss` | `false` | Explicitly accept that the static IPv4 configuration drops existing IPv6 addresses/routes. |
| `netplan_static_require_cloud_init_disabled` | `true` | Require a `network: {config: disabled}` drop-in before removing cloud-init's netplan file. |

### Address overrides and multiple IPs

Netplan's `addresses` is a CIDR list, and the role captures the primary IPv4
address plus every `ipv4_secondaries` entry. Use an override when the live
address/prefix is wrong or a secondary address must be pinned:

```yaml
netplan_static_addresses:
  enp0s17:
    - 172.16.0.42/24
    - 172.16.1.42/24
```

An override replaces the captured list for that interface exactly. It also
covers the "the original netmask is wrong" case without a separate scalar
prefix variable.

## Netplan merge semantics and conflict policy

Netplan is a multi-file merge system, not an "one interface, one file" system.
It reads `/{lib,etc,run}/netplan/*.yaml` and processes them in lexicographic
filename order:

- a later file **amends** new mapping keys and **overrides** the same mapping
  keys;
- scalar values are replaced;
- list values (`addresses`, `routes`, `nameservers.addresses`, ...) are
  replaced wholesale, not concatenated;
- a same-named file in `/run/netplan` shadows `/etc/netplan`, which shadows
  `/lib/netplan`.

Therefore, another file that defines the same interface is not automatically
a conflict. A complementary split is valid:

```yaml
# 10-mtu.yaml
network:
  ethernets:
    eth0:
      mtu: 9000
```

The role file at `90-ansible-static.yaml` then contributes the addresses,
gateway and DNS, and the merged result keeps `mtu: 9000`.

`netplan_static_conflict_check` controls how strictly the role treats other
files:

| Value | Behavior |
| --- | --- |
| `overlap` (default) | Merge-aware. Fail when a later file sets a key the role owns, when a file claims the same device under a different ID, or when a same-named `/run/netplan` file shadows the role file. Warn when an earlier file sets a key the role shadows. Allow complementary keys. |
| `strict` | Any other file defining a managed interface is a hard conflict. Use when this role must have exclusive ownership of the interface. |
| `none` | Do not inspect other netplan files. |

The generated file uses current netplan syntax: `dhcp4` / `dhcp6` (not
deprecated), `addresses`, `routes` with `to: default`, `nameservers.addresses`
and `accept-ra`. It never writes the deprecated `gateway4` / `gateway6` keys.

The conflict key paths are `match`, `set-name`, `dhcp4`, `dhcp6`,
`accept-ra`, `addresses`, and - when configured - `routes`,
`nameservers.addresses`, plus the legacy `gateway4` / `gateway6` keys. The
legacy gateway keys are not generated by the role; they are included only
because a foreign file using them can collide with the role's modern default
route in `routes`. Keys such as `mtu`, `optional`, `wakeonlan`, `link-local`
and `nameservers.search` are complementary.

Real conflicts include:

- a later file sets `addresses`, `routes`, `dhcp4`, ... (it overrides the role);
- a different interface ID matches the same device by `match.name`,
  `match.macaddress` or `set-name`;
- a same-named file in `/run/netplan` shadows the role file completely.

An earlier file that sets a managed key is only shadowed by the role file; the
role warns instead of failing so the operator can clean it up or move it to a
complementary file. `addresses` and `routes` are lists, so "splitting" those
across files does not merge them - the later list wins.

## Taking over from cloud-init

Apply `cloud_init` first so cloud-init will not regenerate its netplan file on
the next boot:

```yaml
- hosts: cloud-image-vms
  become: true
  gather_facts: true
  tasks:
    - import_role:
        name: ak1ra_lab.network.cloud_init
      vars:
        cloud_init_network: disabled
        cloud_init_ssh_deletekeys: false
    - import_role:
        name: ak1ra_lab.network.netplan_static
      vars:
        netplan_static_gateway: 172.16.0.240
        netplan_static_nameservers:
          - 172.16.0.240
```

The role backs up `50-cloud-init.yaml` to
`/var/lib/ansible/ak1ra_lab/network/netplan_static/etc/netplan/50-cloud-init.yaml`
before removing it. The backup is the pre-takeover file, so it remains useful
for an immediate rollback even after cloud-init has been re-enabled. The path
is fixed and the first backup wins; it is a rollback snapshot, not a
timestamped backup history.

## Handing the network back to cloud-init

cloud-init regenerates `50-cloud-init.yaml` on the next boot when its network
configuration is enabled; the file is not persistent across reboots. The role
still keeps a backup because relying on regeneration alone is not safe for an
immediate rollback.

Recommended order:

```text
1. cloud_init:     cloud_init_network=managed
2. netplan_static: state=absent
3. reboot (optional; cloud-init can regenerate 50-cloud-init.yaml)
```

`netplan_static_state: absent` restores the backup to `50-cloud-init.yaml`,
removes the role file and runs the netplan handlers. Without a backup it
refuses to remove the role file unless
`netplan_static_allow_absent_without_backup: true`; in that case make sure
cloud-init is enabled and reboot so it can regenerate its file.

## Declarative teardown: `netplan_static_state: absent`

Removes only the role-owned netplan file and restores the cloud-init backup.
It does **not** remove cloud-init's network disable drop-in; that belongs to
`ak1ra_lab.network.cloud_init`. It also leaves the backup directory in place.

## Custom template escape hatch

For features outside the capture model, copy
`templates/etc/netplan/90-ansible-static.yaml.j2`, edit the copy, and point
`netplan_static_config_template` at it. The role still owns the file mode,
conflict preflight, cloud-init backup/removal and the `netplan generate/apply`
handlers. The normalized interface data is available as
`_netplan_static_interfaces`:

```yaml
- name: enp0s17
  macaddress: "52:54:00:00:00:01"
  addresses:
    - 172.16.0.42/24
```

## Limitations

- IPv4 only; IPv6 fails closed unless explicitly accepted.
- One default route; advanced routing uses a custom template.
- Netplan conflict detection scans `/lib/netplan`, `/usr/lib/netplan`,
  `/etc/netplan` and `/run/netplan`, but it does not inspect hand-written
  `/etc/systemd/network` files, bridge/bond membership, or device matches by
  driver/path.
- Complementary split files are allowed in `overlap` mode, but list-valued
  keys are still replaced wholesale by the later file. Do not split
  `addresses`, `routes` or `nameservers.addresses` across files and expect
  concatenation.
- DHCP addresses are captured as static addresses. Make sure the address is
  reserved or outside the DHCP pool before taking it over.
- The role assumes netplan's `networkd` renderer, matching the cloud images it
  targets.
