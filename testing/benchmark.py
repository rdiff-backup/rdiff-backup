import os
import sys
import time
from commontest import re_init_subdir, abs_test_dir, os_system
from rdiff_backup import rpath, Globals
"""benchmark.py

When possible, use 'rdiff-backup' from the shell, which allows using
different versions of rdiff-backup by altering the PYTHONPATH.  We
just use clock time, so this isn't exact at all.

"""

new_pythonpath = None

# How many files to generate in the "many" benchmark
MANY_COUNT = 2000

# Which depth and factor to use in the "nested" benchmark
# Caution: count of files is factor**depth, it increases quickly!
NESTED_DEPTH = 4
NESTED_FACTOR = 7


def run_cmd(cmd):
    """Run the given cmd, return the amount of time it took"""
    time.sleep(1)  # just to be sure to not have the infamous message
    # Fatal Error: Time of Last backup is not in the past.  This is probably caused
    # by running two backups in less than a second.  Wait a second and try again.
    if new_pythonpath:
        full_cmd = b"PYTHONPATH=%b %b" % (new_pythonpath, cmd)
    else:
        full_cmd = cmd
    print("Running command '%s'" % (full_cmd, ))
    t = time.time()
    rc = os_system(full_cmd)
    if rc & Globals.RET_CODE_ERR:
        raise RuntimeError("Return code of '{cmd}' is '{rc}'".format(
            cmd=cmd, rc=rc))
    return time.time() - t


def create_many(dirname, s, count):
    """Create many short files in the dirname directory

    There will be count files in the directory, and each file will
    contain the string s.

    """
    dir_rp = rpath.RPath(Globals.local_connection, dirname)
    if (not dir_rp.isdir()):
        dir_rp.mkdir()
    for i in range(count):
        rp = dir_rp.append(b"file_%d" % i)
        fp = rp.open("w")
        fp.write(s)
        fp.close()


def create_nested(dirname, s, depth, branch_factor):
    """Create many short files in branching directory"""

    def write(rp):
        fp = rp.open("w")
        fp.write(s)
        fp.close()

    def helper(rp, depth):
        if (not rp.isdir()):
            rp.mkdir()
        sub_rps = [rp.append("file_%d" % i) for i in range(branch_factor)]
        if depth == 1:
            list(map(write, sub_rps))
        else:
            list(map(lambda rp: helper(rp, depth - 1), sub_rps))

    re_init_subdir(abs_test_dir, b'nested_out')
    helper(rpath.RPath(Globals.local_connection, dirname), depth)


def benchmark(backup_cmd, restore_cmd, desc, update_func=None):
    """Print benchmark using backup_cmd and restore_cmd

    If update_func is given, run it and then do backup a third time.

    """
    times_list = []
    times_list.append(run_cmd(backup_cmd))
    print("Initially backing up %s: %ss" % (desc, times_list[-1]))
    times_list.append(run_cmd(backup_cmd))
    print("Updating %s, no change: %ss" % (desc, times_list[-1]))

    if update_func:
        update_func()
        times_list.append(run_cmd(backup_cmd))
        print("Updating %s, all changed: %ss" % (desc, times_list[-1]))

    re_init_subdir(abs_test_dir, b'rest_out')
    times_list.append(run_cmd(restore_cmd))
    print("Restoring %s to empty dir: %ss" % (desc, times_list[-1]))
    times_list.append(run_cmd(restore_cmd))
    print("Restoring %s to unchanged dir: %ss" % (desc, times_list[-1]))

    return times_list


def many(backup, restore, many_count=MANY_COUNT):
    """Time backup and restore of many_count files"""
    manyout_dir = re_init_subdir(abs_test_dir, b'many_out')
    backout_dir = re_init_subdir(abs_test_dir, b'back_out')
    restout_dir = re_init_subdir(abs_test_dir, b'rest_out')
    create_many(manyout_dir, "a", many_count)
    backup_cmd = backup % (manyout_dir, backout_dir)
    restore_cmd = restore % (backout_dir, restout_dir)

    def update_func():
        create_many(manyout_dir, "e", many_count)

    return benchmark(backup_cmd, restore_cmd, "{count} 1-byte files".format(
        count=many_count), update_func)


def nested(backup, restore, nested_depth=NESTED_DEPTH, nested_factor=NESTED_FACTOR):
    """Time backup and restore of factor**depth nested files"""
    nestedout_dir = re_init_subdir(abs_test_dir, b'nested_out')
    backout_dir = re_init_subdir(abs_test_dir, b'back_out')
    restout_dir = re_init_subdir(abs_test_dir, b'rest_out')
    create_nested(nestedout_dir, "a", nested_depth, nested_factor)
    backup_cmd = backup % (nestedout_dir, backout_dir)
    restore_cmd = restore % (backout_dir, restout_dir)

    def update_func():
        create_nested(nestedout_dir, "e", nested_depth, nested_factor)

    nested_count = nested_factor**nested_depth
    return benchmark(
        backup_cmd, restore_cmd, "{count} 1-byte nested files".format(
            count=nested_count), update_func)


def print_results(bench, results):
    """Print a table with the absolute and relative results"""
    func_names = list(map(lambda x: x['name'], bench))
    names_width = max(list(map(len, func_names)))

    for ires in range(len(bench)):
        sys.stdout.write("{name:{width}};".format(name=func_names[ires],
                                                  width=names_width))
        all_results = results[ires][0:]  # deep copy
        for jres in range(len(results[0])):
            all_results.append(results[ires][jres] / results[0][jres])
        for value in all_results:
            sys.stdout.write("{val:6.3f};".format(val=value))
        print("")


# MAIN SECTION

benchmarks = {
    'many': [
        {
            'name': 'many_rsync',
            'func': many,
            'backup': b"rsync -e ssh -aH --delete '%s' '%s'",
            'restore': b"rsync -e ssh -aH --delete '%s' '%s'",
        },
        {
            'name': 'many_normal',
            'func': many,
            'backup': b"rdiff-backup '%b' '%b'",
            'restore': b"rdiff-backup --force -r now '%b' '%b'",
        },
        {
            'name': 'many_no_fsync',
            'func': many,
            'backup': b"rdiff-backup --no-fsync '%b' '%b'",
            'restore': b"rdiff-backup --no-fsync --force -r now '%b' '%b'",
        },
    ],
    'nested': [
        {
            'name': 'nested_rsync',
            'func': nested,
            'backup': b"rsync -e ssh -aH --delete '%s' '%s'",
            'restore': b"rsync -e ssh -aH --delete '%s' '%s'",
        },
        {
            'name': 'nested_normal',
            'func': nested,
            'backup': b"rdiff-backup '%b' '%b'",
            'restore': b"rdiff-backup --force -r now '%b' '%b'",
        },
        {
            'name': 'nested_no_fsync',
            'func': nested,
            'backup': b"rdiff-backup --no-fsync '%b' '%b'",
            'restore': b"rdiff-backup --no-fsync --force -r now '%b' '%b'",
        },
    ],
}

if len(sys.argv) != 2:
    print("Syntax:  benchmark.py many|nested")
    sys.exit(1)

if 'BENCHMARKPYPATH' in os.environ:
    new_pythonpath = os.fsencode(os.environ['BENCHMARKPYPATH'])

benchmark_name = sys.argv[1]
print("=== Running '{bench}' benchmark ===".format(bench=benchmark_name))
benchmark_results = []
for bench in benchmarks[benchmark_name]:
    benchmark_results.append(bench['func'](bench['backup'], bench['restore']))
print("=== Results of '{bench}' benchmark (absolute and relative) ===".format(
    bench=benchmark_name))
print_results(benchmarks[benchmark_name], benchmark_results)
