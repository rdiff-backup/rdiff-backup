![rdiff-backup banner](docs/resources/logo-banner.png)

<p align="center">
  <strong>
    <a href="https://rdiff-backup.net/">website</a>
    •
    <a href="https://rdiff-backup.net/docs/docs.html">docs</a>
    •
    <a href="https://lists.nongnu.org/mailman/listinfo/rdiff-backup-users">community</a>
  </strong>
</p>

<p align="center">
<a href="https://travis-ci.org/rdiff-backup/rdiff-backup"><img alt="Build Status" src="https://travis-ci.org/rdiff-backup/rdiff-backup.svg?branch=master"></a>
<a href="COPYING"><img alt="License" src="https://img.shields.io/github/license/rdiff-backup/rdiff-backup"></a>
<a href="http://hits.dwyl.io/rdiff-backup/rdiff-backup"><img alt="HitCount" src="http://hits.dwyl.io/rdiff-backup/rdiff-backup.svg"></a>
</p>

# rdiff-backup

rdiff-backup is a simple backup tool which can be used locally and remotely,
on Linux and Windows, and even cross-platform between both.
Users have reported using it successfully on FreeBSD and MacOS X.

Beside its ease of use, one of the main advantages of rdiff-backup is that it
does use the same efficient protocol as rsync to transfer and store data.
Because rdiff-backup only stores the differences from the previous backup to
the next one (a so called
[reverse incremental backup](https://en.wikipedia.org/wiki/Incremental_backup#Reverse_incremental)),
the latest backup is always a full backup, making it easiest
and fastest to restore the most recent backups, combining the space
advantages of incremental backups while keeping the speed advantages of full
backups (at least for recent ones).

If the optional dependencies pylibacl and pyxattr are installed, rdiff-backup will support
[Access Control Lists](https://en.wikipedia.org/wiki/Access-control_list#Filesystem_ACLs)
and [Extended Attributes](https://en.wikipedia.org/wiki/Extended_file_attributes)
provided the file system(s) also support these features.

## INSTALLATION

In older Linux distributions the rdiff-backup versions are of the 1.x series, which is not recommended for new installs anymore. Follow the instructions below to install the latest 2.x release of rdiff-backup.

> **CAUTION:** rdiff-backup 1.x and 2.x aren't compatible and can't be mixed in server/client mode!
	See [how to migrate side-by-side](docs/migration.md).

### Ubuntu Focal or Debian Bullseye or newer (has 2.0)

```
sudo apt install rdiff-backup
```

### Ubuntu backports for older versions (needs a backported 2.0)

```
sudo apt install software-properties-common
sudo add-apt-repository ppa:rdiff-backup/rdiff-backup-backports
sudo apt update
sudo apt install rdiff-backup
```

### CentOS and RHEL 7 (From COPR)

```
sudo yum install yum-plugin-copr epel-release
sudo yum copr enable frankcrawford/rdiff-backup
sudo yum install rdiff-backup
sudo yum install py3libacl pyxattr
```

> **NOTE:** the last line is optional to get ACLs and EAs support.

### CentOS and RHEL 8 (From COPR)

```
sudo dnf install dnf-plugins-core epel-release
sudo dnf copr enable frankcrawford/rdiff-backup
sudo dnf --enablerepo=PowerTools install rdiff-backup
```

> **NOTE:** you can add the option `--setopt=install_weak_deps=False` to the
	last line if you don't need ACLs and EAs support. You can install
	`python3-pylibacl` and `python3-pyxattr` also separately.
	Under RHEL, the repo to enable is [codeready-builder-for-rhel-8-x86_64-rpms](https://access.redhat.com/documentation/en-us/red_hat_enterprise_linux/8/html/package_manifest/codereadylinuxbuilder-repository) in order to get access
	to pyxattr, instead of PowerTools.

### Fedora 32+

```
sudo dnf install rdiff-backup
```

> **NOTE:** for earlier versions, see the COPR instructions below.

### Debian and derivatives, Raspbian, etc. (from PyPi)

```
sudo apt install python3-pip python3-setuptools python3-pylibacl python3-pyxattr
sudo pip3 install rdiff-backup
```

> **NOTE:** If your platform is not i386 or amd64, e.g. ARM/MIPS/etc,
  you may need the build dependencies `build-essentials`, `librsync-dev`.

### CentOS and RHEL 6 (from PyPi)

```
sudo yum install centos-release-scl
sudo yum install rh-python36 gcc libacl-devel
scl enable rh-python36 bash
sudo pip install rdiff-backup pyxattr pylibacl
echo 'exec scl enable rh-python36 -- rdiff-backup "$@"' | sudo tee /usr/bin/rdiff-backup
sudo chmod +x /usr/bin/rdiff-backup
```

### Fedora and derivatives (from PyPI)

```
sudo dnf install python3-pip python3-setuptools py3libacl python3-pyxattr
sudo pip3 install rdiff-backup
```

### Other Linux and UN\*X-oid systems, e.g. BSD (From PyPi)

You need to make sure that the following requirements are met:

* Python 3.6 or higher
* pip3 e.g. installed with `curl https://bootstrap.pypa.io/get-pip.py -o get-pip.py; sudo python3 get-pip.py`.
* librsync 1.0.0 or higher
* pylibacl (optional, to support ACLs)
* pyxattr (optional, to support extended attributes) - the xattr library (without py) isn't regularly tested but should work and you will be helped
* if Python's version is 3.7.x or below, importlib-metadata 1.x
  (or alternatively setuptools)
* SSH for remote operations

Then you should only need to call the following before you can use rdiff-backup:

```
sudo pip3 install rdiff-backup
```

> **NOTE:** especially if your platform is not i386 or amd64, e.g. ARM/MIPS/PowerPC/etc,
  but also if the pip3 installation fails with `include [...].h` files missing,
  you may need the build dependencies named like `python3-devel` or `librsync-dev`.

### Windows

Just download and unpack the file `rdiff-backup-VERSION.win32exe.zip`
available as _asset_ attached to one of the releases available in the
[releases section](https://github.com/rdiff-backup/rdiff-backup/releases) and
drop the binary `rdiff-backup.exe` somewhere in your PATH and it should work,
as it comes with all dependencies included.

For remote operations, you will need to have an SSH package installed.
We recommand using OpenSSH from http://www.mls-software.com/opensshd.html

## BASIC USAGE

Creating your first backup is as easy as calling `rdiff-backup <source-dir> <backup-dir>`
(possibly as root), e.g. `rdiff-backup -v5 /home/myuser /run/media/myuser/MYUSBDRIVE/homebackup`
would save your whole home directory (under Linux) to a USB drive (which you should have
formatted with a POSIX file system, e.g. ext4 or xfs). Without the `-v5` (v for verbosity),
rdiff-backup isn't very talkative, hence the recommendation.

Subsequent backups can simply be done by calling exactly the same command, again and again.
Only the differences will be saved to the backup directory.

If you need to restore the latest version of a file you lost, it can be as simple as copying
it back using normal operating system means (cp or copy, or even pointing your file browser at
the backup directory). E.g. taking the above example `cp -i /run/media/myuser/MYUSBDRIVE/homebackup/mydir/myfile /home/myuser/mydir/myfile` and the lost file is back!

There are many more ways to use and tweak rdiff-backup, they're documented in the man pages,
in the [documentation directory](docs/), or on [our website](https://rdiff-backup.net).

## TROUBLESHOOTING

If you have everything installed properly, and it still doesn't work,
see the enclosed [FAQ](docs/FAQ.md), the [rdiff-backup web page](https://rdiff-backup.net/)
and/or the [rdiff-backup-users mailing list](https://lists.nongnu.org/mailman/listinfo/rdiff-backup-users).

We're also happy to help if you create an issue to our
[GitHub repo](https://github.com/rdiff-backup/rdiff-backup/issues). The most
important is probably to explain what happened with which version of rdiff-backup,
with which command parameters on which operating system version, and attach the output
of rdiff-backup run with the very verbose option `-v9`.

The FAQ in particular is an important reference, especially if you are
using smbfs/CIFS, Windows, or have compiled by hand on Mac OS X.


## CONTRIBUTING

Rdiff-backup is an open source software developed by many people over a long period of time. There is no particular company backing the development of rdiff-backup, so we rely very much on individual contributors who "scratch their itch". **All contributions are welcome!**

There are many ways to contribute:

- Testing, troubleshooting and writing good bug reports that are easy for other developers to read and act upon
- Reviewing and triaging [existing bug reports and issues](https://github.com/rdiff-backup/rdiff-backup/issues), helping other developers focus their efforts
- Writing documentation (e.g. the [man page](https://github.com/rdiff-backup/rdiff-backup/blob/master/rdiff-backup.1)), or updating the webpage rdiff-backup.net
- Packaging and shipping rdiff-backup in your own favorite Linux distribution or operating system
- Running tests on your favorite platforms and fixing failing tests
- Writing new tests to get test coverage up
- Fixing bug in existing features or adding new features

If you don't have anything particular in your mind but want to help out, just browse the list of issues. Both coding and non-coding tasks have been filed as issues.

For source code related documentation see [docs/DEVELOP.md](docs/DEVELOP.md)

### Installing latest development release

To provide meaningful bug reports and help with testing, please use the latest development release.

#### Ubuntu and Debian development releases

```
sudo add-apt-repository ppa:rdiff-backup/rdiff-backup-development
sudo apt update
sudo apt install rdiff-backup
```

#### Fedora, CentOS and RHEL

On CentOS and RHEL (7 and 8):

```
sudo yum install dnf-plugins-core epel-release
sudo yum copr enable frankcrawford/rdiff-backup
sudo yum install rdiff-backup
```

On Fedora 30+:

```
sudo dnf install dnf-plugins-core
sudo dnf copr enable frankcrawford/rdiff-backup
sudo dnf install rdiff-backup
```

#### PyPi pre-releases

```
sudo pip3 install rdiff-backup --pre
```

## Packaging status in distros

[![Packaging status](https://repology.org/badge/vertical-allrepos/rdiff-backup.svg)](https://repology.org/project/rdiff-backup/versions)
