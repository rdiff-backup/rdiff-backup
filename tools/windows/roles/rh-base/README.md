# Ansible role `rh-base`

Ansible role for basic setup of a server with a RedHat-based Linux distribution (CentOS, Fedora, RHEL, ...). Specifically, the responsibilities of this role are to:

- Manage repositories,
- Manage package installation and removal,
- Turn specified services on or off,
- Create users and groups,
- Set up an administrator account with an SSH key,
- Apply basic security settings, like turning on SELinux and the firewall,
- Manage firewall rules (in the public zone).
- Install and configure yum-cron for automatic updates

## Requirements

No specific requirements

## Role Variables

| Variable                                  | Default         | Comment                                                                                                               |
|:------------------------------------------|:----------------|:----------------------------------------------------------------------------------------------------------------------|
| `rhbase_automatic_updates`                | false           | When set, automatic updates will be configured (yum-cron or dnf-automatic, as appropriate). See `rhbase_updates_*`    |
| `rhbase_dynamic_motd`                     | false           | When set, provides a dynamic message of the day at login with system information                                      |
| `rhbase_enable_repos`                     | []              | List of dicts specifying repositories to be enabled. See below for details.                                           |
| `rhbase_firewall_allow_ports`             | []              | List of ports to be allowed to pass through the firewall, e.g. 80/tcp, 53/udp, etc.                                   |
| `rhbase_firewall_allow_services`          | []              | List of services to be allowed to pass through the firewall, e.g. http, dns, etc.(1)                                  |
| `rhbase_firewall_interfaces`              | []              | List of network interfaces to be added to the public zone of the firewall ruleset.                                    |
| `rhbase_hosts_entry`                      | true            | When set, an entry is added to `/etc/hosts` with the machine's host name. This speeds up gathering facts.             |
| `rhbase_install_packages`                 | []              | List of packages that should be installed. URLs are also allowed.                                                     |
| `rhbase_override_firewalld_zones`         | false           | When set, allows NetworkManager to override firewall zones set by the administrator(2).                               |
| `rhbase_remove_packages`                  | []              | List of packages that should **not** be installed                                                                     |
| `rhbase_repo_exclude_from_update`         | []              | List of packages to be excluded from an update. Wildcards allowed, e.g. `kernel*`.                                    |
| `rhbase_repo_exclude`                     | []              | List of repositories that should be disabled in yum/dnf.conf                                                          |
| `rhbase_repo_gpgcheck`                    | false           | When set, GPG checks will be performed when installing packages.                                                      |
| `rhbase_repo_installonly_limit`           | 3               | The maximum number of versions of a package (e.g. kernel) that can be installed simultaneously. Should be at least 2. |
| `rhbase_repo_remove_dependencies`         | true            | When set, dependencies that become unused after removing a package will be removed as well.                           |
| `rhbase_repositories`                     | []              | List of RPM packages (including URLs) that install external repositories (e.g. `epel-release`).                       |
| `rhbase_selinux_booleans`                 | []              | List of SELinux booleans to be set to on, e.g. httpd_can_network_connect                                              |
| `rhbase_selinux_state`                    | enforcing       | The default SELinux state for the system. Just [leave this as is](http://stopdisablingselinux.com/).                  |
| `rhbase_ssh_allow_groups`                 | []              | List of groups allowed to ssh. When enabled, only users in these groups are allowed ssh access. (4)                   |
| `rhbase_ssh_hostbasedauthentication`      | 'no'            | Wheter to allow host based authentication.                                                                            |
| `rhbase_ssh_ignorerhosts`                 | 'yes'           | Specifies that .rhosts and .shosts files will not be used in RhostsRSAAuthentication or HostbasedAuthentication.      |
| `rhbase_ssh_key`                          | -               | The public SSH key for the admin user that allows her to log in without a password. The user should exist.            |
| `rhbase_ssh_permitemptypasswords`         | 'no'            | Wheter to allow empty passwords to logon.                                                                             |
| `rhbase_ssh_protocol_version`             | 2               | Sets the SSH protocol version.                                                                                        |
| `rhbase_ssh_rhostsrsaauthentication`      | 'no'            | Wheter to allow rhosts RSA authentication                                                                             |
| `rhbase_ssh_user`                         | -               | The name of the user that will manage this machine. The SSH key will be installed into the user's home directory.(3)  |
| `rhbase_start_services`                   | []              | List of services that should be running and enabled.                                                                  |
| `rhbase_stop_services`                    | []              | List of services that should **not** be running                                                                       |
| `rhbase_tz`                               | :/etc/localtime | Sets the `$TZ` environment variable (5)                                                                               |
| `rhbase_update`                           | false           | When set, a package update will be performed after installation.                                                      |
| `rhbase_updates_apply`                    | true            | When set, automatic updates will actually install updates.                                                            |
| `rhbase_updates_debuglevel`               | 0               | Integer denoting the level of verbosity of debug messages.                                                            |
| `rhbase_updates_download`                 | true            | When set, automatic updates will download                                                                             |
| `rhbase_updates_email_from`               | root            | From: Email address used for messages regarding automatic updates                                                     |
| `rhbase_updates_email_host`               | localhost       | Host name used for email messages regarding automatic updates                                                         |
| `rhbase_updates_email_to`                 | root            | To: Email address used for messages regarding automatic updates                                                       |
| `rhbase_updates_emit_via`                 | stdio           | Emitter to report results of automatic updates through (either `stdio`, `email`, `motd`, or a comma separated list)   |
| `rhbase_updates_message`                  | true            | Whether a message should be emitted when updates are available, were downloaded, or applied (yum-cron)                |
| `rhbase_updates_random_sleep`             | 360             | Maximum random delay in seconds betfore downloading.                                                                  |
| `rhbase_updates_type`                     | default         | Type of updates (default, security; yum-cron has more options, e.g. minimal)                                          |
| `rhbase_user_groups`                      | []              | List of user groups that should be present.                                                                           |
| `rhbase_users`                            | []              | List of dicts specifying users that should be present. See below for an example.                                      |
| `rhbase_yum_cron_hourly_download_updates` | true            | Whether to download updates when available using the hourly yum-cron.                                                 |
| `rhbase_yum_cron_hourly_install_updates`  | false           | Whether to install updates when available using the hourly yum-cron.                                                  |
| `rhbase_yum_cron_hourly_sleep_time`       | 15              | Maximum of amount of random sleep for the hourly yum-cron in minutes.                                                 |
| `rhbase_yum_cron_hourly_update_level`     | minimal         | What kind of update to use on the hourly cron (default, security, security-severity:Critical, minimal, ...).          |
| `rhbase_yum_cron_hourly_update_messages`  | true            | Whether to display or send messages when the hourly yum-cron has executed a task.                                     |

**Remarks:**

(1) A complete list of valid values for `rhbase_firewall_allow_services` can be enumerated with the command `firewall-cmd --get-services`.

(2) This is a workaround for [CentOS bug #7407](https://bugs.centos.org/view.php?id=7407). NetworkManager by default manages firewall zones, which overrides rules you add with `--permanent`.

(3) Setting the variable `rhbase_ssh_user` does not actually create a user, but installs the `rhbase_ssh_key` in that user's home directory (`~/.ssh/authorized_keys`). Consequently, `rhbase_ssh_user` should be the name of an existing user, specified in `rhbase_users`.

(4) If you use this role with Vagrant and set the variable `rhbase_ssh_allow_groups`, you need to define the `vagrant` group in the list of `rhbase_ssh_allow_groups`.

(5) Setting `$TZ` variable may reduce the number of system calls. See <https://blog.packagecloud.io/eng/2017/02/21/set-environment-variable-save-thousands-of-system-calls/>

### Enabling repositories

Enable (installed, but disabled) repositories by specifying `rhbase_enable_repos` as a list of dicts with keys `name:` (required) and `section:` (optional), e.g.:

```Yaml
rhbase_enable_repos:
  - name: CentOS-fasttrack
    section: fasttrack
  - name: epel-testing
```

When the section is not specified, it defaults to the repository name.

### Adding users

Users are specified by dicts like this:

```Yaml
rhbase_users:
  - name: johndoe
    comment: 'John Doe'
    groups:
      - users
      - devs
    password: '$6$WIFkXf07Kn3kALDp$fHbqRKztuufS895easdT [...]'
  - name: janedoe
```

The only mandatory key is `name`.

| Key        | Required |   Default   | Comments                               |
|:-----------|:--------:|:-----------:|:---------------------------------------|
| `name`     |   yes    |      -      | The user name                          |
| `comment`  |    no    |     ''      | Comment string                         |
| `shell`    |    no    | '/bin/bash' | The user's command shell               |
| `groups`   |    no    |     []      | Groups this user should be added to(1) |
| `password` |    no    |    '!!'     | The user's password hash(2)            |

**Remarks:**

(1) If you want to make a user an administrator, make sure they are member of the group `wheel` (See [RedHat System Administrator's Guide](https://access.redhat.com/documentation/en-US/Red_Hat_Enterprise_Linux/7/html/System_Administrators_Guide/chap-Gaining_Privileges.html#sect-Gaining_Privileges-The_su_Command).

(2) The password should be specified as a hash, as returned by [crypt(3)](http://man7.org/linux/man-pages/man3/crypt.3.html), in the form `$algo$salt$hash`. For tests and proof-of-concept VMs, you can take a look at <https://www.mkpasswd.net/> for generating hashes in the correct form. Typical hash types for Linux are MD5 (crypt-md5, hashes starting with `$1$`) and SHA-512 (crypt-sha-512, hashes starting with `$6$`).

## Dependencies

No dependencies.

## Example Playbook

See the [test playbook](https://github.com/bertvv/ansible-role-rh-base/blob/tests/test.yml)

## Testing

Tests for this role are provided in the form of a Vagrant environment that is kept in a separate branch, `tests`. I use [git-worktree(1)](https://git-scm.com/docs/git-worktree) to include the test code into the working directory. Instructions for running the tests:

1. Fetch the tests branch: `git fetch origin tests`
2. Create a Git worktree for the test code: `git worktree add tests tests` (remark: this requires at least Git v2.5.0). This will create a directory `tests/`.
3. `cd tests/`
4. `vagrant up` will then create VMs of the supported platforms and apply a test playbook (`test.yml`).

## Contributing

Issues, feature requests, ideas are appreciated and can be posted in the Issues section.

Pull requests are also very welcome. The best way to submit a PR is by first creating a fork of this Github project, then creating a topic branch for the suggested change and pushing that branch to your own fork. Github can then easily create a PR based on that branch. Don't forget to add your name to the contributor list below!

## License

BSD

## Contributors

- Bert Van Vreckem (maintainer)
- [Jens Van Deynse](https://github.com/JensVanDeynse1994)
- [Jeroen De Meerleer](https://github.com/JeroenED)
- [Sebastien Nussbaum](https://github.com/SebaNuss)
- [Sven de Windt](https://github.com/svendewindt)
- [Tim Caudron](https://github.com/TimCaudron)
- [Tomas Dabašinskas](https://github.com/T0MASD)
