import unittest, os, signal, sys, random, time
execfile("commontest.py")
rbexec("restore.py")

"""Test consistency by killing rdiff-backup as it is backing up"""

Log.setverbosity(3)

class Local:
	"""Hold some local RPaths"""
	def get_local_rp(ext):
		return RPath(Globals.local_connection, "testfiles/" + ext)

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

	back1 = get_local_rp('backup1')
	back2 = get_local_rp('backup2')
	back3 = get_local_rp('backup3')
	back4 = get_local_rp('backup4')


class Kill(unittest.TestCase):
	def delete_tmpdirs(self):
		"""Remove any temp directories created by previous tests"""
		assert not os.system(MiscDir + '/myrm testfiles/output* '
							 'testfiles/restoretarget* testfiles/vft_out '
							 'timbar.pyc testfiles/vft2_out')

	def is_aborted_backup(self):
		"""True if there are signs of aborted backup in output/"""
		try: dirlist = os.listdir("testfiles/output/rdiff-backup-data")
		except OSError:
			print "No data dir found, give process more time"
			raise
		dirlist = filter(lambda f: f.startswith("last-file-incremented"),
						 dirlist)
		return len(dirlist) != 0

	def exec_rb(self, time, wait, *args):
		"""Run rdiff-backup return pid"""
		arglist = ['python', '../src/rdiff-backup', '-v7']
		if time:
			arglist.append("--current-time")
			arglist.append(str(time))
		arglist.extend(args)

		print "Running ", arglist
		if wait: return os.spawnvp(os.P_WAIT, 'python', arglist)
		else: return os.spawnvp(os.P_NOWAIT, 'python', arglist)

	def exec_and_kill(self, mintime, maxtime, backup_time, *args):
		"""Run rdiff-backup, then kill and run again

		Kill after a time between mintime and maxtime.  First process
		should not terminate before maxtime.

		"""
		pid = self.exec_rb(backup_time, None, *args)
		time.sleep(random.uniform(mintime, maxtime))
		assert os.waitpid(pid, os.WNOHANG)[0] == 0, \
			   "Process already quit - try lowering max time"
		os.kill(pid, self.killsignal)
		while 1:
			pid, exitstatus = os.waitpid(pid, os.WNOHANG)
			if pid:
				assert exitstatus != 0
				break
			time.sleep(0.2)
		assert self.is_aborted_backup(), \
			   "Process already finished or didn't get a chance to start"
		os.system("ls -l %s/rdiff-backup-data" % args[1])
		return self.exec_rb(backup_time + 5, 1, '--resume', *args)

	def verify_back_dirs(self):
		"""Make sure testfiles/output/back? dirs exist"""
		if (Local.back1.lstat() and Local.back2.lstat() and
			Local.back3.lstat() and Local.back4.lstat()): return

		os.system(MiscDir + "/myrm testfiles/backup[1-4]")

		self.exec_rb(10000, 1, 'testfiles/increment1', 'testfiles/backup1')
		Local.back1.setdata()

		self.exec_rb(10000, 1, 'testfiles/increment1', 'testfiles/backup2')
		self.exec_rb(20000, 1, 'testfiles/increment2', 'testfiles/backup2')
		Local.back2.setdata()
		
		self.exec_rb(10000, 1, 'testfiles/increment1', 'testfiles/backup3')
		self.exec_rb(20000, 1, 'testfiles/increment2', 'testfiles/backup3')
		self.exec_rb(30000, 1, 'testfiles/increment3', 'testfiles/backup3')
		Local.back3.setdata()
		
		self.exec_rb(10000, 1, 'testfiles/increment1', 'testfiles/backup4')
		self.exec_rb(20000, 1, 'testfiles/increment2', 'testfiles/backup4')
		self.exec_rb(30000, 1, 'testfiles/increment3', 'testfiles/backup4')
		self.exec_rb(40000, 1, 'testfiles/increment4', 'testfiles/backup4')
		Local.back4.setdata()

	def runtest(self):
		self.delete_tmpdirs()
		self.verify_back_dirs()
		
		# Backing up increment1 - unfortunately, not big enough to test?
		#self.exec_and_kill(0.6, 0.6, 10000,
		#				   'testfiles/increment1', 'testfiles/output')
		#assert CompareRecursive(Local.back1, Local.rpout, 1, None, None)
		self.exec_rb(10000, 1, 'testfiles/increment1', 'testfiles/output')
		time.sleep(1)

		# Backing up increment2
		self.exec_and_kill(0.7, 1.0, 20000,
						   'testfiles/increment2', 'testfiles/output')
		assert CompareRecursive(Local.back2, Local.rpout, 1, None, None)
		time.sleep(1)

		# Backing up increment3
		self.exec_and_kill(0.7, 2.0, 30000,
						   'testfiles/increment3', 'testfiles/output')
		assert CompareRecursive(Local.back3, Local.rpout, 1, None, None)
		time.sleep(1)

		# Backing up increment4
		self.exec_and_kill(1.0, 5.0, 40000,
						   'testfiles/increment4', 'testfiles/output')
		assert CompareRecursive(Local.back4, Local.rpout, 1, None, None)

	def testTERM(self):
		"""Test sending local processes a TERM signal"""
		self.killsignal = signal.SIGTERM
		for i in range(5):
			self.runtest()

	def testKILL(self):
		"""Send local backup process a KILL signal"""
		self.killsignal = signal.SIGKILL
		self.runtest()

if __name__ == "__main__": unittest.main()
