import unittest
execfile("commontest.py")
rbexec("highlevel.py")

class TimeTest(unittest.TestCase):
	def testConversion(self):
		"""test timetostring and stringtotime"""
		Time.setcurtime()
		assert type(Time.curtime) is types.FloatType
		assert type(Time.curtimestr) is types.StringType
		assert (Time.cmp(int(Time.curtime), Time.curtimestr) == 0 or
				Time.cmp(int(Time.curtime) + 1, Time.curtimestr) == 0)
		time.sleep(1.05)
		assert Time.cmp(time.time(), Time.curtime) == 1
		assert Time.cmp(Time.timetostring(time.time()), Time.curtimestr) == 1

	def testConversion_separator(self):
		"""Same as testConversion, but change time Separator"""
		Globals.time_separator = "_"
		self.testConversion()
		Globals.time_separator = ":"

	def testCmp(self):
		"""Test time comparisons"""
		cmp = Time.cmp
		assert cmp(1,2) == -1
		assert cmp(2,2) == 0
		assert cmp(5,1) == 1
		assert cmp("2001-09-01T21:49:04Z", "2001-08-01T21:49:04Z") == 1
		assert cmp("2001-09-01T04:49:04+03:23", "2001-09-01T21:49:04Z") == -1
		assert cmp("2001-09-01T12:00:00Z", "2001-09-01T04:00:00-08:00") == 0
		assert cmp("2001-09-01T12:00:00-08:00",
				   "2001-09-01T12:00:00-07:00") == 1

	def testCmp_separator(self):
		"""Like testCmp but with new separator"""
		Globals.time_separator = "_"
		cmp = Time.cmp
		assert cmp(1,2) == -1
		assert cmp(2,2) == 0
		assert cmp(5,1) == 1
		assert cmp("2001-09-01T21_49_04Z", "2001-08-01T21_49_04Z") == 1
		assert cmp("2001-09-01T04_49_04+03_23", "2001-09-01T21_49_04Z") == -1
		assert cmp("2001-09-01T12_00_00Z", "2001-09-01T04_00_00-08_00") == 0
		assert cmp("2001-09-01T12_00_00-08_00",
				   "2001-09-01T12_00_00-07_00") == 1
		Globals.time_separator = ":"

	def testStringtotime(self):
		"""Test converting string to time"""
		timesec = int(time.time())
		assert timesec == int(Time.stringtotime(Time.timetostring(timesec)))
		assert not Time.stringtotime("2001-18-83T03:03:03Z")
		assert not Time.stringtotime("2001-01-23L03:03:03L")
		assert not Time.stringtotime("2001_01_23T03:03:03Z")

	def testIntervals(self):
		"""Test converting strings to intervals"""
		i2s = Time.intstringtoseconds
		for s in ["32", "", "d", "231I", "MM", "s", "-2h"]:
			try: i2s(s)
			except TimeException: pass
			else: assert 0, s
		assert i2s("7D") == 7*86400
		assert i2s("232s") == 232
		assert i2s("2M") == 2*30*86400
		assert i2s("400m") == 400*60
		assert i2s("1Y") == 365*86400
		assert i2s("30h") == 30*60*60

if __name__ == '__main__': unittest.main()
