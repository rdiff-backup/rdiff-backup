# rdiff-backup

[![Build Status](https://travis-ci.org/rdiff-backup/rdiff-backup.svg?branch=master)](https://travis-ci.org/rdiff-backup/rdiff-backup)

rdiff-backup is a simple backup tool which can be used locally and remotely,
on Linux and Windows, and even cross-platform between both.
Users have reported using it successfully on FreeBSD and MacOS X.

Beside it's ease of use, one of the main advantages of rdiff-backup is that it
does use the same efficient protocol as rsync to transfer and store data.
Because rdiff-backup only stores the differences from the previous backup to
the next one (a so called
[reverse incremental backup](https://en.wikipedia.org/wiki/Incremental_backup#Reverse_incremental)),
the latest backup is always a full backup, making it easiest
and fastest to restore the most recent backups, combining the space
advantages of incremental backups while keeping the speed advantages of full
backups (at least for recent ones).

If the optional dependencies pylibacl and pyxattr are installed,
rdiff-backup will support
[Access Control Lists](https://en.wikipedia.org/wiki/Access-control_list#Filesystem_ACLs)
and [Extended Attributes](https://en.wikipedia.org/wiki/Extended_file_attributes)
provided the file system(s) also support these features.

## INSTALLATION

### From Linux system package

Many Linux distributions have packaged rdiff-backup, which can then easiest be installed
using the system tool e.g. `apt|yum|dnf|zypper install rdiff-backup`.

> **NOTE:** consider that the package might not install the optional dependencies
pylibacl and pyxattr, packaged e.g. as python3-pyxattr and py3libacl.

### From our own packaging

If you want or need a more recent version than provided by your distribution,
the [rdiff-project releases its' own packages](https://github.com/rdiff-backup/rdiff-backup/releases), which you can install as follows.

> **IMPORTANT:** the following instructions assume the availability of a
version of rdiff-backup equal or higher to 1.4.0 (beta) or 2.0.0 (stable).

#### On Linux

You need to make sure that the following requirements are met:

* Python 3.5 or higher
* librsync 1.0.0 or higher
* pylibacl (optional, to support ACLs)
* pyxattr (optional, to support extended attributes)
* SSH for remote operations

Then you can install one of the following packages:

* `rdiff_backup-VERSION-PYVER-PLATFORM.whl` - wheel distribution - this is the recommended installation approach (because you can easily deinstall), either with `sudo pip install rdiff_backup...whl` to install globally for all users, or with `pip install --user rdiff_backup...whl` for only the current user. Advanced and cautious users can of course install within a virtualenv. Deinstallation works similarly with `sudo pip uninstall rdiff-backup` (global) resp. `pip uninstall rdiff-backup` (user).
* `rdiff-backup-VERSION-PLATFORM.tar.gz` - binary distribution - can be "installed" using `tar xvzf rdiff-backup...tar.gz -C /` but it can't be easily deinstalled, you'll need to do it manually.

> **NOTE:** the installation approach should make sure that rdiff-backup is in the PATH, which makes remote operations a lot easier.

#### On Windows

Just drop the binary `rdiff-backup-VERSION-PLATFORM.exe`, possibly renamed to `rdiff-backup`,
somewhere in your PATH and it should work, as it comes with all dependencies included.

For remote operations, you will need to have an SSH package installed (also on Linux but it is
generally more obvious).

> **NOTE:** for now the documentation under Windows is available online from the [documentation folder](docs/).

### From source code

This is an advanced topic, but necessary for platforms like MacOS X and FreeBSD, and
described in the [developer documentation](docs/DEVELOP.md).

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
