execfile("log.py")
import time, types, re

#######################################################################
#
# ttime - Provide Time class, which contains time related functions.
#

class TimeException(Exception): pass

class Time:
	"""Functions which act on the time"""
	_interval_conv_dict = {"s": 1, "m": 60, "h": 3600, "D": 86400,
						   "W": 7*86400, "M": 30*86400, "Y": 365*86400}
	_integer_regexp = re.compile("^[0-9]+$")
	_interval_regexp = re.compile("^([0-9]+)([smhDWMY])")
	_genstr_date_regexp1 = re.compile("^(?P<year>[0-9]{4})[-/]"
						   "(?P<month>[0-9]{1,2})[-/](?P<day>[0-9]{1,2})$")
	_genstr_date_regexp2 = re.compile("^(?P<month>[0-9]{1,2})[-/]"
						   "(?P<day>[0-9]{1,2})[-/](?P<year>[0-9]{4})$")

	def setcurtime(cls, curtime = None):
		"""Sets the current time in curtime and curtimestr on all systems"""
		t = curtime or time.time()
		for conn in Globals.connections:
			conn.Time.setcurtime_local(t, cls.timetostring(t))

	def setcurtime_local(cls, timeinseconds, timestr):
		"""Only set the current time locally"""
		cls.curtime = timeinseconds
		cls.curtimestr = timestr

	def setprevtime(cls, timeinseconds):
		"""Sets the previous inc time in prevtime and prevtimestr"""
		assert timeinseconds > 0, timeinseconds
		timestr = cls.timetostring(timeinseconds)
		for conn in Globals.connections:
			conn.Time.setprevtime_local(timeinseconds, timestr)

	def setprevtime_local(cls, timeinseconds, timestr):
		"""Like setprevtime but only set the local version"""
		cls.prevtime = timeinseconds
		cls.prevtimestr = timestr

	def timetostring(cls, timeinseconds):
		"""Return w3 datetime compliant listing of timeinseconds"""
		return time.strftime("%Y-%m-%dT%H" + Globals.time_separator +
							 "%M" + Globals.time_separator + "%S",
							 time.localtime(timeinseconds)) + cls.gettzd()

	def stringtotime(cls, timestring):
		"""Return time in seconds from w3 timestring

		If there is an error parsing the string, or it doesn't look
		like a w3 datetime string, return None.

		"""
		try:
			date, daytime = timestring[:19].split("T")
			year, month, day = map(int, date.split("-"))
			hour, minute, second = map(int,
									   daytime.split(Globals.time_separator))
			assert 1900 < year < 2100, year
			assert 1 <= month <= 12
			assert 1 <= day <= 31
			assert 0 <= hour <= 23
			assert 0 <= minute <= 59
			assert 0 <= second <= 61  # leap seconds
			timetuple = (year, month, day, hour, minute, second, -1, -1, -1)
			if time.daylight:
				utc_in_secs = time.mktime(timetuple) - time.altzone
			else: utc_in_secs = time.mktime(timetuple) - time.timezone

			return long(utc_in_secs) + cls.tzdtoseconds(timestring[19:])
		except (TypeError, ValueError, AssertionError): return None

	def timetopretty(cls, timeinseconds):
		"""Return pretty version of time"""
		return time.asctime(time.localtime(timeinseconds))

	def stringtopretty(cls, timestring):
		"""Return pretty version of time given w3 time string"""
		return cls.timetopretty(cls.stringtotime(timestring))

	def inttopretty(cls, seconds):
		"""Convert num of seconds to readable string like "2 hours"."""
		partlist = []
		hours, seconds = divmod(seconds, 3600)
		if hours > 1: partlist.append("%d hours" % hours)
		elif hours == 1: partlist.append("1 hour")

		minutes, seconds = divmod(seconds, 60)
		if minutes > 1: partlist.append("%d minutes" % minutes)
		elif minutes == 1: partlist.append("1 minute")

		if seconds == 1: partlist.append("1 second")
		elif not partlist or seconds > 1:
			partlist.append("%s seconds" % seconds)
		return " ".join(partlist)

	def intstringtoseconds(cls, interval_string):
		"""Convert a string expressing an interval (e.g. "4D2s") to seconds"""
		def error():
			raise TimeException("""Bad interval string "%s"

Intervals are specified like 2Y (2 years) or 2h30m (2.5 hours).  The
allowed special characters are s, m, h, D, W, M, and Y.  See the man
page for more information.
""" % interval_string)
		if len(interval_string) < 2: error()
		
		total = 0
		while interval_string:
			match = cls._interval_regexp.match(interval_string)
			if not match: error()
			num, ext = int(match.group(1)), match.group(2)
			if not ext in cls._interval_conv_dict or num < 0: error()
			total += num*cls._interval_conv_dict[ext]
			interval_string = interval_string[match.end(0):]
		return total

	def gettzd(cls):
		"""Return w3's timezone identification string.

		Expresed as [+/-]hh:mm.  For instance, PST is -08:00.  Zone is
		coincides with what localtime(), etc., use.

		"""
		if time.daylight: offset = -1 * time.altzone/60
		else: offset = -1 * time.timezone/60
		if offset > 0: prefix = "+"
		elif offset < 0: prefix = "-"
		else: return "Z" # time is already in UTC

		hours, minutes = map(abs, divmod(offset, 60))
		assert 0 <= hours <= 23
		assert 0 <= minutes <= 59
		return "%s%02d%s%02d" % (prefix, hours,
								 Globals.time_separator, minutes)

	def tzdtoseconds(cls, tzd):
		"""Given w3 compliant TZD, return how far ahead UTC is"""
		if tzd == "Z": return 0
		assert len(tzd) == 6 # only accept forms like +08:00 for now
		assert (tzd[0] == "-" or tzd[0] == "+") and \
			   tzd[3] == Globals.time_separator
		return -60 * (60 * int(tzd[:3]) + int(tzd[4:]))

	def cmp(cls, time1, time2):
		"""Compare time1 and time2 and return -1, 0, or 1"""
		if type(time1) is types.StringType:
			time1 = cls.stringtotime(time1)
			assert time1 is not None
		if type(time2) is types.StringType:
			time2 = cls.stringtotime(time2)
			assert time2 is not None
		
		if time1 < time2: return -1
		elif time1 == time2: return 0
		else: return 1

	def genstrtotime(cls, timestr, curtime = None):
		"""Convert a generic time string to a time in seconds"""
		if curtime is None: curtime = cls.curtime
		if timestr == "now": return curtime

		def error():
			raise TimeException("""Bad time string "%s"

The acceptible time strings are intervals (like "3D64s"), w3-datetime
strings, like "2002-04-26T04:22:01-07:00" (strings like
"2002-04-26T04:22:01" are also acceptable - rdiff-backup will use the
current time zone), or ordinary dates like 2/4/1997 or 2001-04-23
(various combinations are acceptable, but the month always precedes
the day).""" % timestr)

		# Test for straight integer
		if cls._integer_regexp.search(timestr): return int(timestr)

		# Test for w3-datetime format, possibly missing tzd
		t = cls.stringtotime(timestr) or cls.stringtotime(timestr+cls.gettzd())
		if t: return t

		try: # test for an interval, like "2 days ago"
			return curtime - cls.intstringtoseconds(timestr)
		except TimeException: pass

		# Now check for dates like 2001/3/23
		match = cls._genstr_date_regexp1.search(timestr) or \
				cls._genstr_date_regexp2.search(timestr)
		if not match: error()
		timestr = "%s-%02d-%02dT00:00:00%s" % \
				  (match.group('year'), int(match.group('month')),
				   int(match.group('day')), cls.gettzd())
		t = cls.stringtotime(timestr)
		if t: return t
		else: error()

MakeClass(Time)
