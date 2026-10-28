# Playbooks

The collection ships thin playbook entry points. They set privileges, gather
facts, and orchestrate roles; the variable contracts stay in the roles.

| Playbook | Behavior |
| --- | --- |
| `ak1ra_lab.network.systemd_bridge` | Wrapper around the `systemd_bridge` role (root privileges, fact gathering). Drive it through the `systemd_bridge_*` contract. |
| `ak1ra_lab.network.systemd_netns` | Applies the host bridges declared for the run (`systemd_bridge_bridges`) first, flushes their handlers, then applies the namespace role. The `systemd_netns_*` contract drives the namespace. |
| `ak1ra_lab.network.cloud_init` | Wrapper around the `cloud_init` role (root privileges, fact gathering). The `cloud_init_*` contract drives it. |
| `ak1ra_lab.network.netplan_static` | Wrapper around the `netplan_static` role (root privileges, fact gathering). The playbook can change the network path, so target an explicit inventory group and keep console access. |
| `ak1ra_lab.network.systemd_resolved` | Wrapper around the `systemd_resolved` role (root privileges, fact gathering). The `systemd_resolved_*` contract drives it. |
| `ak1ra_lab.network.mihomo_install` | Installs or upgrades the binary only (root privileges, fact gathering). The `mihomo_install_*` contract drives it. |
| `ak1ra_lab.network.mihomo_client` | Applies `mihomo_install` first, then `mihomo_client`. A binary upgrade restarts `mihomo.service` through the client role's handler. |
| `ak1ra_lab.network.mihomo_server` | Applies `mihomo_install` first, optionally applies `ak1ra_lab.general.certbot` (`mihomo_server_tls_certbot_enabled`), then the server role. |

## Host selection

Each playbook targets a group by default and accepts `playbook_hosts` as an
override:

| Playbook | Default host group |
| --- | --- |
| `systemd_bridge` | `localhost` |
| `systemd_netns` | `localhost` |
| `cloud_init` | `cloud-image-vms` |
| `netplan_static` | `cloud-image-vms` |
| `systemd_resolved` | `cloud-image-vms` |
| `mihomo_install` | `localhost` |
| `mihomo_client` | `mihomo-client` |
| `mihomo_server` | `mihomo-server` |

## Examples

```shell
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
```

## Cloud-image network takeover

`cloud_init`, `netplan_static`, and `systemd_resolved` are independent roles;
compose them in a site playbook in that order when a cloud image should stop
letting cloud-init own its network configuration:

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
    - meta: flush_handlers
    - import_role:
        name: ak1ra_lab.network.systemd_resolved
```

`cloud_init` disables cloud-init's network ownership first, `netplan_static`
backs up and removes cloud-init's `50-cloud-init.yaml` before applying the
static file, and `systemd_resolved` configures the host resolver. Keep console
or out-of-band access for the first `netplan_static` run. Only one role may
own `/etc/resolv.conf`: `systemd_resolved` keeps resolved running, while
`mihomo_client` and `tproxy` have their own static resolver modes.

## mihomo server TLS modes

Manual TLS is the default. Set
`mihomo_server_tls_certificate_path` and `mihomo_server_tls_key_path` to a
pair readable by the `mihomo` service user. To let the playbook obtain the
lineage with `ak1ra_lab.general.certbot`, set
`mihomo_server_tls_certbot_enabled=true` and provide the normal `certbot_*`
contract (email, certificates, challenge/provider) in group or host vars.
The playbook derives the source paths from `certbot`'s `live/<lineage>`
directory and enables the role's independent renewal hook. Do not configure
`certbot_deploy_hooks` for mihomo.

The lineage defaults to `mihomo_server_hostname` (or the gathered FQDN).
Override `mihomo_server_tls_certbot_lineage` for a custom certificate name,
such as a wildcard lineage. The certificate must be present in
`certbot_certificates`.

See the [`mihomo_server` role](roles/mihomo_server.md) for the listener,
REALITY, JLS, and padding contracts.
