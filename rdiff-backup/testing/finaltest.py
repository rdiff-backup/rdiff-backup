import unittest, os, re, sys
execfile("commontest.py")
rbexec("restore.py")

"""Regression tests"""

Globals.exclude_mirror_regexps = [re.compile(".*/rdiff-backup-data")]
Log.setverbosity(7)
Make()

lc = Globals.local_connection

class Local:
	"""This is just a place to put increments relative to the local
	connection"""
	def get_local_rp(extension):
		return RPath(Globals.local_connection, "testfiles/" + extension)

	inc1rp = get_local_rp('increment1')
	inc2rp = get_local_rp('increment2')
	inc3rp = get_local_rp('increment3')
	inc4rp = get_local_rp('increment4')

	rpout = get_local_rp('output')
	rpout_inc = get_local_rp('output_inc')
	rpout1 = get_local_rp('restoretarget1')
	rpout2 = get_local_rp('restoretarget2')
	rpout3 = get_local_rp('restoretarget3')
	rpout4 = get_local_rp('restoretarget4')

	prefix = get_local_rp('.')

	vft_in = get_local_rp('vft_out')
	vft_out = get_local_rp('increment2/various_file_types')

	timbar_in = get_local_rp('increment1/timbar.pyc')
	timbar_out = get_local_rp('../timbar.pyc') # in cur directory

class PathSetter(unittest.TestCase):
	def setUp(self):
		self.rb_schema = SourceDir + \
			  "/rdiff-backup -v5 --remote-schema './chdir-wrapper %s' "

	def refresh(self, *rp_list):
		"""Reread data for the given rps"""
		for rp in rp_list: rp.setdata()

	def set_connections(self, src_pre, src_back, dest_pre, dest_back):
		"""Set source and destination prefixes"""
		if src_pre: self.src_prefix = "%s::%s" % (src_pre, src_back)
		else: self.src_prefix = './'

		if dest_pre: self.dest_prefix = "%s::%s" % (dest_pre, dest_back)
		else: self.dest_prefix = './'

	def exec_rb(self, *args):
		"""Run rdiff-backup on given arguments"""
		arglist = []
		arglist.append(self.src_prefix + args[0])
		if len(args) > 1:
			arglist.append(self.dest_prefix + args[1])
			assert len(args) == 2

		cmdstr = self.rb_schema + ' '.join(arglist)
		print "executing " + cmdstr
		assert not os.system(cmdstr)

	def runtest(self):
		# Deleting previous output
		assert not os.system(MiscDir + '/myrm testfiles/output* '
							 'testfiles/restoretarget* testfiles/vft_out '
							 'timbar.pyc')

		# Backing up increment1
		self.exec_rb('testfiles/increment1', 'testfiles/output')
		assert RPathStatic.cmp_recursive(Local.inc1rp, Local.rpout)
		time.sleep(1)

		# Backing up increment2
		self.exec_rb('testfiles/increment2', 'testfiles/output')
		assert RPathStatic.cmp_recursive(Local.inc2rp, Local.rpout)
		time.sleep(1)

		# Backing up increment3
		self.exec_rb('testfiles/increment3', 'testfiles/output')
		assert RPathStatic.cmp_recursive(Local.inc3rp, Local.rpout)
		time.sleep(1)

		# Backing up increment4
		self.exec_rb('testfiles/increment4', 'testfiles/output')
		assert RPathStatic.cmp_recursive(Local.inc4rp, Local.rpout)

		# Getting restore rps
		inc_paths = self.getinc_paths("increments.",
								   "testfiles/output/rdiff-backup-data")
		assert len(inc_paths) == 3

		# Restoring increment1
		self.exec_rb(inc_paths[0], 'testfiles/restoretarget1')
		assert RPathStatic.cmp_recursive(Local.inc1rp, Local.rpout1)

		# Restoring increment2
		self.exec_rb(inc_paths[1], 'testfiles/restoretarget2')
		assert RPathStatic.cmp_recursive(Local.inc2rp, Local.rpout2)

		# Restoring increment3
		self.exec_rb(inc_paths[2], 'testfiles/restoretarget3')
		assert RPathStatic.cmp_recursive(Local.inc3rp, Local.rpout3)

		# Test restoration of a few random files
		vft_paths = self.getinc_paths("various_file_types.",
					     "testfiles/output/rdiff-backup-data/increments")
		self.exec_rb(vft_paths[1], 'testfiles/vft_out')
		self.refresh(Local.vft_in, Local.vft_out)
		assert RPathStatic.cmp_recursive(Local.vft_in, Local.vft_out)

		timbar_paths = self.getinc_paths("timbar.pyc.",
						 "testfiles/output/rdiff-backup-data/increments")
		self.exec_rb(timbar_paths[0])
		self.refresh(Local.timbar_in, Local.timbar_out)
		assert RPath.cmp_with_attribs(Local.timbar_in, Local.timbar_out)

		# Make sure too many increment files not created
		assert len(self.getinc_paths("nochange.",
			  "testfiles/output/rdiff-backup-data/increments")) == 0
		assert len(self.getinc_paths("",
			"testfiles/output/rdiff-backup-data/increments/nochange")) == 0

	def getinc_paths(self, basename, directory):
		"""Return increment.______.dir paths"""
		incfiles = filter(lambda s: s.startswith(basename),
						  os.listdir(directory))
		incfiles.sort()
		incrps = map(lambda f: RPath(lc, directory+"/"+f), incfiles)
		return map(lambda x: x.path, filter(RPath.isincfile, incrps))


class Final(PathSetter):
	def testLocal(self):
		"""Run test sequence everything local"""
		self.set_connections(None, None, None, None)
		self.runtest()

	def testRemoteAll(self):
		"""Run test sequence everything remote"""
		self.set_connections("test1/", '../', 'test2/tmp/', '../../')
		self.runtest()


if __name__ == "__main__": unittest.main()
