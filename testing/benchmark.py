import sys, time
from commontest import *
from rdiff_backup import rpath, Globals

"""benchmark.py

When possible, use 'rdiff-backup' from the shell, which allows using
different versions of rdiff-backup by altering the PYTHONPATH.  We
just use clock time, so this isn't exact at all.

"""

output_desc = abs_output_dir
new_pythonpath = None

def run_cmd(cmd):
	"""Run the given cmd, return the amount of time it took"""
	time.sleep(1)  # just to be sure to not have the infamous message
	# Fatal Error: Time of Last backup is not in the past.  This is probably caused
	# by running two backups in less than a second.  Wait a second and try again.
	if new_pythonpath: full_cmd = "PYTHONPATH=%s %s" % (new_pythonpath, cmd)
	else: full_cmd = cmd
	print("Running command '%s'" % (full_cmd,))
	t = time.time()
	assert not os.system(full_cmd)
	return time.time() - t


def create_many_files(dirname, s, count = 1000):
	"""Create many short files in the dirname directory

	There will be count files in the directory, and each file will
	contain the string s.

	"""
	dir_rp = rpath.RPath(Globals.local_connection, dirname)
	if (not dir_rp.isdir()): dir_rp.mkdir()
	for i in range(count):
		rp = dir_rp.append("file_%d" % i)
		fp = rp.open("w")
		fp.write(s)
		assert not fp.close()

def create_nested(dirname, s, depth, branch_factor = 10):
	"""Create many short files in branching directory"""
	def write(rp):
		fp = rp.open("w")
		fp.write(s)
		assert not fp.close()

	def helper(rp, depth):
		if (not rp.isdir()): rp.mkdir()
		sub_rps = [rp.append("file_%d" % i) for i in range(branch_factor)]
		if depth == 1: list(map(write, sub_rps))
		else: list(map(lambda rp: helper(rp, depth-1), sub_rps))

	nestedout_dir = re_init_subdir(abs_test_dir, 'nested_out')
	helper(rpath.RPath(Globals.local_connection, dirname), depth)

def benchmark(backup_cmd, restore_cmd, desc, update_func = None):
	"""Print benchmark using backup_cmd and restore_cmd

	If update_func is given, run it and then do backup a third time.

	"""
	print("Initially backing up %s: %ss" % (desc, run_cmd(backup_cmd)))
	print("Updating %s, no change: %ss" % (desc, run_cmd(backup_cmd)))

	if update_func:
		update_func()
		print("Updating %s, all changed: %ss" % (desc, run_cmd(backup_cmd)))

	restout_dir = re_init_subdir(abs_test_dir, 'rest_out')
	print("Restoring %s to empty dir: %ss" % (desc, run_cmd(restore_cmd)))
	print("Restoring %s to unchanged dir: %ss" % (desc, run_cmd(restore_cmd)))

def many_files():
	"""Time backup and restore of 2000 files"""
	count = 2000
	manyout_dir = re_init_subdir(abs_test_dir, 'many_out')
	restout_dir = re_init_subdir(abs_test_dir, 'rest_out')
	create_many_files(manyout_dir, "a", count)
	backup_cmd = "rdiff-backup '%s' '%s'" % (manyout_dir, output_desc)
	restore_cmd = "rdiff-backup --force -r now '%s' '%s'" % \
				  (output_desc, restout_dir)
	update_func = lambda: create_many_files(manyout_dir, "e", count)
	benchmark(backup_cmd, restore_cmd, "2000 1-byte files", update_func)

def many_files_rsync():
	"""Test rsync benchmark"""
	count = 2000
	manyout_dir = re_init_subdir(abs_test_dir, 'many_out')
	create_many_files(manyout_dir, "a", count)
	rsync_command = "rsync -e ssh -aH --delete '%s' '%s'" % \
					 (manyout_dir, output_desc)
	print("Initial rsync: %ss" % (run_cmd(rsync_command),))
	print("rsync update: %ss" % (run_cmd(rsync_command),))

	create_many_files(manyout_dir, "e", count)
	print("Update changed rsync: %ss" % (run_cmd(rsync_command),))

def nested_files():
	"""Time backup and restore of 10000 nested files"""
	depth = 4
	nestedout_dir = re_init_subdir(abs_test_dir, 'nested_out')
	restout_dir = re_init_subdir(abs_test_dir, 'rest_out')
	create_nested(nestedout_dir, "a", depth)
	backup_cmd = "rdiff-backup '%s' '%s'" % (nestedout_dir, output_desc)
	restore_cmd = "rdiff-backup --force -r now '%s' '%s'" % \
				  (output_desc, restout_dir)
	update_func = lambda: create_nested(nestedout_dir, "e", depth)
	benchmark(backup_cmd, restore_cmd, "10000 1-byte nested files",
			  update_func)

def nested_files_rsync():
	"""Test rsync on nested files"""
	depth = 4
	nestedout_dir = re_init_subdir(abs_test_dir, 'nested_out')
	create_nested(nestedout_dir, "a", depth)
	rsync_command = "rsync -e ssh -aH --delete '%s' '%s'" % \
					(nestedout_dir, output_desc)
	print("Initial rsync: %ss" % (run_cmd(rsync_command),))
	print("rsync update: %ss" % (run_cmd(rsync_command),))

	create_nested(nestedout_dir, "e", depth)
	print("Update changed rsync: %ss" % (run_cmd(rsync_command),))

if len(sys.argv) < 2 or len(sys.argv) > 3:
	print("Syntax:  benchmark.py benchmark_func [output_description]")
	print("")
	print("Where output_description defaults to '%s'." % abs_output_dir)
	print("Currently benchmark_func includes:")
	print("'many_files', 'many_files_rsync', and, 'nested_files'.")
	sys.exit(1)

if len(sys.argv) == 3:
	output_desc = sys.argv[2]
	if ":" not in output_desc:  # file is local
		assert not rpath.RPath(Globals.local_connection, output_desc).lstat(), \
		   "Outfile file '%s' exists, try deleting it first." % (output_desc,)
else:   # we assume we can always remove the default output directory
	Myrm(output_desc)


if 'BENCHMARKPYPATH' in os.environ:
	new_pythonpath = os.environ['BENCHMARKPYPATH']

function_name = sys.argv[1]
print("Running ", function_name)
eval(sys.argv[1])()
