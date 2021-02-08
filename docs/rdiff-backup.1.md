---
title: RDIFF-BACKUP
section: 1
header: User Manual
author:
- Ben Escoto <ben@emerose.org>
- Eric Lavarde <ewl+rdiffbackup@lavar.de>
...

# NAME

**rdiff-backup** — local/remote mirror and incremental backup

# SYNOPSIS

| **rdiff-backup** \[options...] _action_ \[sub-options...] [_locations_...]
| **rdiff-backup** \[**\--new**] \[**-h**|**\--help**|**-V**|**\--version**]

# DESCRIPTION

rdiff-backup is a script, written in **python(1)** that backs up one directory
to another. The target directory ends up a copy (mirror) of the source
directory, but extra reverse diffs are stored in a special sub-directory of
that target directory, so you can still recover files lost
some time ago. The idea is to combine the best features of a mirror
and an incremental backup. rdiff-backup also preserves symlinks, special files, hardlinks, permissions, uid/gid ownership, and modification
times.

rdiff-backup can also operate in a bandwidth efficient manner over a
pipe, like **rsync(1)**. Thus you can use ssh and rdiff-backup to securely
back a hard drive up to a remote location, and only the differences
will be transmitted. Using the default settings, rdiff-backup requires
that the remote system accept ssh connections, and that rdiff-backup is
installed in the user's PATH on the remote system. For information on
other options, see the section on REMOTE OPERATION.

Note that you should not write to the mirror directory except with
rdiff-backup. Many of the increments are stored as reverse diffs, so
if you delete or modify a file, you may lose the ability to restore
previous versions of that file.

Finally, this man page is intended more as a precise description of the
behavior and syntax of rdiff-backup. New users may want to check out
the examples file included in the rdiff-backup distribution.

The rdiff-backup commands knows four types of parameters

1. generic options valid for all actions,
2. one action out of **backup**, **calculate**, **compare**, **info**,
   **list**, **regress**, **remove**, **restore**, **server**, **test**,
   **verify**,
3. sub-options applicable to each action specifically, even though some are
   common to multiple actions,
4. zero, one, two or more location paths, either local or remote.

Note that this documents the _new_ command line interface of rdiff-backup
since 2.1+; for the traditional one, check **rdiff-backup-old(1)** but
consider that it is deprecated and will disappear.

## Options

-h, \--help

:   Prints brief usage information and exits. Add **\--new** to be sure to get
    this CLI description, and not the old one.
    Placed _after_ the action, outputs the action's specific help message.

-V, \--version

:   Prints the current version number and exits.

\--api-version _API-VERSION_

:   Sets the API version to the given integer between minimum and
    maximum versions as given by the **info** action.
    It is the responsibility of the user to make sure that this version is
    also supported by any server started by this client.

\--chars-to-quote, \--override-chars-to-quote _CHARS_

:   If the filesystem to which we are backing up is not case-sensitive,
    automatic 'quoting' of characters occurs. For example, a file
    'Developer.doc' will be converted into ';068eveloper.doc'.
    To quote other characters or force quoting, e.g. in case rdiff-backup
    doesn't recognize a case-insensitive file system, you need to specify
    this option. _CHARS_ is a string of characters fit to be used in regexp
    square brackets (e.g. 'A-Z' as in '[A-Z]').

    **CAUTION:** do NOT change the chars to quote within the same repository!
    Actually, you only need to set this parameter when creating a new backup
    repository. Do also NOT quote any character used by rdiff-backup  in
    rdiff-backup-data (any of 'a-z0-9._-')!

\--current-time _CURRENT-TIME_

:   This option is useful mainly for testing. If set, rdiff-backup
    will use it for the current time instead of consulting the
    clock. The argument is the number of seconds since the epoch.

\--force

:   Authorize a more drastic modification of a directory than usual
    (for instance, when overwriting of a destination path, or when
    removing multiple sessions with \--remove-older-than). rdiff-backup
    will generally tell you if it needs this.

    **CAUTION:** You can cause data loss if you mis-use this option.
    Furthermore, do NOT use this option when doing a restore, as it will
    DELETE files, unless you absolutely know what you are doing.

\--fsync, \--no-fsync

:   This will enable/disable issuing fsync from rdiff-backup altogether.
    This option is designed to optimize performance on busy backup
    systems.

    **CAUTION:** This may render your backup unusable in case of filesystem
    failure. Default is hence for fsync to be enabled.

\--new, \--no-new

:   enforce (or not) the usage of the new parameters. The default currently
    is to show the old usage, but this will change in the near future.

\--null-separator

:   Use nulls (\0) instead of newlines (\n) as line separators,
    which may help when dealing with filenames containing newlines.
    This affects the expected format of the files specified by the
    **\--{include|exclude}-filelist[-stdin]** switches as well as the
    format of the directory statistics file.

\--parsable-output

:   If set, rdiff-backup's output will be tailored for easy parsing
    by computers, instead of convenience for humans. Currently this
    only applies when listing increments using the 'list increments' action,
    where the time will be given in seconds since the epoch.

\--remote-schema _REMOTE-SCHEMA_

:   Specify an alternate method of connecting to a remote computer.
    This is necessary to get rdiff-backup not to use ssh for remote
    backups, or if, for instance, rdiff-backup is not in the PATH on
    the remote side. See the REMOTE OPERATION section for more information.

\--remote-tempdir _DIR-PATH_

:   use path as temporary directory on the remote side of the connection.

\--restrict-path _DIR-PATH_

:   Require that all file access be inside the given path. This
    switch, and **\--restrict-mode**, are intended to be used with the
    \--server switch to provide a bit more protection when doing au‐
    tomated remote backups.

    **CAUTION:** Those options are not intended as your only line
    of defense so please don't do something silly like allow public
    access to an rdiff-backup server run with **\--restrict-mode read-only**.

\--restrict-mode {**read-write**,**read-only**,**update-only**}

:   restriction mode for the directory given by **\--restrict-path**, either
    full access (aka read-write), read-only, or only to update incrementally
    an already existing back-up (default is **read-write**).

\--ssh-compression, \--no-ssh-compression

:   use SSH with or without compression with default remote-schema.  This
    option is ignored when using **\--remote-schema**. Compression is on by
    default.

\--tempdir _DIR-PATH_

:   Sets the directory that rdiff-backup uses for temporary files to
    the given path. The environment variables TMPDIR, TEMP, and TMP
    can also be used to set the temporary files directory. See the
    documentation of the Python tempfile module for more information.

\--terminal-verbosity {**0**,**1**,**2**,**3**,**4**,**5**,**6**,**7**,**8**,**9**}

:   select which verbosity to use for messages on the terminal,
    the default is given by **\--verbosity**.

\--use-compatible-timestamps

:   Create timestamps in which the hour/minute/second separator is a
    - (hyphen) instead of a : (colon). It is safe to use this option
    on one backup, and then not use it on another; rdiff-backup supports
    the intermingling of different timestamp formats. This option is enabled
    by default on platforms which require that the colon be escaped.

-v, \--verbosity {**0**,**1**,**2**,**3**,**4**,**5**,**6**,**7**,**8**,**9**}

:   Specify verbosity level (0 is totally silent, 3 is the default,
    and 9 is noisiest). This determines how much is written to the
    log file, and without using **\--terminal-verbosity** to the terminal..

## Actions

backup [[CREATION OPTIONS](#creation)] [[COMPRESSION OPTIONS](#compression)] [[SELECTION OPTIONS](#selection)] [[FILESYSTEM OPTIONS](#filesystem)] [[USER GROUP OPTIONS](#usergroup)] [[STATISTICS OPTIONS](#statistics)] _sourcedir_ _targetdir_

:   back-up a source directory to a target backup repository.

calculate [\--method **average**] _statfile1_ _statfile2_ [...]

:   calculate average across multiple statistics files

    \--method **average**

    :   there is currently only one method and it is the default, but it might
        change in the future.

compare [[SELECTION OPTIONS](#selection)] [\--method _method_] [\--at _time_] _sourcedir_ _targetdir_

:   Compare a directory with the backup set at the given time. This
    can be useful to see how archived data differs from current
    data, or to check that a backup is current.

    \--method _method_

    :   method used to compare can be either **meta**, **full** or **hash**,
        where the default is **meta**, which is also how rdiff-backup decides
        which file needs to be backed-up. Note that with **full**, the
        repository data will be copied in its entirety to the source side and
        compared byte by byte. This is the slowest but most complete compare
        method. With **hash** only the SHA1 checksum of regular files will be
        compared. With **meta** only the metadata of files will be compared
        (name, size, date, type, etc).

    \--at _time_

    :   at which _time_ of the back-up directory should the comparaison take
        place. The default is **now**, meaning the latest version.

info

:   outputs information about the current system in YAML format, so that it
    can be used in a bug report, and exits.

list
regress
remove
restore
server
test
verify

# <a name="compression">COMPRESSION OPTIONS</a>
# <a name="creation">CREATION OPTIONS</a>
# <a name="filesystem">FILESYSTEM OPTIONS</a>
# <a name="selection">SELECTION OPTIONS</a>
# <a name="statistics">STATISTICS OPTIONS</a>
# <a name="usergroup">USER GROUP OPTIONS</a>

# FILES

*any config file*

:   you can create a file with one option/action/sub-option per line and
    use it on the command line with _\@anyconfigfile_ and its content
    will be interpreted as if given on the command line.

    For example, creating a file '`mybackup`' with following content:

        backup
        source_dir
        target_dir

    and calling '`rdiff-backup @mybackup`' will be the same as calling
    '`rdiff-backup backup source_dir target_dir`'.

# ENVIRONMENT

**RDIFF_BACKUP_VERBOSITY**=_[0-9]_

:   the default verbosity for log file and terminal, can be
    overwritten by the corresponding options **-v/\--verbosity** and
    **\--terminal-verbosity**.

# BUGS

See GitHub Issues:

:   <https://github.com/rdiff-backup/rdiff-backup/issues>

# SEE ALSO

**hi(1)**, **hello(3)**, **hello.conf(4)**

<!---
pandoc --standalone --to man --variable date="$(date -I)" --variable footer="Version $(./setup.py --version)" docs/rdiff-backup.1.md -o /tmp/rdiff-backup.1 && man -l /tmp/rdiff-backup.1
-->
