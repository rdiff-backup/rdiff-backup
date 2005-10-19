import sys, time
from commontest import *
from rdiff_backup import rpath, Globals

"""benchmark.py

When possible, use 'rdiff-backup' from the shell, which allows using
different versions of rdiff-backup by altering the PYTHONPATH.  We
just use clock time, so this isn't exact at all.

"""

output_local = 1
output_desc = "testfiles/output"
new_pythonpath = None

def run_cmd(cmd):
	"""Run the given cmd, return the amount of time it took"""
	if new_pythonpath: full_cmd = "PYTHONPATH=%s %s" % (new_pythonpath, cmd)
	else: full_cmd = cmd
	print "Running command '%s'" % (full_cmd,)
	t = time.time()
	assert not os.system(full_cmd)
	return time.time() - t

def create_many_files(dirname, s, count = 1000):
	"""Create many short files in the dirname directory

	There will be count files in the directory, and each file will
	contain the string s.

	"""
	Myrm("testfiles/many_out")
	dir_rp = rpath.RPath(Globals.local_connection, dirname)
	dir_rp.mkdir()
	for i in xrange(count):
		rp = dir_rp.append(str(i))
		fp = rp.open("wb")
		fp.write(s)
		assert not fp.close()

def create_nested(dirname, s, depth, branch_factor = 10):
	"""Create many short files in branching directory"""
	def write(rp):
		fp = rp.open("wb")
		fp.write(s)
		assert not fp.close()

	def helper(rp, depth):
		rp.mkdir()
		sub_rps = map(lambda i: rp.append(str(i)), range(branch_factor))
		if depth == 1: map(write, sub_rps)
		else: map(lambda rp: helper(rp, depth-1), sub_rps)

	Myrm("testfiles/nested_out")
	helper(rpath.RPath(Globals.local_connection, dirname), depth)

def benchmark(backup_cmd, restore_cmd, desc, update_func = None):
	"""Print benchmark using backup_cmd and restore_cmd

	If update_func is given, run it and then do backup a third time.

	"""
	print "Initially backing up %s: %ss" % (desc, run_cmd(backup_cmd))
	print "Updating %s, no change: %ss" % (desc, run_cmd(backup_cmd))

	if update_func:
		update_func()
		print "Updating %s, all changed: %ss" % (desc, run_cmd(backup_cmd))

	Myrm("testfiles/rest_out")
	print "Restoring %s to empty dir: %ss" % (desc, run_cmd(restore_cmd))
	print "Restoring %s to unchanged dir: %ss" % (desc, run_cmd(restore_cmd))

def many_files():
	"""Time backup and restore of 2000 files"""
	count = 2000
	create_many_files("testfiles/many_out", "a", count)
	backup_cmd = "rdiff-backup testfiles/many_out " + output_desc
	restore_cmd = "rdiff-backup --force -r now %s testfiles/rest_out" % \
				  (output_desc,)
	update_func = lambda: create_many_files("testfiles/many_out", "e", count)
	benchmark(backup_cmd, restore_cmd, "2000 1-byte files", update_func)

def many_files_rsync():
	"""Test rsync benchmark"""
	count = 2000
	create_many_files("testfiles/many_out", "a", count)
	rsync_command = ("rsync -e ssh -aH --delete testfiles/many_out " +
					 output_desc)
	print "Initial rsync: %ss" % (run_cmd(rsync_command),)
	print "rsync update: %ss" % (run_cmd(rsync_command),)

	create_many_files("testfiles/many_out", "e", count)
	print "Update changed rsync: %ss" % (run_cmd(rsync_command),)

def nested_files():
	"""Time backup and restore of 10000 nested files"""
	depth = 4
	create_nested("testfiles/nested_out", "a", depth)
	backup_cmd = "rdiff-backup testfiles/nested_out " + output_desc
	restore_cmd = "rdiff-backup --force -r now %s testfiles/rest_out" % \
				  (output_desc,)
	update_func = lambda: create_nested("testfiles/nested_out", "e", depth)
	benchmark(backup_cmd, restore_cmd, "10000 1-byte nested files",
			  update_func)

def nested_files_rsync():
	"""Test rsync on nested files"""
	depth = 4
	create_nested("testfiles/nested_out", "a", depth)
	rsync_command = ("rsync -e ssh -aH --delete testfiles/nested_out " +
					 output_desc)
	print "Initial rsync: %ss" % (run_cmd(rsync_command),)
	print "rsync update: %ss" % (run_cmd(rsync_command),)

	create_nested("testfiles/nested_out", "e", depth)
	print "Update changed rsync: %ss" % (run_cmd(rsync_command),)

if len(sys.argv) < 2 or len(sys.argv) > 3:
	print "Syntax:  benchmark.py benchmark_func [output_description]"
	print
	print "Where output_description defaults to 'testfiles/output'."
	print "Currently benchmark_func includes:"
	print "'many_files', 'many_files_rsync', and, 'nested_files'."
	sys.exit(1)

if len(sys.argv) == 3:
	output_desc = sys.argv[2]
	if ":" in output_desc: output_local = None

if output_local:
	assert not rpath.RPath(Globals.local_connection, output_desc).lstat(), \
		   "Outfile file %s exists, try deleting it first" % (output_desc,)

if os.environ.has_key('BENCHMARKPYPATH'):
	new_pythonpath = os.environ['BENCHMARKPYPATH']

function_name = sys.argv[1]
print "Running ", function_name
eval(sys.argv[1])()
