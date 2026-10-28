# ak1ra_lab.network.cloud_init

Manages cloud-init drop-ins under `/etc/cloud/cloud.cfg.d`. The role is
deliberately narrow: it changes cloud-init's own behavior (network ownership,
SSH host-key handling, host identity) and never touches netplan, DNS or
`/etc/resolv.conf`.

The defaults are no-ops. Applying the role without overrides leaves the
distribution's cloud-init configuration untouched; the cloud-image network
takeover explicitly opts in:

```yaml
cloud_init_network: disabled
cloud_init_network_activation: disabled   # optional extra safety layer
cloud_init_ssh_deletekeys: false
```

## Requirements

- A systemd-based Debian/Ubuntu host with cloud-init installed.
- Root privileges. The role only writes files under `/etc/cloud/cloud.cfg.d`;
  it does not install or restart cloud-init.

## What it deploys

| Artifact | Purpose |
| --- | --- |
| `/etc/cloud/cloud.cfg.d/99-ansible-network.cfg` | `network: {config: disabled}` and/or `disable_network_activation: true` |
| `/etc/cloud/cloud.cfg.d/99-ansible-ssh.cfg` | `ssh_deletekeys: false` when host keys must stay stable |
| `/etc/cloud/cloud.cfg.d/99-ansible-host.cfg` | `manage_etc_hosts: false` and/or `preserve_hostname: true` |
| `/etc/cloud/cloud.cfg.d/99-ansible-extra.cfg` | `cloud_init_extra_config`, rendered last so it can override the typed settings |

All files are `0600 root:root`. cloud-init reads every `*.cfg` in lexical
order, so the `99-` prefix wins over the distribution defaults.

## Variable contract

| Variable | Default | Description |
| --- | --- | --- |
| `cloud_init_state` | `present` | `present` applies the configured drop-ins; `absent` removes every drop-in this role manages. |
| `cloud_init_network` | `managed` | `disabled` writes `network: {config: disabled}`; `managed` removes the role drop-in and leaves cloud-init in charge. |
| `cloud_init_network_activation` | `enabled` | `disabled` writes `disable_network_activation: true`, preventing cloud-init from bringing up datasource-described interfaces. |
| `cloud_init_ssh_deletekeys` | `true` | cloud-init's upstream default; set `false` to keep `/etc/ssh/ssh_host_*` stable across cloud-init drive changes. |
| `cloud_init_manage_etc_hosts` | `true` | Set `false` to stop cloud-init from rewriting `/etc/hosts`. |
| `cloud_init_preserve_hostname` | `false` | Set `true` to stop cloud-init from changing the hostname from datasource metadata. |
| `cloud_init_extra_config` | `{}` | Extra cloud-init configuration rendered to `99-ansible-extra.cfg`; keep secrets in Vault. |
| `cloud_init_require_installed` | `true` | Fail when `/etc/cloud/cloud.cfg` is missing; set `false` only for controlled fixtures. |

## Example playbook

```yaml
- hosts: cloud-image-vms
  become: true
  gather_facts: true
  roles:
    - role: ak1ra_lab.network.cloud_init
      vars:
        cloud_init_network: disabled
        cloud_init_network_activation: disabled
        cloud_init_ssh_deletekeys: false
        cloud_init_extra_config:
          phone_home:
            url: "http://telemetry.example/instance"
```

## Declarative teardown: `cloud_init_state: absent`

Removes the four role-managed drop-ins. The cloud-init package and
`/etc/cloud/cloud.cfg.d` are left in place, so cloud-init returns to its
distribution defaults.

The network takeover is a two-role handback: re-enable cloud-init with
`cloud_init_network: managed`, and hand the netplan file back with
`ak1ra_lab.network.netplan_static` (`netplan_static_state: absent`) so both
sides release ownership in a defined order. See the `netplan_static` README
for the rollback details.
