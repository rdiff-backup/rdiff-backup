import unittest, os, signal, sys, random, time
from commontest import *
from rdiff_backup.log import *
from rdiff_backup import Globals, Main, restore

"""Test consistency by killing rdiff-backup as it is backing up"""

Log.setverbosity(3)

class Local:
	"""Hold some local RPaths"""
	def get_local_rp(ext):
		return RPath(Globals.local_connection, os.path.join(abs_test_dir, ext))

	ktrp = []
	for i in range(4):
		ktrp.append(get_local_rp(b'killtest%d' % (i+1)))

	rpout = get_local_rp(b'output')
	rpout_inc = get_local_rp(b'output_inc')

	outrp = []
	for i in range(5):
		outrp.append(get_local_rp(b'restoretarget%d' % (i+1)))

	backrp = []
	for i in range(5):
		backrp.append(get_local_rp(b'backup%d' % (i+1)))

class TimingError(Exception):
	"""Indicates timing error - process killed too soon or too late"""
	pass


class ProcessFuncs(unittest.TestCase):
	"""Subclassed by Resume and NoResume"""
	def delete_tmpdirs(self):
		"""Remove any temp directories created by previous tests"""
		if Local.rpout.lstat(): Local.rpout.delete()
		if Local.rpout_inc.lstat(): Local.rpout_inc.delete()
		for rp in Local.outrp:
			if rp.lstat(): rp.delete()
		# TODO check if following files really need to be deleted:
		# testfiles/vft_out timbar.pyc testfiles/vft2_out

	def exec_rb(self, time, wait, *args):
		"""Run rdiff-backup return pid.  Wait until done if wait is true"""
		arglist = [sys.executable, 'rdiff-backup', '-v3']
		if time:
			arglist.append("--current-time")
			arglist.append(str(time))
		arglist.extend(args)

		print("Running ", arglist)
		if wait: return os.spawnvp(os.P_WAIT, sys.executable, arglist)
		else: return os.spawnvp(os.P_NOWAIT, sys.executable, arglist)

	def exec_and_kill(self, min_max_pair, backup_time, arg1, arg2):
		"""Run rdiff-backup, then kill and run again

		Kill after a time between mintime and maxtime.  First process
		should not terminate before maxtime.

		"""
		mintime, maxtime = min_max_pair
		pid = self.exec_rb(backup_time, None, arg1, arg2)
		time.sleep(random.uniform(mintime, maxtime))
		if os.waitpid(pid, os.WNOHANG)[0] != 0:
			# Timing problem, process already terminated (max time too big?)
			return -1
		os.kill(pid, self.killsignal)
		while 1:
			pid, exitstatus = os.waitpid(pid, os.WNOHANG)
			if pid:
				assert exitstatus != 0
				break
			time.sleep(0.2)
		print("---------------------- killed")

	def create_killtest_dirs(self):
		"""Create testfiles/killtest? directories

		They are similar to the testfiles/increment? directories but
		have more files in them so they take a significant time to
		back up.

		"""
		def copy_thrice(input, output):
			"""Copy input directory to output directory three times"""
			assert not os.system(b"cp -a %s %s" % (input, output))
			assert not os.system(b"cp -a %s %s/killtesta" % (input, output))
			assert not os.system(b"cp -a %s %s/killtestb" % (input, output))

		for i in range(len(Local.ktrp)):
			if Local.ktrp[i].lstat(): Local.ktrp[i].delete()
			copy_thrice(os.path.join(old_test_dir, b"increment%d" % (i+1)),
					Local.ktrp[i].path)

	def runtest_sequence(self, total_tests,
						 exclude_rbdir, ignore_tmp, compare_links,
						 stop_on_error = None):
		timing_problems, failures = 0, 0
		for i in range(total_tests):
			try:
				result = self.runtest(exclude_rbdir, ignore_tmp, compare_links)
			except TimingError as te:
				print(te)
				timing_problems += 1
				continue
			if result != 1:
				if stop_on_error: assert 0, "Compare Failure"
				else: failures += 1

		print(total_tests, "tests attempted total")
		print("%s setup problems, %s failures, %s successes" % \
			  (timing_problems, failures,
			   total_tests - timing_problems - failures))		

class KillTest(ProcessFuncs):
	"""Test rdiff-backup by killing it, recovering, and then comparing"""
	killsignal = signal.SIGTERM

	# The following are lower and upper bounds on the amount of time
	# rdiff-backup is expected to run.  They are used to determine how
	# long to wait before killing the rdiff-backup process
	time_pairs = [(0.0, 3.7), (0.0, 3.7), (0.0, 3.0), (0.0, 5.0), (0.0, 5.0)]

	def setUp(self):
		"""Create killtest? and backup? directories if necessary"""
		for rp in Local.ktrp:
			rp.setdata()
		if (not Local.ktrp[0].lstat() or not Local.ktrp[1].lstat() or
			not Local.ktrp[2].lstat() or not Local.ktrp[3].lstat()):
			self.create_killtest_dirs()

	def testTiming(self):
		"""Run each rdiff-backup sequence 10 times, printing average time"""
		time_list = [[], [], [], [], []] # List of time lists
		iterations = 10

		def run_once(current_time, input_rp, index):
			start_time = time.time()
			self.exec_rb(current_time, 1, input_rp.path, Local.rpout.path)
			time_list[index].append(time.time() - start_time)

		for i in range(iterations):
			self.delete_tmpdirs()
			run_once(10000, Local.ktrp[2], 0)
			run_once(20000, Local.ktrp[0], 1)
			run_once(30000, Local.ktrp[2], 2)
			run_once(40000, Local.ktrp[2], 3)
			run_once(50000, Local.ktrp[2], 4)

		for i in range(len(time_list)):
			print("%s -> %s" % (i, " ".join(map(str, time_list[i]))))

	def mark_incomplete(self, curtime, rp):
		"""Check the date of current mirror

		Return 1 if there are two current_mirror incs and last one has
		time curtime.  Return 0 if only one with time curtime, and
		then add a current_mirror marker.  Return -1 if only one and
		time is not curtime.

		"""
		rbdir = rp.append_path("rdiff-backup-data")
		inclist = restore.get_inclist(rbdir.append("current_mirror"))
		assert 1 <= len(inclist) <= 2, str([x.path for x in inclist])

		inc_date_pairs = [(inc.getinctime(), inc) for inc in inclist]
		inc_date_pairs.sort()
		if len(inclist) == 2:
			assert inc_date_pairs[-1][0] == curtime, \
				   (inc_date_pairs[-1][0], curtime)
			return 1

		if inc_date_pairs[-1][0] == curtime:
			result = 0
			marker_time = curtime - 10000
		else:
			assert inc_date_pairs[-1][0] == curtime - 10000
			marker_time = curtime
			result = -1

		cur_mirror_rp = rbdir.append("current_mirror.%s.data" %
									 (Time.timetostring(marker_time),))
		assert not cur_mirror_rp.lstat()
		cur_mirror_rp.touch()
		return result

	def testTerm(self):
		"""Run rdiff-backup, termining and regressing each time

		Because rdiff-backup must be killed, the timing should be
		updated

		"""
		count, killed_too_soon, killed_too_late = 5, [0]*4, [0]*4
		self.delete_tmpdirs()
		# Back up killtest3 first because it is big and the first case
		# is kind of special (there's no incrementing, so different
		# code)
		self.exec_rb(10000, 1, Local.ktrp[2].path, Local.rpout.path)
		assert CompareRecursive(Local.ktrp[2], Local.rpout)

		def cycle_once(min_max_time_pair, curtime, input_rp, old_rp):
			"""Backup input_rp, kill, regress, and then compare"""
			time.sleep(1)
			self.exec_and_kill(min_max_time_pair, curtime,
							   input_rp.path, Local.rpout.path)
			result = self.mark_incomplete(curtime, Local.rpout)
			assert not self.exec_rb(None, 1, '--check-destination-dir',
			   						Local.rpout.path)
			assert CompareRecursive(old_rp, Local.rpout, compare_hardlinks = 0)
			return result

		# Keep backing ktrp[0], and then regressing to ktrp[2].  Then go to ktrp[0]
		for i in range(count):
			result = cycle_once(self.time_pairs[1], 20000,
								Local.ktrp[0], Local.ktrp[2])
			if result == 0: killed_too_late[0] += 1
			elif result == -1: killed_too_soon[0] += 1
		self.exec_rb(20000, 1, Local.ktrp[0].path, Local.rpout.path)

		# Now keep regressing from ktrp[1], only staying there at the end
		for i in range(count):
			result = cycle_once(self.time_pairs[2], 30000,
								Local.ktrp[1], Local.ktrp[0])
			if result == 0: killed_too_late[1] += 1
			elif result == -1: killed_too_soon[1] += 1
		self.exec_rb(30000, 1, Local.ktrp[1].path, Local.rpout.path)

		# Now keep regressing from ktrp[2], only staying there at the end
		for i in range(count):
			result = cycle_once(self.time_pairs[3], 40000,
								Local.ktrp[2], Local.ktrp[1])
			if result == 0: killed_too_late[2] += 1
			elif result == -1: killed_too_soon[2] += 1
		self.exec_rb(40000, 1, Local.ktrp[2].path, Local.rpout.path)

		# Now keep regressing from ktrp[3], only staying there at the end
		for i in range(count):
			result = cycle_once(self.time_pairs[4], 50000,
								Local.ktrp[3], Local.ktrp[2])
			if result == 0: killed_too_late[3] += 1
			elif result == -1: killed_too_soon[3] += 1

		print("Killed too soon out of %s: %s" % (count, killed_too_soon))
		print("Killed too late out of %s: %s" % (count, killed_too_late))

if __name__ == "__main__": unittest.main()
