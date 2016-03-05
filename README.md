## rdiff-backup is a reverse differential backup tool

rdiff-backup backs up one directory to another, possibly over a network. The target directory ends up a copy of the source directory, but extra reverse diffs are stored in a special subdirectory of that target directory, so you can still recover files lost some time ago. The idea is to combine the best features of a mirror and an incremental backup. rdiff-backup also preserves subdirectories, hard links, dev files, permissions, uid/gid ownership (if it is running as root), modification times, acls, eas, resource forks, etc. Finally, rdiff-backup can operate in a bandwidth efficient manner over a pipe, like rsync. Thus you can use rdiff-backup and ssh to securely back a hard drive up to a remote location, and only the differences will be transmitted.

Read more on [the rdiff-backup website](http://www.nongnu.org/rdiff-backup/).

## Installing

rdiff-backup is available in package form across many operating systems.

### Linux

 * Debian/Ubuntu: `apt-get install rdiff-backup`
 * RHEL/CentOS: `yum install rdiff-backup`

### OS X

 * With [homebrew](http://brew.sh/): `brew install rdiff-backup`

### Windows

 * With the [Cygwin](https://cygwin.com/) setup tool, install the `rdiff-backup` package, or
 * With [Chocolatey](https://chocolatey.org/): `choco install rdiff-backup` (and probably `choco install win32-openssh` if you'd like to back up over a network)

The [old README](rdiff-backup/README) contains information about building from source.

## Usage

Here are some basic examples. For more detail and information about restoring files, see [these examples](http://www.nongnu.org/rdiff-backup/examples.html).

### Local to local backup

`rdiff-backup /some/local-dir /some/other-local-dir`

### Local to remote backup

`rdiff-backup /some/local-dir user@example.com::/some/remote-dir`

### Remote to local backup

`rdiff-backup user@example.com::/some/remote-dir /some/local-dir`

## License

rdiff-backup is released under the [GNU General Public License](rdiff-backup/COPYING).