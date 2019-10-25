---
pagetitle: rdiff-backup FAQ
---
rdiff-backup FAQ
================

### [Table of contents]{#ToC3}

1.  [What do the different verbosity levels mean?](#verbosity)
2.  [Is rdiff-backup backwards compatible?](#compatible)
3.  [Does rdiff-backup run under Windows?](#windows)
4.  [Does rdiff-backup run under Mac OS X?](#OSX)
5.  [Can I backup files to a CIFS or smbfs mount?](#cifs)
6.  [Help! Why do all my filenames now look like ;077y;070ile
    ?!](#case_insensitive)
7.  [My backup set contains some files that I just realized I don\'t
    want/need backed up. How do I remove them from the backup volume to
    save space?](#remove_dir)
8.  [Does rdiff-backup work under Solaris?](#solaris)
9.  [How fast is rdiff-backup? Can it be run on large data
    sets?](#speed)
10. [What do the various fields mean in the session statistics and
    directory statistics files?](#statistics)
11. [Is there some way to limit rdiff-backup\'s bandwidth usage, as in
    rsync\'s \--bwlimit option?](#bwlimit)
12. [How much memory should rdiff-backup use? Is there a memory
    leak?](#leak)
13. [I use NFS and keep getting some error that includes \"OSError:
    \[Errno 39\] Directory not empty\"](#dir_not_empty)
14. [For some reason rdiff-backup failed while backing up. Now every
    time it runs it says \"regressing destination\" and then fails
    again. What should I do?](#regress_failure)
15. [Where does rdiff-backup need free space and how much is required?
    What is the problem if rdiff-backup says
    \"`ValueError: Incorrect length of data produced`\"?](#free_space)
16. [What does \"internal error: job made no progress\"
    mean?](#librsync_bug)
17. [Why does rdiff-backup say it\'s not in my \$PATH? It is when I
    login!](#path)
18. [What does \"`touple index out of range`\" mean?](#touple)
19. [What does \"`IO Error: CRC check failed`\" mean?](#crc)
20. [What does \"`AssertionError: Bad index order`\" mean?](#badindex)
21. [How can rdiff-backup use UTC as the timezone?](#utc)

### [Questions and Answers]{#ToC4}

1.  **[What do the different verbosity levels mean?]{#verbosity}**

    There is no formal specification, but here is a rough description
    (settings are always cumulative, so 5 displays everything 4 does):

      --- ----------------------------------------------------------------------
      0   No information given
      1   Fatal Errors displayed
      2   Warnings
      3   Important messages, and maybe later some global statistics (default)
      4   Some global settings, miscellaneous messages
      5   Mentions which files were changed
      6   More information on each file processed
      7   More information on various things
      8   All logging is dated
      9   Details on which objects are moving across the connection
      --- ----------------------------------------------------------------------

2.  **[Is rdiff-backup backwards compatible?]{#compatible}**

    In general, rdiff-backup does not strive to make newer clients
    compatible with older servers (or vice versa). However, there is no
    intention to purposefully make different versions incompatible
    across the network \-- changes are introduced primarily to fix bugs
    or introduce new features that cannot be implemented without
    breaking the network protocol. Furthermore, rdiff-backup does try to
    make it possible to read older archives.

    When running as a client, rdiff-backup checks the version of
    rdiff-backup running on the server, and prints a warning message if
    the two versions are different. If you have any problems with your
    backup, it is strongly recommended that you upgrade the older
    version before reporting any issues.

3.  **[Does rdiff-backup run under Windows?]{#windows}**

    Yes, although it is not a heavily tested configuration. Rdiff-backup
    can be run as a native Windows application or under Cygwin. To run
    as a native Windows application, simply download the provided .exe
    binary. To setup remote operation, you will also need an SSH client,
    such as [Putty](https://www.chiark.greenend.org.uk/~sgtatham/putty/)
    or [SSH Secure Shell](https://www.ssh.com).

    If you wish to run rdiff-backup under Cygwin, use at least version
    1.1.12. The setup under Cygwin is the same as under other Unix-like
    operating systems. From the Cygwin installer you will need Python
    3.5 or higher (under Interpreters), autoconf, automake, binutils,
    gcc, make, and patchutils (all under Devel). Then you will need to
    compile and install librsync, which can be downloaded [from
    Sourceforge](https://sourceforge.net/project/showfiles.php?group_id=56125).
    Finally, you can compile and install rdiff-backup using the usual
    instructions.

    Although some Windows filesystems lack features like FIFOs, case
    sensitive filenames, or files with colons (\":\") in them, all of
    these situations should be autodetected and compensated for by
    rdiff-backup.

    If you would like more detailed instructions for compiling and
    installing rdiff-backup on Cygwin, you can read this blog entry:
    <https://katastrophos.net/andre/blog/2005/11/02/rdiff-backup-on-windows/>.
    Note: The patch that the blog suggests that you download is no
    longer necessary starting with version 1.1.8 of rdiff-backup.

4.  **[Does rdiff-backup run under Mac OS X?]{#OSX}**

    Yes, quite a few people seem to be using rdiff-backup under Mac
    OS X. rdiff-backup can also backup resource forks and other Mac OS X
    metadata to a traditional unix filesystem, which is can be a handy
    feature for Mac users. When rdiff-backup is used to do the restore,
    all of the metadata is recovered from rdiff-backup\'s storage.

    The easiest option is probably to use Fink
    <http://fink.sourceforge.net/>, which can install rdiff-backup
    automatically for you. With Fink, you should install the `librsync`,
    `librsync-shlibs`, `python25`, `python25-shlibs`, `xattr-py25`, and
    `rdiff-backup` packages. Another option is DarwinPorts
    <https://www.macports.org/>, for which you should install the
    `py-xattr` and `rdiff-backup` packages.

    If you want to build rdiff-backup yourself, you should be able to
    build librsync and rdiff-backup using the standard Unix
    instructions. You can also see this message from Gerd Knops:

        From: Gerd Knops <gerti@bitart.com>
        Date: Thu, 3 Oct 2002 03:56:47 -0500 (01:56 PDT)

        [parts of original message deleted]
        these instructions build it fine with all tests running OK
        (librsync-0.9.5.1 on OS X 10.2.1):

            aclocal
            autoconf
            automake --foreign --add-missing
            env CFLAGS=-no-cpp-precomp ./configure
            make
            make install

    An important note if you use the Apple-provided version of Python:
    Apple\'s version of Python will install rdiff-backup in something
    like
    `/System/Library/Frameworks/Python.framework/Versions/Current/bin/rdiff-backup`
    and `rdiff-backup` will not be in your `$PATH`. You can copy
    rdiff-backup out of this folder and into someplace reasonable like
    `/usr/bin` or another directory in your `$PATH` to use it. For a
    full explanation of why this happens see this post to the mailing
    list:
    <https://lists.nongnu.org/archive/html/rdiff-backup-users/2007-06/msg00107.html>.

5.  **[Can I backup files to a CIFS or smbfs mount?]{#cifs}**

    You can certainly try! Using a CIFS or smbfs mount as the mirror
    directory has been troublesome for some users because of the wide
    variety of Samba configurations. If possible, the best solution is
    always to use rdiff-backup over SSH in the default configuration.
    Using rdiff-backup in the default configuration is also guaranteed
    to be faster because there is lower network utilization.
    Rdiff-backup uses the rsync algorithm to minimize the amount of
    bandwidth consumed. By using smbfs or CIFS, the complete file is
    transferred over the network.

    Under both Linux and Mac OS X, smbfs seems to be working quite well.
    However, it has a 2 GB file limit and is deprecated on Linux. CIFS
    users sometimes experience one of these common errors:

    -   rdiff-backup fails to run, printing an exception about
        \"`assert not upper_a.lstat()`\" failing. This can be resolved
        by unmounting the share, running the following command as root:\
        `$ echo 0 > /proc/fs/cifs/LookupCacheEnabled`\
        and then remounting the CIFS share.\
        \
    -   If filenames in the mirror directory have some characters
        transformed to a \'?\' instead of remaining the expected Unicode
        character, you will need to adjust the `iocharset=` mount
        option. This happens because the server is using a codepage with
        only partial Unicode support and is not translating characters
        correctly. See the mount.cifs man page for more information.
        Using smbfs can also improve this situation since it has both an
        `iocharset=` and a `codepage=` option.
    -   If you have trouble with filenames containing a colon \':\', or
        another reserved Windows character, try using the `mapchars`
        option to the CIFS mount. At least one user has reported success
        when using this option while mounting a NAS system via CIFS. See
        the mount.cifs man page for more information.\
        \
    -   Other CIFS mount options which may be helpful include `nocase`,
        `directio`, and `sfu`. Also, try changing the value of
        `/proc/fs/cifs/LinuxExtensionsEnabled` (requires remount). A
        user with a DroboShare reported that
        `-o mapchars,nocase,directio` worked for that NAS appliance.

    If you\'re still having trouble backing up to a CIFS or smbfs mount,
    try searching the [mailing-list
    archives](https://lists.gnu.org/archive/html/rdiff-backup-users/)
    and then sending further questions to the list.

6.  **[Help! Why do all my filenames now look like ;077y;070ile
    ?!]{#case_insensitive}**

    When backing up from a case-sensitive filesystem to a
    case-insensitive filesystem (such as Mac\'s HFS+ or Windows\'s FAT32
    or NTFS), rdiff-backup escapes uppercase characters in filenames to
    make sure that no files are accidentally overwritten. When a
    filesystem is case-preserving but case-insensitive, it means that it
    remembers that a file is named \"Foo\" but doesn\'t distinguish
    between \"Foo\", \"foo\", \"foO\", \"fOo\", etc. However,
    filesystems such as Linux\'s ext3 do treat these names as separate
    files.

    Imagine you have a Linux directory with two files, \"bar\" and
    \"BAR\", and you copy them to a Mac system. You will wind up with
    only one file (!) since HFS+ doesn\'t distinguish between the names,
    and the second file copied will overwrite the first. Therefore, when
    rdiff-backup copies files from case-sensitive to case-insensitive
    filesystems, it escapes the uppercase characters (eg, \"M\" is
    replaced with \";077\", and \"F\" with \";070\") so that no filename
    conflicts occur. Upon restore (from the Mac backup server to the
    Linux system), the filenames are unquoted and you will get
    \"MyFile\" back.

7.  **[My backup set contains some files that I just realized I don\'t
    want/need backed up. How do I remove them from the backup volume to
    save space?]{#remove_dir}**

    The only official way to remove files from an rdiff-backup
    repository is by letting them expire using the \--remove-older-than
    option. Deleting increments from the rdiff-backup-data directory
    will prevent you from recovering those files, but shouldn\'t prevent
    the rest of the repository from being restored.

8.  **[Does rdiff-backup work under Solaris?]{#solaris}**

    There may be a problem with rdiff-backup and Solaris\' libthread.
    Adding \"ulimit -n unlimited\" may fix the problem though. Here is a
    post by Kevin Spicer on the subject:

        Subject: RE: Crash report....still not^H^H^H working
        From: "Spicer, Kevin" <kevin.spicer@bmrb.co.uk>
        Date: Sat, 11 May 2002 23:36:42 +0100
        To: rdiff-backup@keywest.Stanford.EDU

        Quick mail to follow up on this..
        My rdiff backup (on Solaris 2.6 if you remember) has now worked
        reliably for nearly two weeks after I added...

            ulimit -n unlimited

        to the start of my cron job and created a wrapper script on the remote
        machine which looked like this...

            ulimit -n unlimited
            rdiff-backup --server
            exit

        And changed the remote schema on the command line of rdiff-backup to
        call the wrapper script rather than rdiff-backup itself on the remote
        machine.  As for the /dev/zero thing I've done a bit of Googleing and
        it seems that /dev/zero is used internally by libthread on Solaris
        (which doesn't really explain why its opening more than 64 files - but
        at least I think I've now got round it).

9.  **[How fast is rdiff-backup? Can it be run on large data
    sets?]{#speed}**

    rdiff-backup can be limited by the CPU, disk IO, or available
    bandwidth, and the length of a session can be affected by the amount
    of data, how much the data changed, and how many files are present.
    That said, in the typical case the number/size of changed files is
    relatively small compared to that of unchanged files, and
    rdiff-backup is often either CPU or bandwidth bound, and takes time
    proportional to the total number of files. Initial mirrorings will
    usually be bandwidth or disk bound, and will take much longer than
    subsequent updates.

    To give one arbitrary data point, when I back up my personal HD
    locally (about 36GB, 530000 files, maybe 500 MB turnover, Athlon
    2000, 7200 IDE disks, version 0.12.2) rdiff-backup takes about 15
    minutes and is usually CPU bound.

10. **[What do the various fields mean in the session statistics and
    directory statistics files?]{#statistics}**

    Let\'s examine an example session statistics file:

        StartTime 1028200920.44 (Thu Aug  1 04:22:00 2002)
        EndTime 1028203082.77 (Thu Aug  1 04:58:02 2002)
        ElapsedTime 2162.33 (36 minutes 2.33 seconds)
        SourceFiles 494619
        SourceFileSize 8535991560 (7.95 GB)
        MirrorFiles 493797
        MirrorFileSize 8521756994 (7.94 GB)
        NewFiles 1053
        NewFileSize 23601632 (22.5 MB)
        DeletedFiles 231
        DeletedFileSize 10346238 (9.87 MB)
        ChangedFiles 572
        ChangedSourceSize 86207321 (82.2 MB)
        ChangedMirrorSize 85228149 (81.3 MB)
        IncrementFiles 1857
        IncrementFileSize 13799799 (13.2 MB)
        TotalDestinationSizeChange 28034365 (26.7 MB)
        Errors 0

    StartTime and EndTime are measured in seconds since the epoch.
    ElapsedTime is just EndTime - StartTime, the length of the
    rdiff-backup session.

    SourceFiles are the number of files found in the source directory,
    and SourceFileSize is the total size of those files. MirrorFiles are
    the number of files found in the mirror directory (not including the
    rdiff-backup-data directory) and MirrorFileSize is the total size of
    those files. All sizes are in bytes. If the source directory hasn\'t
    changed since the last backup, MirrorFiles == SourceFiles and
    SourceFileSize == MirrorFileSize.

    NewFiles and NewFileSize are the total number and size of the files
    found in the source directory but not in the mirror directory. They
    are new as of the last backup.

    DeletedFiles and DeletedFileSize are the total number and size of
    the files found in the mirror directory but not the source
    directory. They have been deleted since the last backup.

    ChangedFiles are the number of files that exist both on the mirror
    and on the source directories and have changed since the previous
    backup. ChangedSourceSize is their total size on the source
    directory, and ChangedMirrorSize is their total size on the mirror
    directory.

    IncrementFiles is the number of increment files written to the
    rdiff-backup-data directory, and IncrementFileSize is their total
    size. Generally one increment file will be written for every new,
    deleted, and changed file.

    TotalDestinationSizeChange is the number of bytes the destination
    directory as a whole (mirror portion and rdiff-backup-data
    directory) has grown during the given rdiff-backup session. This is
    usually close to IncrementFileSize + NewFileSize - DeletedFileSize +
    ChangedSourceSize - ChangedMirrorSize, but it also includes the
    space taken up by the hardlink\_data file to record hard links.

11. **[Is there some way to limit rdiff-backup\'s bandwidth usage, as in
    rsync\'s \--bwlimit option?]{#bwlimit}**

    There is no internal rdiff-backup option to do this. However,
    external utilities such as
    [cstream](https://www.cons.org/cracauer/cstream.html) can be used to
    monitor bandwidth explicitly. trevor\@tecnopolis.ca writes:

        rdiff-backup --remote-schema
          'cstream -v 1 -t 10000 | ssh %s '\''rdiff-backup --server'\'' | cstream -t 20000'
          'netbak@foo.bar.com::/mnt/backup' localbakdir

        (must run from a bsh-type shell, not a csh type)

        That would apply a limit in both directions [10000 bytes/sec outgoing,
        20000 bytes/sec incoming].  I don't think you'd ever really want to do
        this though as really you just want to limit it in one direction.
        Also, note how I only -v 1 in one direction.  You probably don't want
        to output stats for both directions as it will confuse whatever script
        you have parsing the output.  I guess it wouldn't hurt for manual runs
        however.

    To only limit bandwidth in one directory, simply remove one of the
    cstream commands. Two cstream caveats may be worth mentioning:

    1.  Because cstream is limiting the uncompressed data heading into
        or out of ssh, if ssh compression is turned on, cstream may be
        overly restrictive.
    2.  cstream may be \"bursty\", limiting average bandwidth but
        allowing rdiff-backup to exceed it for significant periods.

    Another option is to limit bandwidth at a lower (and perhaps more
    appropriate) level. Adam Lazur mentions [The Wonder
    Shaper](https://lartc.org/wondershaper/).

12. **[How much memory should rdiff-backup use? Is there a memory
    leak?]{#leak}**

    The amount of memory rdiff-backup uses should not depend much on the
    size of directories being processed. Keeping track of hard links may
    use up memory, so if you have, say, hundreds of thousands of files
    hard linked together, rdiff-backup may need tens of MB.

    If rdiff-backup seems to be leaking memory, it is probably because
    it is using an early version of librsync. **librsync 0.9.5 leaks
    lots of memory.** Later versions should not leak and are available
    from the [librsync
    homepage](https://sourceforge.net/projects/librsync/).

13. **[I use NFS and keep getting some error that includes \"OSError:
    \[Errno 39\] Directory not empty\"]{#dir_not_empty}**

    Several users have reported seeing errors that contain lines like
    this:

        File "/usr/lib/python2.2/site-packages/rdiff_backup/rpath.py",
            line 661, in rmdir
        OSError: [Errno 39] Directory not empty:
            '/nfs/backup/redfish/win/Program Files/Common Files/GMT/Banners/11132'
        Exception exceptions.TypeError: "'NoneType' object is not callable"
             in <bound method GzipFile.__del__ of

    All of these users were backing up onto NFS (Network File System). I
    think this is probably a bug in NFS, although tell me if you know
    how to make rdiff-backup more NFS-friendly. To avoid this problem,
    run rdiff-backup locally on both ends instead of over NFS. This
    should be faster anyway.

14. **[For some reason rdiff-backup failed while backing up. Now every
    time it runs it says \"regressing destination\" and then fails
    again. What should I do?]{#regress_failure}**

    Firstly, this shouldn\'t happen. If it does, it indicates a
    corrupted destination directory, a bug in rdiff-backup, or some
    other serious recurring problem.

    However, here is a workaround that you might want to use, even
    though it probably won\'t solve the underlying problem: In the
    destination\'s rdiff-backup-data directory, there should be two
    \"current\_mirror\" files, for instance:

        current_mirror.2003-09-07T16:43:00-07:00.data
        current_mirror.2003-09-08T04:22:01-07:00.data

    Delete the one with the earlier date. Also move the mirror\_metadata
    file with the later date out of the way, because it probably didn\'t
    get written correctly because that session was aborted:

        mv mirror_metadata.2003-09-08T04:22:01-07:00.snapshot.gz aborted-metadata.2003-09-08T04:22:01-07:00.snapshot.gz

    The next time rdiff-backup runs it won\'t try regressing the
    destination. Metadata will be read from the file system, which may
    result in some extra files being backed up, but there shouldn\'t be
    any data loss.

15. **[Where does rdiff-backup need free space and how much is required?
    What is the problem when rdiff-backup says
    \"`ValueError: Incorrect length of data produced`\"?]{#free_space}**

    When backing up, rdiff-backup needs free space in the mirror
    directory. The amount of free space required is usually a bit more
    than the size of the file getting backed up, but can be as much as
    twice the size of the current file. For instance, suppose you ran
    `rdiff-backup foo bar` and the largest file, `foo/largefile`, was
    1GB. Then rdiff-backup would need 1+GB of free space in the `bar`
    directory.

    When restoring or regressing, rdiff-backup needs free space in the
    default temp directory. Under unix systems this is usually the
    `/tmp` directory. The temp directory that rdiff-backup uses can be
    set using the `--tempdir` and `--remote-tempdir` options available
    in versions 1.1.13 and newer. See the entry for `tempfile.tempdir`
    in the [Python tempfile
    docs](https://docs.python.org/3/library/tempfile.html) for more
    information on the default temp directory. The amount of free space
    required can vary, but it usually about the size of the largest file
    being restored.

    Usually free space errors are intelligible, like
    `IOError: [Errno 28] No space left on device` or similar. However,
    due to a gzip quirk they may look like
    `ValueError: Incorrect length of data produced`.

16. **[What does \"internal error: job made no progress\"
    mean?]{#librsync_bug}**

    This error happens due to a bug in `librsync` that prevents it from
    handling files greater than 4 GB in some situations, such as when
    transferring between a 32-bit host and a 64-bit host. [A patch is
    available](https://sourceforge.net/tracker/index.php?func=detail&aid=1439412&group_id=56125&atid=479441)
    from the librsync project page on Sourceforge. The [CVS
    version](https://sourceforge.net/cvs/?group_id=56125) of librsync
    also contains the patch. More information is also available in
    [Debian bug report
    \#355178](https://bugs.debian.org/cgi-bin/bugreport.cgi?bug=355178).

17. **[Why does rdiff-backup say it\'s not in my \$PATH? It is when I
    login!]{#path}**

    If you get an error like
    `sh: line1: rdiff-backup: command not found`, but rdiff-backup *is*
    in your `$PATH` when you login to the remote host, it is happening
    because the value of bash\'s `$PATH` is set differently when you
    login to an interactive shell than when you run a command remotely
    via SSH. For more information, read the [bash
    manpage](https://linux.die.net/man/1/bash) and look at your
    `.bashrc` and `.bash_profile` files.

    In particular, this can happen if rdiff-backup was installed via
    Fink on a remote Mac OS X system. `/sw/bin` is magically added to
    your `$PATH` by the script `/sw/bin/init.sh` when you login with an
    interactive shell. Fink did this behind the scenes when you set it
    up. Simply add `/sw/bin` to your path manually, or copy rdiff-backup
    to a directory that is in your `$PATH`.

18. **[What does \"`touple index out of range`\" mean?]{#touple}**

    If you see the error \"`tuple index out of range`\" after running a
    command like:\
    \
    `$ rdiff-backup -l /path/to/backup/rdiff-backup-data/`\
    \
    then the solution is to simply remove the extra
    \"rdiff-backup-data\" from the end of the path. The list increments
    option, and others like it, take the path to the repository, not the
    path to the rdiff-backup-data directory. In the above example, you
    should run again with:\
    \
    `$ rdiff-backup -l /path/to/backup`\
    \
    If you get this error message for an unrelated reason, try
    contacting the mailing list.

19. **[What does \"`IO Error: CRC check failed`\" mean?]{#crc}**

    This error message means that a [Cyclic Redundancy
    Check](https://en.wikipedia.org/wiki/Cyclic_redundancy_check) failed
    during some operation, most likely while gzip\'ing or un-gzip\'ing a
    file. Possible causes of this error include an incomplete gzip
    operation, and hardware failure. A brute-force way to recover from
    this error is to remove the rdiff-backup-data directory. However,
    this will remove all of your past increments. A better approach may
    be to delete the particular file that is causing the problem. A
    command like:\
    \
    `$ find rdiff-backup-data -type f -name \*.gz -print0 | xargs -0r gzip --test`\
    \
    will find the failing file. For more information on this approach,
    see this mailing list post:
    <https://lists.nongnu.org/archive/html/rdiff-backup-users/2007-11/msg00008.html>.

20. **[What does \"`AssertionError: Bad index order`\"
    mean?]{#badindex}**

    If rdiff-backup fails with the message
    \"`AssertionError: Bad index order`,\" it could be because the files
    in a directory have changed while rdiff-backup is running. Possible
    ways of dealing with this situation include implementing filesystem
    snapshots using the volume manager, excluding the offending
    directory, or suspending the process that is changing the directory.
    After the text \"Bad index order\", the error message will indicate
    which files have caused the problem.

    If you get this message for an unrelated reason, try contacting the
    mailing list.

21. **[How can rdiff-backup use UTC as the timezone?]{#utc}**

    Like other Unix and Python programs, rdiff-backup respects the `TZ`
    environment variable, which can be used to temporarily change the
    timezone. On Unix, simply set `TZ=UTC` either in your shell, or on
    the command line used to run rdiff-backup. On Windows, the command
    `USE TZ=UTC` sets the `%TZ%` environment variable, and can be used
    either in a batch script, or at the DOS prompt.
