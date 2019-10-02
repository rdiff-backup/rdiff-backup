"""commontest - Some functions and constants common to several test cases.
Can be called also directly to setup the test environment"""
import os
import sys
import code
import shutil
import subprocess
# Avoid circularities
from rdiff_backup.log import Log
from rdiff_backup import Globals, Hardlink, SetConnections, Main, \
    selection, rpath, eas_acls, rorpiter, Security

RBBin = os.fsencode(shutil.which("rdiff-backup"))

# Working directory is defined by Tox, venv or the current build directory
abs_work_dir = os.getenvb(
    b'TOX_ENV_DIR',
    os.getenvb(b'VIRTUAL_ENV', os.path.join(os.getcwdb(), b'build')))
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


def Myrm(dirstring):
    """Run myrm on given directory string"""
    root_rp = rpath.RPath(Globals.local_connection, dirstring)
    for rp in selection.Select(root_rp).set_iter():
        if rp.isdir():
            rp.chmod(0o700)  # otherwise may not be able to remove
    assert not os.system(b"rm -rf %s" % (root_rp.path, ))


def re_init_rpath_dir(rp, uid=-1, gid=-1):
    """Delete directory if present, then recreate"""
    if rp.lstat():
        Myrm(rp.path)
        rp.setdata()
    rp.mkdir()
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
                 check_return_val=1,
                 expected_ret_val=0):
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

    """
    if not source_local:
        src_dir = (b"'cd %s; %s --server'::%s" %
                   (abs_remote1_dir, RBBin, src_dir))
    if dest_dir and not dest_local:
        dest_dir = (b"'cd %s; %s --server'::%s" %
                    (abs_remote2_dir, RBBin, dest_dir))

    cmdargs = [RBBin, extra_options]
    if not (source_local and dest_local):
        cmdargs.append(b"--remote-schema %s")

    if current_time:
        cmdargs.append(b"--current-time %i" % current_time)
    cmdargs.append(src_dir)
    if dest_dir:
        cmdargs.append(dest_dir)
    cmdline = b" ".join(cmdargs)
    print("Executing: ", cmdline)
    ret_val = subprocess.run(cmdline,
                             shell=True,
                             input=input,
                             universal_newlines=False).returncode
    if check_return_val:
        # the construct is needed because os.system seemingly doesn't
        # respect expected return values (FIXME)
        assert ((expected_ret_val == 0 and ret_val == 0) or (expected_ret_val > 0 and ret_val > 0)), \
            "Return code %d of command `%a` isn't expected %d." % \
            (ret_val, cmdline, expected_ret_val)
    return ret_val


def InternalBackup(source_local,
                   dest_local,
                   src_dir,
                   dest_dir,
                   current_time=None,
                   eas=None,
                   acls=None):
    """Backup src to dest internally

    This is like rdiff_backup but instead of running a separate
    rdiff-backup script, use the separate *.py files.  This way the
    script doesn't have to be rebuild constantly, and stacktraces have
    correct line/file references.

    """
    Globals.current_time = current_time
    Globals.security_level = "override"
    remote_schema = b'%s'

    if not source_local:
        src_dir = b"cd %s; %s/server.py::%s" % (abs_remote1_dir, abs_testing_dir, src_dir)
    if not dest_local:
        dest_dir = b"cd %s; %s/server.py::%s" % (abs_remote2_dir, abs_testing_dir, dest_dir)

    cmdpairs = SetConnections.get_cmd_pairs([src_dir, dest_dir], remote_schema)
    Security.initialize("backup", cmdpairs)
    rpin, rpout = list(map(SetConnections.cmdpair2rp, cmdpairs))
    for attr in ('eas_active', 'eas_write', 'eas_conn'):
        SetConnections.UpdateGlobal(attr, eas)
    for attr in ('acls_active', 'acls_write', 'acls_conn'):
        SetConnections.UpdateGlobal(attr, acls)
    Main.misc_setup([rpin, rpout])
    Main.Backup(rpin, rpout)
    Main.cleanup()


def InternalMirror(source_local, dest_local, src_dir, dest_dir):
    """Mirror src to dest internally

    like InternalBackup, but only mirror.  Do this through
    InternalBackup, but then delete rdiff-backup-data directory.

    """
    # Save attributes of root to restore later
    src_root = rpath.RPath(Globals.local_connection, src_dir)
    dest_root = rpath.RPath(Globals.local_connection, dest_dir)
    dest_rbdir = dest_root.append("rdiff-backup-data")

    InternalBackup(source_local, dest_local, src_dir, dest_dir)
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
    Main.force = 1
    Main.restore_root_set = 0
    remote_schema = b'%s'
    Globals.security_level = "override"
    if not mirror_local:
        mirror_dir = b"cd %s; %s/server.py::%s" % (abs_remote1_dir, abs_testing_dir, mirror_dir)
    if not dest_local:
        dest_dir = b"cd %s; %s/server.py::%s" % (abs_remote2_dir, abs_testing_dir, dest_dir)

    cmdpairs = SetConnections.get_cmd_pairs([mirror_dir, dest_dir],
                                            remote_schema)
    Security.initialize("restore", cmdpairs)
    mirror_rp, dest_rp = list(map(SetConnections.cmdpair2rp, cmdpairs))
    for attr in ('eas_active', 'eas_write', 'eas_conn'):
        SetConnections.UpdateGlobal(attr, eas)
    for attr in ('acls_active', 'acls_write', 'acls_conn'):
        SetConnections.UpdateGlobal(attr, acls)
    Main.misc_setup([mirror_rp, dest_rp])
    inc = get_increment_rp(mirror_rp, time)
    if inc:
        Main.Restore(get_increment_rp(mirror_rp, time), dest_rp)
    else:  # use alternate syntax
        Main.restore_timestr = str(time)
        Main.Restore(mirror_rp, dest_rp, restore_as_of=1)
    Main.cleanup()


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
    Globals.security_level = "override"
    Globals.isbackup_reader = Globals.isbackup_writer = None
    SetConnections.UpdateGlobal('rbdir', None)
    Main.misc_setup([src_rp, dest_rp])


def CompareRecursive(src_rp,
                     dest_rp,
                     compare_hardlinks=1,
                     equality_func=None,
                     exclude_rbdir=1,
                     ignore_tmp_files=None,
                     compare_ownership=0,
                     compare_eas=0,
                     compare_acls=0):
    """Compare src_rp and dest_rp, which can be directories

    This only compares file attributes, not the actual data.  This
    will overwrite the hardlink dictionaries if compare_hardlinks is
    specified.

    """

    def get_selection_functions():
        """Return generators of files in source, dest"""
        src_rp.setdata()
        dest_rp.setdata()
        src_select = selection.Select(src_rp)
        dest_select = selection.Select(dest_rp)

        if ignore_tmp_files:
            # Ignoring temp files can be useful when we want to check the
            # correctness of a backup which aborted in the middle.  In
            # these cases it is OK to have tmp files lying around.
            src_select.add_selection_func(
                src_select.regexp_get_sf(".*rdiff-backup.tmp.[^/]+$", 0))
            dest_select.add_selection_func(
                dest_select.regexp_get_sf(".*rdiff-backup.tmp.[^/]+$", 0))

        if exclude_rbdir:  # Exclude rdiff-backup-data directory
            src_select.parse_rbdir_exclude()
            dest_select.parse_rbdir_exclude()

        return src_select.set_iter(), dest_select.set_iter()

    def preprocess(src_rorp, dest_rorp):
        """Initially process src and dest_rorp"""
        if compare_hardlinks and src_rorp:
            Hardlink.add_rorp(src_rorp, dest_rorp)

    def postprocess(src_rorp, dest_rorp):
        """After comparison, process src_rorp and dest_rorp"""
        if compare_hardlinks and src_rorp:
            Hardlink.del_rorp(src_rorp)

    def equality_func(src_rorp, dest_rorp):
        """Combined eq func returns true if two files compare same"""
        if not src_rorp:
            Log("Source rorp missing: %s" % str(dest_rorp), 3)
            return 0
        if not dest_rorp:
            Log("Dest rorp missing: %s" % str(src_rorp), 3)
            return 0
        if not src_rorp.equal_verbose(dest_rorp,
                                      compare_ownership=compare_ownership):
            return 0
        if compare_hardlinks and not Hardlink.rorp_eq(src_rorp, dest_rorp):
            Log("Hardlink compare failure", 3)
            Log("%s: %s" % (src_rorp.index, Hardlink.get_inode_key(src_rorp)), 3)
            Log("%s: %s" % (dest_rorp.index, Hardlink.get_inode_key(dest_rorp)), 3)
            return 0
        if compare_eas and not eas_acls.ea_compare_rps(src_rorp, dest_rorp):
            Log(
                "Different EAs in files %s and %s" %
                (src_rorp.get_indexpath(), dest_rorp.get_indexpath()), 3)
            return 0
        if compare_acls and not eas_acls.acl_compare_rps(src_rorp, dest_rorp):
            Log(
                "Different ACLs in files %s and %s" %
                (src_rorp.get_indexpath(), dest_rorp.get_indexpath()), 3)
            return 0
        return 1

    Log(
        "Comparing %s and %s, hardlinks %s, eas %s, acls %s" %
        (src_rp.get_safepath(), dest_rp.get_safepath(), compare_hardlinks,
         compare_eas, compare_acls), 3)
    if compare_hardlinks:
        reset_hardlink_dicts()
    src_iter, dest_iter = get_selection_functions()
    for src_rorp, dest_rorp in rorpiter.Collate2Iters(src_iter, dest_iter):
        preprocess(src_rorp, dest_rorp)
        if not equality_func(src_rorp, dest_rorp):
            return 0
        postprocess(src_rorp, dest_rorp)
    return 1

    def rbdir_equal(src_rorp, dest_rorp):
        """Like hardlink_equal, but make allowances for data directories"""
        if not src_rorp.index and not dest_rorp.index:
            return 1
        if (src_rorp.index and src_rorp.index[0] == 'rdiff-backup-data' and src_rorp.index == dest_rorp.index):
            # Don't compare dirs - they don't carry significant info
            if dest_rorp.isdir() and src_rorp.isdir():
                return 1
            if dest_rorp.isreg() and src_rorp.isreg():
                # Don't compare gzipped files because it is apparently
                # non-deterministic.
                if dest_rorp.index[-1].endswith('gz'):
                    return 1
                # Don't compare .missing increments because they don't matter
                if dest_rorp.index[-1].endswith('.missing'):
                    return 1
        if compare_eas and not eas_acls.ea_compare_rps(src_rorp, dest_rorp):
            Log("Different EAs in files %s and %s" %
                (src_rorp.get_indexpath(), dest_rorp.get_indexpath()))
            return None
        if compare_acls and not eas_acls.acl_compare_rps(src_rorp, dest_rorp):
            Log(
                "Different ACLs in files %s and %s" %
                (src_rorp.get_indexpath(), dest_rorp.get_indexpath()), 3)
            return None
        if compare_hardlinks:
            if Hardlink.rorp_eq(src_rorp, dest_rorp):
                return 1
        elif src_rorp.equal_verbose(dest_rorp,
                                    compare_ownership=compare_ownership):
            return 1
        Log("%s: %s" % (src_rorp.index, Hardlink.get_inode_key(src_rorp)), 3)
        Log("%s: %s" % (dest_rorp.index, Hardlink.get_inode_key(dest_rorp)), 3)
        return None


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
            assert CompareRecursive(src_rp,
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
        assert CompareRecursive(src_rp,
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
    dest_rp = rpath.RPath(Globals.local_connection, dest_dirname)
    old_force_val = Main.force
    Main.force = 1

    Myrm(dest_dirname)
    for dirname in list_of_dirnames:
        src_rp = rpath.RPath(Globals.local_connection, dirname)
        reset_hardlink_dicts()
        _reset_connections(src_rp, dest_rp)

        InternalMirror(source_local, dest_local, dirname, dest_dirname)
        _reset_connections(src_rp, dest_rp)
        assert CompareRecursive(src_rp, dest_rp, compare_hardlinks)
    Main.force = old_force_val


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


if __name__ == '__main__':
    os.makedirs(abs_test_dir, exist_ok=True)
