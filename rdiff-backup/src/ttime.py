execfile("log.py")
import time, types

#######################################################################
#
# ttime - Provide Time class, which contains time related functions.
#

class TimeException(Exception): pass

class Time:
	"""Functions which act on the time"""
	_interval_conv_dict = {"s": 1, "m": 60, "h": 3600,
						   "D": 86400, "M": 30*86400, "Y": 365*86400}

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

			return utc_in_secs + cls.tzdtoseconds(timestring[19:])
		except (TypeError, ValueError, AssertionError): return None

	def timetopretty(cls, timeinseconds):
		"""Return pretty version of time"""
		return time.asctime(time.localtime(timeinseconds))

	def stringtopretty(cls, timestring):
		"""Return pretty version of time given w3 time string"""
		return cls.timetopretty(cls.stringtotime(timestring))

	def intstringtoseconds(cls, interval_string):
		"""Convert a string expressing an interval to seconds"""
		def error():
			raise TimeException('Bad interval string "%s"' % interval_string)
		if len(interval_string) < 2: error()
		try: num, ext = int(interval_string[:-1]), interval_string[-1]
		except ValueError: error()
		if not ext in cls._interval_conv_dict or num < 0: error()
		return num*cls._interval_conv_dict[ext]

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

MakeClass(Time)
