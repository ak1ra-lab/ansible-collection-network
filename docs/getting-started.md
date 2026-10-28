# Getting started

## Install the collection

```shell
ansible-galaxy collection install git+https://github.com/ak1ra-lab/ansible-collection-network.git
```

The `mihomo_*` roles also need `ak1ra_lab.general`, which is not published to
Galaxy yet. Add it to the consuming repository's `requirements.yaml` and
install from git:

```yaml
collections:
  - name: git+https://github.com/ak1ra-lab/ansible-collection-general.git
    version: master
```

For development in this repository, `just ansible-collection-install` installs
the collection under test plus the local `../ansible-collection-general`
checkout into `.ansible/collections`. Override the path with
`GENERAL_COLLECTION=/path/to/checkout` when working from a git worktree.

## Control-node requirements

- `ansible-core >= 2.18` (`meta/runtime.yml`).
- `ansible.utils >= 6.0.0` (a `galaxy.yml` dependency) for the `ipaddr` and
  `in_network` filters used by the `systemd_bridge` and `systemd_netns` roles.
- `netaddr` for the `ansible.utils.ipaddr` filter:

  ```shell
  ansible-galaxy collection install ansible.utils
  python -m pip install netaddr
  ```

- `ak1ra_lab.general` for the `mihomo_install`, `mihomo_client`, and
  `mihomo_server` roles (`github_releases_info` and `cpu_info`). The optional
  certbot orchestration in `mihomo_server` also needs the
  `ak1ra_lab.general.certbot` role (general >= 0.3.0).

The development environment uses `uv`; `just ansible-collection-install`
installs the collection under test and the local general checkout, and
`just ansible-requirements-install` installs the Molecule and lint
collections from `requirements.yaml`.

## Managed-node requirements

The roles target systemd-based Linux. The Molecule images used by this
repository are:

- `debian:12`
- `debian:13`
- `ubuntu:24.04`
- `ubuntu:26.04`

The `systemd_bridge` and `systemd_netns` roles require `systemd-networkd`,
which is not available on the RHEL family. Fedora would additionally need the
separate `systemd-networkd` package and the `iproute` package name.

Role-specific requirements:

- `systemd_bridge`: root privileges; dedicated physical interfaces that are
  not managed by netplan, ifupdown, or another NetworkManager profile.
- `systemd_netns`: root privileges; an existing bridge with at least one
  enslaved member interface; `iproute2`.
- `cloud_init`: root privileges; a Debian/Ubuntu cloud image with cloud-init
  installed. The role only writes drop-ins under `/etc/cloud/cloud.cfg.d`.
- `netplan_static`: root privileges; `netplan.io`, a live IPv4 default route
  in the kernel main table, and physical ethernet interfaces. TUN defaults
  such as `mihomo0` are ignored; select the underlay interface explicitly when
  the main table is ambiguous. It is IPv4-only and needs console or
  out-of-band access because it can change the host's network path.
- `systemd_resolved`: root privileges; the `systemd-resolved` package. The
  role must be the only owner of `/etc/resolv.conf` on the host.
- `tproxy`: root privileges; nftables and the kernel modules the role loads
  (`nft_tproxy`, `nf_conntrack`, `tcp_bbr`, ...).
- `mihomo_client`: a writable `/dev/net/tun`, the `tun` module, and kernel
  nftables support for the default TUN `auto-redirect`. Debian and Ubuntu
  stock kernels provide it; kernels without it need `DISABLE_NFTABLES=true`
  plus `iptables` through a unit drop-in.
- `mihomo_server`: root privileges; TLS material for the certificate-using
  listeners, either managed manually or copied from an external source.
- `mihomo_install`: a writable `/usr/local/bin` and `gzip`; the archive is a
  statically linked binary, so no package manager is involved.

## First playbooks

```shell
ansible-playbook ak1ra_lab.network.systemd_bridge \
  -e systemd_bridge_bridges='[{"name": "br_wan", "interface": "enp36s0"}]'

ansible-playbook ak1ra_lab.network.systemd_netns \
  -e systemd_netns_name=qbittorrent

ansible-playbook ak1ra_lab.network.cloud_init \
  -e playbook_hosts=cloud-image-vms

ansible-playbook ak1ra_lab.network.netplan_static \
  -e playbook_hosts=cloud-image-vms

ansible-playbook ak1ra_lab.network.systemd_resolved \
  -e playbook_hosts=cloud-image-vms

ansible-playbook ak1ra_lab.network.mihomo_client \
  -e mihomo_install_version=latest

ansible-playbook ak1ra_lab.network.mihomo_server \
  -e mihomo_install_version=latest
```

The playbooks default to the `mihomo-client`, `mihomo-server`,
`cloud-image-vms`, or `localhost` inventory groups; override the target with
`playbook_hosts`. The role variable contracts are documented in the
individual role READMEs.
