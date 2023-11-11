rdiff-backup is a simple backup tool which can be used locally and remotely,
on Linux and Windows, and even cross-platform between both.
Users have reported using it successfully on FreeBSD and MacOS X.

Beside it's ease of use, one of the main advantages of rdiff-backup is that it
does use the same efficient protocol as rsync to transfer and store data.
Because rdiff-backup only stores the differences from the previous backup to
the next one (a so called reverse incremental backup),
the latest backup is always a full backup, making it easiest
and fastest to restore the most recent backups, combining the space
advantages of incremental backups while keeping the speed advantages of full
backups (at least for recent ones).

If the optional dependencies pylibacl and pyxattr are installed,
rdiff-backup will support Access Control Lists and Extended Attributes
provided the file system(s) also support these features.
