---
pagetitle: rdiff-backup examples
---
rdiff-backup examples
=====================

### Sections

-   [Backing up](#backup)
-   [Restoring](#restore)
-   [Deleting older files](#delete_older)
-   [File selection with include/exclude options](#exclude)
-   [Getting information about the backup directory](#query)
-   [Miscellaneous other commands](#misc)

[]{#backup}

### Backing up

-   Simplest case\-\--backup local directory `foo` to local directory
    `bar`. `bar` will end up a copy of `foo`, except it will contain the
    directory foo/rdiff-backup-data, which will allow rdiff-backup to
    restore previous states.

    > `rdiff-backup foo bar`

-   Simple remote case\-\--backup directory `/some/local-dir` to the
    directory `/whatever/remote-dir` on the machine hostname.net. It
    uses ssh to open the necessary pipe to the remote copy of
    rdiff-backup. Just like the above except one directory is on a
    remove computer.

    > `rdiff-backup /some/local-dir hostname.net::/whatever/remote-dir`

-   This time the source directory is remote and the destination is
    local. Also, we have specified the username on the remote host (by
    default ssh will attempt to log you in with the same username you
    have on the local host).

    > `rdiff-backup user@hostname.net::/remote-dir local-dir`

-   It is even possible for both the source and destination directories
    to be on other machines. Below we have also added the `-v5` switch
    for greater verbosity (verbosity settings go from 0 to 9, with 3 as
    the default), and the `--print-statistics` switch so some statistics
    will be displayed at the end (even without this switch, the
    statistics will still be saved in the `rdiff-backup-data`
    directory).

    > `rdiff-backup -v5 --print-statistics user1@host1::/source-dir user2@host2::/dest-dir`

[]{#restore}

### Restoring

-   Suppose earlier we have run `rdiff-backup foo bar`, with both foo
    and bar local. We accidentally deleted `foo/dir` and now want to
    restore it from `bar/dir`.

    > `cp -a bar/dir foo/dir`

    That\'s right, since rdiff-backup makes a mirror, we can retrieve
    files using standard commands like `cp`.

-   For the rest of the examples in the section, we will assume that the
    user has backed up with the command
    `rdiff-backup local-dir host.net::/remote-dir`. Of course, in all
    these examples it would be equally possible to have the source being
    remote and the backup directory local.

    In this case we can\'t use `cp` to copying
    `host.net::remote-dir/file` to `local-dir/file` because they are on
    different machines. We can get rdiff-backup to restore the current
    version of that file using either of these::

    > `rdiff-backup --restore-as-of now host.net::/remote-dir/file local-dir/filerdiff-backup -r now host.net::/remote-dir/file local-dir/file`

    The `--restore-as-of` (or `-r` for short) switch tells rdiff-backup
    to restore instead of back up, and the `now` option indicates the
    current time.

-   But the main advantage of rdiff-backup is that it keeps version
    history. This command restores `host.net::/remote-dir/file` as it
    was 10 days ago into a new location `/tmp/file`.

    > `rdiff-backup -r 10D host.net::/remote-dir/file /tmp/file`

    Other acceptable time strings include `5m4s` (5 minutes and 4
    seconds) and `2002-03-05` (March 5th, 2002). For more information,
    see the TIME FORMATS section of the manual page.

-   Finally, we can use rdiff-backup to restore directory from an
    increment file. Increment files are stored in
    `host.net::/remote-dir/rdiff-backup-data/increments` and hold the
    previous versions of changed files. If you specify one directly:

    > `rdiff-backup host.net::/remote-dir/rdiff-backup-data/increments/file.2003-03-05T12:21:41-07:00.diff.gz local-dir/file`

    rdiff-backup will tell from the filename that it is an rdiff-backup
    increment file and thus enter restore mode. Above the restored
    version is written to `local-dir/file`.

[]{#delete_older}

### Deleting older files

Although rdiff-backup tries to save space by only storing file
differences, eventually space may run out in the destination directory.
rdiff-backup\'s `--remove-older-than` mode can be used to delete older
increments.

This section assumes that rdiff-backup has been used in the past to back
up to `host.net::/remote-dir`, but all commands would work locally too,
if the hostname were omitted.

-   This commands deletes all information concerning file versions which
    have not been current for 2 weeks:

    > `rdiff-backup --remove-older-than 2W host.net::/remote-dir`

    Note that an existing file which hasn\'t changed for a year will
    still be preserved. But a file which was deleted 15 days ago cannot
    be restored after this command is run.

-   As when restoring, there are a variety of ways to specify the time.
    The `20B` below tells rdiff-backup to only preserve information from
    the last 20 rdiff-backup sessions. (`nnB` syntax is only available
    in versions after 0.13.1.)

    > `rdiff-backup --remove-older-than 20B host.net::/remote-dir`

[]{#exclude}

### File selection with include/exclude options

Sometimes you don\'t want to back up all files. The various `--include`
and `--exclude` options can be used to select exactly which files to
back up. See the man page for a list of all the options and their
definitions.

-   In this example we exclude `/mnt/backup` to avoid an infinite loop.

    > `rdiff-backup --exclude /mnt/backup / /mnt/backup`

    (Actually rdiff-backup can automatically detect simple loops like
    the one above.) This is just an example, in reality it would be
    important to exclude `/proc` as well.

-   This example is more realistic. We have excluded `/proc`, `/tmp`,
    and `/mnt`. `/proc` in particular should never be backed up. Also,
    the source directory happens to be remote.

    > `rdiff-backup --exclude /tmp --exclude /mnt --exclude /proc user@host.net::/ /backup/host.net`

-   Multiple include and exclude options take precedence in the order
    they are given. The following command would back up `/usr/local/bin`
    but not `/usr/bin`.

    > `rdiff-backup --include /usr/local --exclude /usr / host.net::/backup`

-   rdiff-backup uses rsync-like wildcards, where `**` matches any path
    and `*` matches any path without a `/` in it. Thus this command:

    > `rdiff-backup --include /usr/local --include /var --exclude '**' / /backup`

    backs up only the `/usr/local` and `/var` directories. The single
    quotes `''` are not part of rdiff-backup and are only used because
    many shells will expand `**`.

-   Here is a more complicated example:

    > `rdiff-backup --include '**txt' --exclude /usr/local/games --include /usr/local --exclude /usr --exclude /backup --exclude /proc / /backup`

    The above command will back up any file ending in `txt`, even
    `/usr/local/games/pong/scores.txt` because that include has highest
    precedence. The contents of the directory `/usr/local/bin` will get
    backed up, but not `/usr/share` or `/usr/local/games/pong`.

-   rdiff-backup can also accept a list of files to be backed up. If the
    file `include-list` contains these two lines:

    >     /var
    >     /usr/bin/gzip

    Then this command:

    > `rdiff-backup --include-filelist include-list --exclude '**' / /backup`

    would only back up the files `/var`, `/usr`, `/usr/bin`, and
    `/usr/bin/gzip`, but not `/var/log` or `/usr/bin/gunzip`. Note that
    this differs from the `--include` option, since `--include /var`
    would also match `/var/log`.

-   The same file list can both include and exclude files. If we create
    a file called `include-list` that contains these lines:

    >     **txt
    >     - /usr/local/games
    >     /usr/local
    >     - /usr
    >     - /backup
    >     - /proc

    Then the following command will do exactly the same thing as the
    complicated example two above.

    >     rdiff-backup --include-globbing-filelist include-list / /backup

    Above we have used `--include-globbing-filelist` instead of
    `--include-filelist` so that the lines would be interpreted as if
    they were specified on the command line. Otherwise, for instance,
    `**txt` would be considered the name of a file, not a globbing
    string.

[]{#query}

### Getting information about the backup directory

The following examples assume that you have run
`rdiff-backup in-dir out-dir` in the past.

-   This command finds all new or old files which contain the string
    `frobniz`.

    > `find out-dir -name '*frobniz*'`

    rdiff-backup doesn\'t obscure the names of files at all, so often
    using traditional tools work well.

-   Either of these equivalent commands lists the times of the available
    versions of the file `out-dir/file`. It may be useful if you need to
    restore an older version of `in-dir/file` but aren\'t sure which
    one.

    > `rdiff-backup --list-increments out-dir/filerdiff-backup -l out-dir/file`

-   The following command lists all the files under `out-dir/subdir`
    which has changed in the last 5 days.

    > `rdiff-backup --list-changed-since 5D out-dir/subdir`

-   This command lists all the files that were present in
    `out-dir/subdir` 5 days ago. This includes files that have not
    changed recently as well as those that have been deleted in the last
    5 days.

    > `rdiff-backup --list-at-time 5D out-dir/subdir`

-   rdiff-backup writes one statistics file per session to the
    `out-dir/rdiff-backup-data` directory. An average of the files can
    be displayed using the `--calculate-average` option and specifying
    the statistics files to use.

    > `rdiff-backup --calculate-average out-dir/rdiff-backup-data/session_statistics*`

[]{#misc}

### Miscellaneous other commands

-   If you are having problems connecting to a remote host, the
    `--test-server` command may be useful. This command simply verifies
    that there is a working rdiff-backup server on the remote side.

    > `rdiff-backup --test-server hostname.net::/ignored`
