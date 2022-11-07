"""commontest - Some functions and constants common to several test cases.
Can be called also directly to setup the test environment"""
import os
import sys
import code
import shlex
import shutil
import subprocess
from rdiff_backup import (
    Globals, Hardlink, hash, log, Main, rorpiter, rpath,
    Security, selection, SetConnections
)
from rdiffbackup import actions, run
from rdiffbackup.meta import ea, acl_posix

RBBin = os.fsencode(shutil.which("rdiff-backup") or "rdiff-backup")

# Working directory is defined by Tox, venv or the current build directory
abs_work_dir = os.fsencode(os.getenv(
    'TOX_ENV_DIR',
    os.getenv('VIRTUAL_ENV', os.path.join(os.getcwd(), 'build'))))
abs_test_dir = os.path.join(abs_work_dir, b'testfiles')
abs_output_dir = os.path.join(abs_test_dir, b'output')
abs_restore_dir = os.path.join(abs_test_dir, b'restore')

# the directory with the testfiles used as input is in the parent directory of the Git clone
old_test_dir = os.path.join(os.path.dirname(os.getcwdb()),
                            b'rdiff-backup_testfiles')
old_inc1_dir = os.path.join(old_test_dir, b'increment1')
old_inc2_dir = os.path.join(old_test_dir, b'increment2')
old_inc3_dir = os.path.join(old_test_dir, b'increment3')
old_inc4_dir = os.path.join(old_test_dir, b'increment4')

# the directory in which all testing scripts are placed is the one
abs_testing_dir = os.path.dirname(os.path.abspath(os.fsencode(sys.argv[0])))

__no_execute__ = 1  # Keeps the actual rdiff-backup program from running

if os.name == "nt":
    Globals.use_compatible_timestamps = 1
    CMD_SEP = b" & "
else:
    CMD_SEP = b" ; "


def Myrm(dirstring):
    """Run myrm on given directory string"""
    root_rp = rpath.RPath(Globals.local_connection, dirstring)
    for rp in selection.Select(root_rp).get_select_iter():
        if rp.isdir():
            rp.chmod(0o700)  # otherwise may not be able to remove
        elif rp.isreg():
            rp.chmod(0o600)  # Windows can't remove read-only files
    path = root_rp.path
    if os.path.isdir(path):
        shutil.rmtree(path)
    elif os.path.isfile(path):
        os.remove(path)


def re_init_rpath_dir(rp, uid=-1, gid=-1):
    """Delete directory if present, then recreate"""
    if rp.lstat():
        Myrm(rp.path)
        rp.setdata()
    rp.mkdir()
    if os.name != "nt":
        rp.chown(uid, gid)


def re_init_subdir(maindir, subdir):
    """Remove a sub-directory and return its name joined
    to the main directory as an empty directory"""
    dir = os.path.join(maindir, subdir)
    Myrm(dir)
    os.makedirs(dir)
    return dir


# two temporary directories to simulate remote actions
abs_remote1_dir = re_init_subdir(abs_test_dir, b'remote1')
abs_remote2_dir = re_init_subdir(abs_test_dir, b'remote2')


def MakeOutputDir():
    """Initialize the output directory"""
    Myrm(abs_output_dir)
    rp = rpath.RPath(Globals.local_connection, abs_output_dir)
    rp.mkdir()
    return rp


def rdiff_backup(source_local,
                 dest_local,
                 src_dir,
                 dest_dir,
                 current_time=None,
                 extra_options=b"",
                 input=None,
                 expected_ret_code=0):
    """Run rdiff-backup with the given options

    source_local and dest_local are boolean values.  If either is
    false, then rdiff-backup will be run pretending that src_dir and
    dest_dir, respectively, are remote.  The server process will be
    run in directories remote1 and remote2 respectively.

    src_dir and dest_dir are the source and destination
    (mirror) directories, relative to the testing directory.

    If current time is true, add the --current-time option with the
    given number of seconds.

    extra_options are just added to the command line.

    If expected_ret_code is set to None, no return value comparaison is done.
    """
    remote_exec = CMD_SEP.join([b'"cd %s', b'%s server::%s"'])

    if not source_local:
        src_dir = (remote_exec % (abs_remote1_dir, RBBin, src_dir))
    if dest_dir and not dest_local:
        dest_dir = (remote_exec % (abs_remote2_dir, RBBin, dest_dir))

    cmdargs = [RBBin, extra_options]
    if not (source_local and dest_local):
        cmdargs.append(b"--remote-schema {h}")

    if current_time:
        cmdargs.append(b"--current-time %i" % current_time)
    cmdargs.append(src_dir)
    if dest_dir:
        cmdargs.append(dest_dir)
    cmdline = b" ".join(cmdargs)
    print("Executing: ", " ".join(map(shlex.quote, map(os.fsdecode, cmdargs))))
    ret_val = os_system(cmdline, input=input, universal_newlines=False)
    if expected_ret_code is not None:
        assert (expected_ret_code == ret_val), \
            "Return code %d of command `%a` isn't as expected %d." % \
            (ret_val, cmdline, expected_ret_code)
    return ret_val


def rdiff_backup_action(source_local, dest_local,
                        src_dir, dest_dir,
                        generic_opts, action, specific_opts,
                        std_input=None, return_stdout=False):
    """
    Run rdiff-backup with the given action and options, faking remote locations

    source_local and dest_local are boolean values.  If either is
    false, then rdiff-backup will be run pretending that src_dir and
    dest_dir, respectively, are remote.  The server process will be
    run in directories remote1 and remote2 respectively.

    src_dir and dest_dir are the source and destination
    (mirror) directories.

    generic_opts and specific_opts are added before/after the action.

    The std_input parameter is optional and used to provide the call to
    rdiff-backup with pre-defined input.
    """
    remote_exec = CMD_SEP.join([b"cd %s", b"%s server::%s"])

    if src_dir and not source_local:
        src_dir = (remote_exec % (abs_remote1_dir, RBBin, src_dir))
    if dest_dir and not dest_local:
        dest_dir = (remote_exec % (abs_remote2_dir, RBBin, dest_dir))

    if not (source_local and dest_local):
        generic_opts = list(generic_opts) + [b"--remote-schema", b"{h}"]

    cmdargs = [RBBin] + list(generic_opts) + [action] + list(specific_opts)

    if src_dir:
        cmdargs.append(src_dir)
    if dest_dir:
        cmdargs.append(dest_dir)
    print("Executing: ", " ".join(map(shlex.quote, map(os.fsdecode, cmdargs))))
    if return_stdout:
        try:
            ret_val = subprocess.check_output(cmdargs, input=std_input,
                                              universal_newlines=False)
        except subprocess.CalledProcessError as exc:
            ret_val = exc.output
        # normalize line endings under Windows
        if os.name == "nt":
            ret_val = ret_val.replace(b"\r\n", b"\n")
    else:
        ret_val = os_system(cmdargs, input=std_input, universal_newlines=False)
    return ret_val


def _get_locations(src_local, dest_local, src_dir, dest_dir):
    """
    Return a tuple of remote or local source and destination locations
    """
    if os.name == "nt":
        remote_location = "cd {rdir} & {tdir}\\server.py::{dir}"
    else:
        remote_location = "cd {rdir}; {tdir}/server.py::{dir}"

    if not src_local:
        src_dir = remote_location.format(
            rdir=os.fsdecode(abs_remote1_dir),
            tdir=os.fsdecode(abs_testing_dir),
            dir=os.fsdecode(src_dir))
    else:
        src_dir = os.fsdecode(src_dir)
    if not dest_local:
        dest_dir = remote_location.format(
            rdir=os.fsdecode(abs_remote2_dir),
            tdir=os.fsdecode(abs_testing_dir),
            dir=os.fsdecode(dest_dir))
    else:
        dest_dir = os.fsdecode(dest_dir)
    return (src_dir, dest_dir)


def _internal_get_cmd_pairs(src_local, dest_local, src_dir, dest_dir):
    """Function returns a tuple of connections based on the given parameters.
    One or both directories are faked for remote connection if not local,
    and the connections are set accordingly.
    Note that the function relies on the global variables
    abs_remote1_dir, abs_remote2_dir and abs_testing_dir."""

    remote_schema = b'%s'  # compat200: replace with {h}
    remote_format = b"cd %s; %s/server.py::%s"

    if not src_local:
        src_dir = remote_format % (abs_remote1_dir, abs_testing_dir, src_dir)
    if not dest_local:
        dest_dir = remote_format % (abs_remote2_dir, abs_testing_dir, dest_dir)

    if src_local and dest_local:
        return SetConnections.get_cmd_pairs([src_dir, dest_dir])
    else:
        return SetConnections.get_cmd_pairs([src_dir, dest_dir], remote_schema)


def InternalBackup(source_local,
                   dest_local,
                   src_dir,
                   dest_dir,
                   current_time=None,
                   eas=None,
                   acls=None,
                   force=False):
    """Backup src to dest internally

    This is like rdiff_backup but instead of running a separate
    rdiff-backup script, use the separate *.py files.  This way the
    script doesn't have to be rebuild constantly, and stacktraces have
    correct line/file references.

    """
    args = []
    if current_time is not None:
        args.append("--current-time")
        args.append(str(current_time))
    if not (source_local and dest_local):
        args.append("--remote-schema")
        args.append("{h}")
    if force:
        args.append("--force")
    args.append("backup")
    if eas:
        args.append("--eas")
    else:
        args.append("--no-eas")
    if acls:
        args.append("--acls")
    else:
        args.append("--no-acls")

    args.extend(_get_locations(source_local, dest_local, src_dir, dest_dir))

    run.main_run(args, security_override=True)


def InternalMirror(source_local, dest_local, src_dir, dest_dir, force=False):
    """
    Mirror src to dest internally

    like InternalBackup, but only mirror.  Do this through
    InternalBackup, but then delete rdiff-backup-data directory.
    """
    # Save attributes of root to restore later
    src_root = rpath.RPath(Globals.local_connection, src_dir)
    dest_root = rpath.RPath(Globals.local_connection, dest_dir)
    dest_rbdir = dest_root.append("rdiff-backup-data")

    InternalBackup(source_local, dest_local, src_dir, dest_dir, force=force)
    dest_root.setdata()
    Myrm(dest_rbdir.path)
    # Restore old attributes
    rpath.copy_attribs(src_root, dest_root)


def InternalRestore(mirror_local,
                    dest_local,
                    mirror_dir,
                    dest_dir,
                    time,
                    eas=None,
                    acls=None):
    """Restore mirror_dir to dest_dir at given time

    This will automatically find the increments.XXX.dir representing
    the time specified.  The mirror_dir and dest_dir are relative to
    the testing directory and will be modified for remote trials.

    """
    Main._restore_root_set = 0  # FIXME required?
    args = []
    args.append("--force")
    if not (mirror_local and dest_local):
        args.append("--remote-schema")
        args.append("{h}")
    args.append("restore")
    if eas:
        args.append("--eas")
    else:
        args.append("--no-eas")
    if acls:
        args.append("--acls")
    else:
        args.append("--no-acls")
    if time:
        args.append("--at")
        args.append(str(time))

    args.extend(_get_locations(mirror_local, dest_local, mirror_dir, dest_dir))

    run.main_run(args, security_override=True)


def get_increment_rp(mirror_rp, time):
    """Return increment rp matching time in seconds"""
    data_rp = mirror_rp.append("rdiff-backup-data")
    if not data_rp.isdir():
        return None
    for filename in data_rp.listdir():
        rp = data_rp.append(filename)
        if rp.isincfile() and rp.getincbase_bname() == b"increments":
            if rp.getinctime() == time:
                return rp
    return None  # Couldn't find appropriate increment


def _reset_connections(src_rp, dest_rp):
    """Reset some global connection information"""
    Security._security_level = "override"
    Globals.isbackup_reader = Globals.isbackup_writer = None
    Globals.set_all('rbdir', None)


def _hardlink_rorp_eq(src_rorp, dest_rorp):
    """Compare two files for hardlink equality, encompassing being hard-linked,
    having the same hashsum, and the same number of link counts."""
    Hardlink.add_rorp(dest_rorp)
    Hardlink.add_rorp(src_rorp, dest_rorp)
    rorp_eq = Hardlink.rorp_eq(src_rorp, dest_rorp)
    if not src_rorp.isreg() or not dest_rorp.isreg() or src_rorp.getnumlinks() == dest_rorp.getnumlinks() == 1:
        if not rorp_eq:
            log.Log("Hardlink compare error with when no links exist", 3)
            log.Log("%s: %s" % (src_rorp.index, Hardlink._get_inode_key(src_rorp)), 3)
            log.Log("%s: %s" % (dest_rorp.index, Hardlink._get_inode_key(dest_rorp)), 3)
            return False
    elif src_rorp.getnumlinks() > 1 and not Hardlink.is_linked(src_rorp):
        if rorp_eq:
            log.Log("Hardlink compare error with first linked src_rorp and no dest_rorp sha1", 3)
            log.Log("%s: %s" % (src_rorp.index, Hardlink._get_inode_key(src_rorp)), 3)
            log.Log("%s: %s" % (dest_rorp.index, Hardlink._get_inode_key(dest_rorp)), 3)
            return False
        hash.compute_sha1(dest_rorp)
        rorp_eq = Hardlink.rorp_eq(src_rorp, dest_rorp)
        if src_rorp.getnumlinks() != dest_rorp.getnumlinks():
            if rorp_eq:
                log.Log("Hardlink compare error with first linked src_rorp, with dest_rorp sha1, and with differing link counts", 3)
                log.Log("%s: %s" % (src_rorp.index, Hardlink._get_inode_key(src_rorp)), 3)
                log.Log("%s: %s" % (dest_rorp.index, Hardlink._get_inode_key(dest_rorp)), 3)
                return False
        elif not rorp_eq:
            log.Log("Hardlink compare error with first linked src_rorp, with dest_rorp sha1, and with equal link counts", 3)
            log.Log("%s: %s" % (src_rorp.index, Hardlink._get_inode_key(src_rorp)), 3)
            log.Log("%s: %s" % (dest_rorp.index, Hardlink._get_inode_key(dest_rorp)), 3)
            return False
    elif src_rorp.getnumlinks() != dest_rorp.getnumlinks():
        if rorp_eq:
            log.Log("Hardlink compare error with non-first linked src_rorp and with differing link counts", 3)
            log.Log("%s: %s" % (src_rorp.index, Hardlink._get_inode_key(src_rorp)), 3)
            log.Log("%s: %s" % (dest_rorp.index, Hardlink._get_inode_key(dest_rorp)), 3)
            return False
    elif not rorp_eq:
        log.Log("Hardlink compare error with non-first linked src_rorp and with equal link counts", 3)
        log.Log("%s: %s" % (src_rorp.index, Hardlink._get_inode_key(src_rorp)), 3)
        log.Log("%s: %s" % (dest_rorp.index, Hardlink._get_inode_key(dest_rorp)), 3)
        return False
    Hardlink.del_rorp(src_rorp)
    Hardlink.del_rorp(dest_rorp)
    return True


def _ea_compare_rps(rp1, rp2):
    """Return true if rp1 and rp2 have same extended attributes."""
    ea1 = ea.ExtendedAttributes(rp1.index)
    ea1.read_from_rp(rp1)
    ea2 = ea.ExtendedAttributes(rp2.index)
    ea2.read_from_rp(rp2)
    return ea1 == ea2


def _acl_compare_rps(rp1, rp2):
    """Return true if rp1 and rp2 have same acl information."""
    acl1 = acl_posix.AccessControlLists(rp1.index)
    acl1.read_from_rp(rp1)
    acl2 = acl_posix.AccessControlLists(rp2.index)
    acl2.read_from_rp(rp2)
    return acl1 == acl2


def _files_rorp_eq(src_rorp, dest_rorp,
                   compare_hardlinks=True,
                   compare_symlinks=None,
                   compare_ownership=False,
                   compare_eas=False,
                   compare_acls=False):
    """Combined eq func returns true if two files compare same"""
    # default value depends on OS, symlinks aren't supported under Windows
    if compare_symlinks is None:
        compare_symlinks = (os.name != "nt")
    if not compare_symlinks:
        if (src_rorp and src_rorp.issym()
                or dest_rorp and dest_rorp.issym()):
            return True
    if not src_rorp:
        log.Log("Source rorp missing: %s" % str(dest_rorp), 3)
        return False
    if not dest_rorp:
        log.Log("Dest rorp missing: %s" % str(src_rorp), 3)
        return False
    if not src_rorp._equal_verbose(dest_rorp,
                                   compare_ownership=compare_ownership):
        return False
    if compare_hardlinks and not _hardlink_rorp_eq(src_rorp, dest_rorp):
        return False
    if compare_eas and not _ea_compare_rps(src_rorp, dest_rorp):
        log.Log(
            "Different EAs in files %s and %s" %
            (src_rorp.get_indexpath(), dest_rorp.get_indexpath()), 3)
        return False
    if compare_acls and not _acl_compare_rps(src_rorp, dest_rorp):
        log.Log(
            "Different ACLs in files %s and %s" %
            (src_rorp.get_indexpath(), dest_rorp.get_indexpath()), 3)
        return False
    return True


def _get_selection_functions(src_rp, dest_rp,
                             exclude_rbdir=True,
                             ignore_tmp_files=False):
    """Return generators of files in source, dest"""
    src_rp.setdata()
    dest_rp.setdata()
    src_select = selection.Select(src_rp)
    dest_select = selection.Select(dest_rp)

    if ignore_tmp_files:
        # Ignoring temp files can be useful when we want to check the
        # correctness of a backup which aborted in the middle.  In
        # these cases it is OK to have tmp files lying around.
        src_select._add_selection_func(
            src_select._regexp_get_sf(".*rdiff-backup.tmp.[^/]+$", 0))
        dest_select._add_selection_func(
            dest_select._regexp_get_sf(".*rdiff-backup.tmp.[^/]+$", 0))

    if exclude_rbdir:  # Exclude rdiff-backup-data directory
        src_select.parse_rbdir_exclude()
        dest_select.parse_rbdir_exclude()

    return src_select.get_select_iter(), dest_select.get_select_iter()


def compare_recursive(src_rp, dest_rp,
                      compare_hardlinks=True,
                      exclude_rbdir=True,
                      ignore_tmp_files=False,
                      compare_ownership=False,
                      compare_eas=False,
                      compare_acls=False):
    """Compare src_rp and dest_rp, which can be directories

    This only compares file attributes, not the actual data.  This
    will overwrite the hardlink dictionaries if compare_hardlinks is
    specified.

    """

    log.Log(
        "Comparing {srp} and {drp}, hardlinks {chl}, "
        "eas {cea}, acls {cacl}".format(
            srp=src_rp, drp=dest_rp, chl=compare_hardlinks,
            cea=compare_eas, cacl=compare_acls), 3)
    if compare_hardlinks:
        reset_hardlink_dicts()
    src_iter, dest_iter = _get_selection_functions(
        src_rp, dest_rp,
        exclude_rbdir=exclude_rbdir,
        ignore_tmp_files=ignore_tmp_files)
    for src_rorp, dest_rorp in rorpiter.Collate2Iters(src_iter, dest_iter):
        if not _files_rorp_eq(src_rorp, dest_rorp,
                              compare_hardlinks=compare_hardlinks,
                              compare_ownership=compare_ownership,
                              compare_eas=compare_eas,
                              compare_acls=compare_acls):
            return 0
    return 1


def reset_hardlink_dicts():
    """Clear the hardlink dictionaries"""
    Hardlink._inode_index = {}


def BackupRestoreSeries(source_local,
                        dest_local,
                        list_of_dirnames,
                        compare_hardlinks=1,
                        dest_dirname=abs_output_dir,
                        restore_dirname=abs_restore_dir,
                        compare_backups=1,
                        compare_eas=0,
                        compare_acls=0,
                        compare_ownership=0):
    """Test backing up/restoring of a series of directories

    The dirnames correspond to a single directory at different times.
    After each backup, the dest dir will be compared.  After the whole
    set, each of the earlier directories will be recovered to the
    restore_dirname and compared.

    """
    Globals.set('preserve_hardlinks', compare_hardlinks)
    Globals.set("no_compression_regexp_string",
                os.fsencode(actions.DEFAULT_NOT_COMPRESSED_REGEXP))
    time = 10000
    dest_rp = rpath.RPath(Globals.local_connection, dest_dirname)
    restore_rp = rpath.RPath(Globals.local_connection, restore_dirname)

    Myrm(dest_dirname)
    for dirname in list_of_dirnames:
        src_rp = rpath.RPath(Globals.local_connection, dirname)
        reset_hardlink_dicts()
        _reset_connections(src_rp, dest_rp)

        InternalBackup(source_local,
                       dest_local,
                       dirname,
                       dest_dirname,
                       time,
                       eas=compare_eas,
                       acls=compare_acls)
        time += 10000
        _reset_connections(src_rp, dest_rp)
        if compare_backups:
            assert compare_recursive(src_rp,
                                     dest_rp,
                                     compare_hardlinks,
                                     compare_eas=compare_eas,
                                     compare_acls=compare_acls,
                                     compare_ownership=compare_ownership)

    time = 10000
    for dirname in list_of_dirnames[:-1]:
        reset_hardlink_dicts()
        Myrm(restore_dirname)
        InternalRestore(dest_local,
                        source_local,
                        dest_dirname,
                        restore_dirname,
                        time,
                        eas=compare_eas,
                        acls=compare_acls)
        src_rp = rpath.RPath(Globals.local_connection, dirname)
        assert compare_recursive(src_rp,
                                 restore_rp,
                                 compare_eas=compare_eas,
                                 compare_acls=compare_acls,
                                 compare_ownership=compare_ownership)

        # Restore should default back to newest time older than it
        # with a backup then.
        if time == 20000:
            time = 21000

        time += 10000


def MirrorTest(source_local,
               dest_local,
               list_of_dirnames,
               compare_hardlinks=1,
               dest_dirname=abs_output_dir):
    """Mirror each of list_of_dirnames, and compare after each"""
    Globals.set('preserve_hardlinks', compare_hardlinks)
    Globals.set("no_compression_regexp_string",
                os.fsencode(actions.DEFAULT_NOT_COMPRESSED_REGEXP))
    dest_rp = rpath.RPath(Globals.local_connection, dest_dirname)

    Myrm(dest_dirname)
    for dirname in list_of_dirnames:
        src_rp = rpath.RPath(Globals.local_connection, dirname)
        reset_hardlink_dicts()
        _reset_connections(src_rp, dest_rp)

        InternalMirror(source_local, dest_local, dirname, dest_dirname,
                       force=True)
        _reset_connections(src_rp, dest_rp)
        assert compare_recursive(src_rp, dest_rp, compare_hardlinks)


def raise_interpreter(use_locals=None):
    """Start Python interpreter, with local variables if locals is true"""
    if use_locals:
        local_dict = locals()
    else:
        local_dict = globals()
    code.InteractiveConsole(local_dict).interact()


def getrefs(i, depth):
    """Get the i'th object in memory, return objects that reference it"""
    import sys
    import gc
    import types
    o = sys.getobjects(i)[-1]
    for d in range(depth):
        for ref in gc.get_referrers(o):
            if type(ref) in (list, dict, types.InstanceType):
                if type(ref) is dict and 'copyright' in ref:
                    continue
                o = ref
                break
        else:
            print("Max depth ", d)
            return o
    return o


def iter_equal(iter1, iter2, verbose=None, operator=lambda x, y: x == y):
    """True if iterator 1 has same elements as iterator 2

    Use equality operator, or == if it is unspecified.

    """
    for i1 in iter1:
        try:
            i2 = next(iter2)
        except StopIteration:
            if verbose:
                print("End when i1 = %s" % (i1, ))
            return False
        if not operator(i1, i2):
            if verbose:
                print("%s not equal to %s" % (i1, i2))
            return False
    try:
        i2 = next(iter2)
    except StopIteration:
        return True
    if verbose:
        print("End when i2 = %s" % (i2, ))
    return False


def iter_map(function, iterator):
    """Like map in a lazy functional programming language"""
    for i in iterator:
        yield function(i)


def os_system(cmd, **kwargs):
    """
    A wrapper function to use decoded strings instead of bytes under Windows

    It simulates os.system and returns the return code value, an integer
    """
    if isinstance(cmd, (list, tuple)):
        # as list, bytes are accepted even under Windows
        return subprocess.run(cmd, **kwargs).returncode
    else:
        if os.name == "nt":
            # bytes args is not allowed on Windows
            cmd = os.fsdecode(cmd)
        return subprocess.run(cmd, shell=True, **kwargs).returncode


def xcopytree(source, dest, content=False):
    """copytree can't copy all kind of files but is platform independent
    hence we use it only if the 'cp' utility doesn't exist.
    If content is True then dest is created if needed and
    the content of the source is copied into dest and not source itself."""
    if content:
        subs = map(lambda d: os.path.join(source, d), os.listdir(source))
        os.makedirs(dest, exist_ok=True)
    else:
        subs = (source,)
    for sub in subs:
        if shutil.which('cp'):
            os_system((b'cp', b'-a', sub, dest), check=True)
        else:
            shutil.copytree(sub, dest, symlinks=True)


if __name__ == '__main__':
    os.makedirs(abs_test_dir, exist_ok=True)
