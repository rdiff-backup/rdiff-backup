import unittest, time, types
from commontest import *
from rdiff_backup import Globals, Time

class TimeTest(unittest.TestCase):
	def testConversion(self):
		"""test timetostring and stringtotime"""
		Time.setcurtime()
		assert type(Time.curtime) is types.FloatType or types.LongType
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
			except Time.TimeException: pass
			else: assert 0, s
		assert i2s("7D") == 7*86400
		assert i2s("232s") == 232
		assert i2s("2M") == 2*30*86400
		assert i2s("400m") == 400*60
		assert i2s("1Y") == 365*86400
		assert i2s("30h") == 30*60*60
		assert i2s("3W") == 3*7*86400

	def testIntervalsComposite(self):
		"""Like above, but allow composite intervals"""
		i2s = Time.intstringtoseconds
		assert i2s("7D2h") == 7*86400 + 2*3600
		assert i2s("2Y3s") == 2*365*86400 + 3
		assert i2s("1M2W4D2h5m20s") == (30*86400 + 2*7*86400 + 4*86400 +
										2*3600 + 5*60 + 20)

	def testPrettyIntervals(self):
		"""Test printable interval conversion"""
		assert Time.inttopretty(3600) == "1 hour"
		assert Time.inttopretty(7220) == "2 hours 20 seconds"
		assert Time.inttopretty(0) == "0 seconds"
		assert Time.inttopretty(353) == "5 minutes 53 seconds"
		assert Time.inttopretty(3661) == "1 hour 1 minute 1 second"
		assert Time.inttopretty(353.234234) == "5 minutes 53.23 seconds"

	def testGenericString(self):
		"""Test genstrtotime, conversion of arbitrary string to time"""
		g2t = Time.genstrtotime
		assert g2t('now', 1000) == 1000
		assert g2t('2h3s', 10000) == 10000 - 2*3600 - 3
		assert g2t('2001-09-01T21:49:04Z') == \
			   Time.stringtotime('2001-09-01T21:49:04Z')
		assert g2t('2002-04-26T04:22:01') == \
			   Time.stringtotime('2002-04-26T04:22:01' + Time.gettzd())
		t = Time.stringtotime('2001-05-12T00:00:00' + Time.gettzd())
		assert g2t('2001-05-12') == t
		assert g2t('2001/05/12') == t
		assert g2t('5/12/2001') == t
		assert g2t('123456') == 123456

	def testGenericStringErrors(self):
		"""Test genstrtotime on some bad strings"""
		g2t = Time.genstrtotime
		self.assertRaises(Time.TimeException, g2t, "hello")
		self.assertRaises(Time.TimeException, g2t, "")
		self.assertRaises(Time.TimeException, g2t, "3q")

	def testSleeping(self):
		"""Test sleep and sleep ratio"""
		sleep_ratio = 0.5
		time1 = time.time()
		Time.sleep(0) # set initial time
		time.sleep(1)
		time2 = time.time()
		Time.sleep(sleep_ratio)
		time3 = time.time()
		time.sleep(0.5)
		time4 = time.time()
		Time.sleep(sleep_ratio)
		time5 = time.time()

		sleep_ratio = 0.25
		time.sleep(0.75)
		time6 = time.time()
		Time.sleep(sleep_ratio)
		time7 = time.time()
		
		assert 0.9 < time3 - time2 < 1.1, time3 - time2
		assert 0.4 < time5 - time4 < 0.6, time5 - time4
		assert 0.2 < time7 - time6 < 0.3, time7 - time6


if __name__ == '__main__': unittest.main()
