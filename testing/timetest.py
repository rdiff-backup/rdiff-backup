import unittest
import time
from commontest import *  # noqa: F403, F401 some side effect or test fails
from rdiff_backup import Globals, Time


class TimeTest(unittest.TestCase):

    def cmp_times(self, time1, time2):
        """Compare time1 and time2 and return -1, 0, or 1"""
        if type(time1) is str:
            time1 = Time.stringtotime(time1)
            self.assertIsNotNone(time1)
        if type(time2) is str:
            time2 = Time.stringtotime(time2)
            self.assertIsNotNone(time2)

        if time1 < time2:
            return -1
        elif time1 == time2:
            return 0
        else:
            return 1

    def testConversion(self):
        """test timetostring and stringtotime"""
        Time.set_current_time()
        self.assertIsInstance(Time.curtime, (float, int))
        self.assertIsInstance(Time.curtimestr, str)
        self.assertTrue(
            self.cmp_times(int(Time.curtime), Time.curtimestr) == 0
            or self.cmp_times(int(Time.curtime) + 1, Time.curtimestr) == 0)
        time.sleep(1.05)
        self.assertEqual(self.cmp_times(time.time(), Time.curtime), 1)
        self.assertEqual(self.cmp_times(Time.timetostring(time.time()),
                                        Time.curtimestr), 1)

    def testConversion_separator(self):
        """Same as testConversion, but change time Separator"""
        Globals.time_separator = "_"
        self.testConversion()
        Globals.time_separator = ":"

    def testCmp(self):
        """Test time comparisons"""
        self.assertEqual(self.cmp_times(1, 2), -1)
        self.assertEqual(self.cmp_times(2, 2), 0)
        self.assertEqual(self.cmp_times(5, 1), 1)
        self.assertEqual(self.cmp_times("2001-09-01T21:49:04Z",
                                        "2001-08-01T21:49:04Z"), 1)
        self.assertEqual(self.cmp_times("2001-09-01T04:49:04+03:23",
                                        "2001-09-01T21:49:04Z"), -1)
        self.assertEqual(self.cmp_times("2001-09-01T12:00:00Z",
                                        "2001-09-01T04:00:00-08:00"), 0)
        self.assertEqual(self.cmp_times("2001-09-01T12:00:00-08:00",
                                        "2001-09-01T12:00:00-07:00"), 1)

    def testBytestotime(self):
        """Test converting byte string to time"""
        timesec = int(time.time())
        self.assertEqual(
            timesec,
            int(Time.bytestotime(Time.timetostring(timesec).encode('ascii'))))

        # assure that non-ascii byte strings return None and that they don't
        # throw an exception (issue #295)
        self.assertIsNone(Time.bytestotime(b'\xff'))

    def testStringtotime(self):
        """Test converting string to time"""
        timesec = int(time.time())
        self.assertEqual(timesec,
                         int(Time.stringtotime(Time.timetostring(timesec))))
        # stringtotime returns None if the time string is invalid
        self.assertIsNone(Time.stringtotime("2001-18-83T03:03:03Z"))
        self.assertIsNone(Time.stringtotime("2001-01-23L03:03:03L"))
        self.assertIsNone(Time.stringtotime("2001_01_23T03:03:03Z"))

    def testIntervals(self):
        """Test converting strings to intervals"""
        i2s = Time._intervalstr_to_seconds
        for s in ["32", "", "d", "231I", "MM", "s", "-2h"]:
            with self.assertRaises(Time.TimeException):
                i2s(s)
        self.assertEqual(i2s("7D"), 7 * 86400)
        self.assertEqual(i2s("232s"), 232)
        self.assertEqual(i2s("2M"), 2 * 30 * 86400)
        self.assertEqual(i2s("400m"), 400 * 60)
        self.assertEqual(i2s("1Y"), 365 * 86400)
        self.assertEqual(i2s("30h"), 30 * 60 * 60)
        self.assertEqual(i2s("3W"), 3 * 7 * 86400)

    def testIntervalsComposite(self):
        """Like above, but allow composite intervals"""
        i2s = Time._intervalstr_to_seconds
        self.assertEqual(i2s("7D2h"), 7 * 86400 + 2 * 3600)
        self.assertEqual(i2s("2Y3s"), 2 * 365 * 86400 + 3)
        self.assertEqual(
            i2s("1M2W4D2h5m20s"),
            (30 * 86400 + 2 * 7 * 86400 + 4 * 86400 + 2 * 3600 + 5 * 60 + 20))

    def testPrettyIntervals(self):
        """Test printable interval conversion"""
        self.assertEqual(Time.inttopretty(3600), "1 hour")
        self.assertEqual(Time.inttopretty(7220), "2 hours 20 seconds")
        self.assertEqual(Time.inttopretty(0), "0 seconds")
        self.assertEqual(Time.inttopretty(353), "5 minutes 53 seconds")
        self.assertEqual(Time.inttopretty(3661), "1 hour 1 minute 1 second")
        self.assertEqual(Time.inttopretty(353.234234),
                         "5 minutes 53.23 seconds")

    def testPrettyTimes(self):
        """Convert seconds to pretty and back"""
        now = int(time.time())
        for i in [1, 200000, now]:
            self.assertEqual(Time.prettytotime(Time.timetopretty(i)), i)
        self.assertIsNone(Time.prettytotime("now"))
        self.assertIsNone(Time.prettytotime("12314"))

    def testGenericString(self):
        """Test genstrtotime, conversion of arbitrary string to time"""
        g2t = Time.genstrtotime
        self.assertEqual(g2t('now', 1000), 1000)
        self.assertEqual(g2t('2h3s', 10000), 10000 - 2 * 3600 - 3)
        self.assertEqual(
            g2t('2001-09-01T21:49:04Z'),
            Time.stringtotime('2001-09-01T21:49:04Z'))
        self.assertEqual(
            g2t('2002-04-26T04:22:01'),
            Time.stringtotime('2002-04-26T04:22:01' + Time._get_tzd()))
        t = Time.stringtotime('2001-05-12T00:00:00' + Time._get_tzd())
        self.assertEqual(g2t('2001-05-12'), t)
        self.assertEqual(g2t('2001/05/12'), t)
        self.assertEqual(g2t('5/12/2001'), t)
        self.assertEqual(g2t('123456'), 123456)

    def testGenericStringErrors(self):
        """Test genstrtotime on some bad strings"""
        g2t = Time.genstrtotime
        self.assertRaises(Time.TimeException, g2t, "hello")
        self.assertRaises(Time.TimeException, g2t, "")
        self.assertRaises(Time.TimeException, g2t, "3q")

    def testTimeZone(self):
        """Test stringtotime on two strings straddling timezones"""
        f = Time.stringtotime
        invf = Time.timetostring
        s1 = "2005-04-03T03:45:03-03:00"
        s2 = "2005-04-03T02:45:03-03:00"
        diff = f(s1) - f(s2)
        self.assertEqual(diff, 3600)

        self.assertEqual(f(invf(f(s1))), f(s1))
        self.assertEqual(f(invf(f(s2))), f(s2))


if __name__ == '__main__':
    unittest.main()
