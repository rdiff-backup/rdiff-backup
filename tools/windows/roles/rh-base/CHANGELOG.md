# Change log

This file contains al notable changes to the bertvv.rh-base Ansible role. This file adheres to the guidelines of [http://keepachangelog.com/](http://keepachangelog.com/). Versioning follows [Semantic Versioning](http://semver.org/).

## 3.0.0 - 2019-10-16

### Added

- (GH-12) Dynamic Message of the Day (credit: @TimCaudron)
- (GH-11, GH-13) Support for automatic updates (credit: @BrechtClaeys and @JensVanDeynse1994)
- (GH-16) Set AllowGroups in sshd config

### Changed

- (GH-10) Update vars-CentOS.yml (credit: @MichaelLeeHobbs)
- (GH-14) Ensure all groups specified in `rhbase_users` exist, even if not added to `rhbase_groups` (credit: @T0MASD)
- Set SELinux booleans when appropriate, i.e. when SELinux state is either permissive or enforcing.
- Fix coding style using Yamllint

### Removed

- `rhbase_motd`, superseded by `rhbase_dynamic_motd`. **Breaking change***: old playbooks will still work, but the role's behaviour is changed (no custom MOTD will be generated).

## 2.3.0 - 2017-11-14

### Added

- (GH-8) Variable `rhbase_selinux_booleans` (credit: @SebaNuss)

### Changed

- (GH-7) Updated documentation for generating password hashes
- Fix Ansible 2.4 deprecation warnings

## 2.2.0 - 2017-09-28

### Added

- (GH-5) Variable `rhbase_tz` sets the TZ environment variable to save system calls

### Changed

- Give keys of the `rhbase_users` variable default values. Only user name is required. See the <README.md> for details.
- Upgrade base boxes to latest versions: CentOS 7.4 and Fedora 26
- (GH-6) Ensure /var/log/journal/ exists so the system can keep persistent logs

## 2.1.0 - 2016-11-24

### Added

- Variable `rhbase_firewall_interfaces` can now be used to add a network interface to the public zone.

### Changed

- The role now ensures essential systemd services (e.g. journald, tmpfiles) are running. The difference with previous version is that two services were added and they are now enumerated in a variable.

## 2.0.0 - 2016-10-30

### Added

- Added ‘exclude=’ option to `/etc/dnf.conf` and `/etc/yum.conf` and the variable `rhbase_repo_exclude_from_updates`
- Added task that creates `/etc/machine-id` if necessary. When this file is not set up correctly (with `systemd-machine-id-setup`), `systemd-journald` cannot run.

### Changed

- (RH-2) Renamed variables `rhbase_admin_user` to `rhbase_ssh_user` and `rhbase_admin_ssh_key` to `rhbase_ssh_key`. The previous names were confusing, as the role did nothing special to make this user an admin (i.e. member of `wheel`). This is a breaking change, hence the major version bump.
- Added `firewalld` to the list of packages to be installed as dependencies

## 1.0.2 - 2016-09-20

Bugfix release

### Changed

- Fixed tag names in tasks

## 1.0.1 - 2016-09-21

Bugfix release

### Changed

- Added handler to restart the firewall daemon
- Added forgotten role tag to a task

## 1.0.0 - 2016-06-08

First release!

### Added

- Functionality from roles [bertvv.el7](https://galaxy.ansible.com/bertvv/el7) and [bertvv.fedora](https://galaxy.ansible.com/bertvv/fedora).

