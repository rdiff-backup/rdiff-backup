# Copyright 2002 Ben Escoto
#
# This file is part of rdiff-backup.
#
# rdiff-backup is free software; you can redistribute it and/or modify
# under the terms of the GNU General Public License as published by the
# Free Software Foundation; either version 2 of the License, or (at your
# option) any later version.
#
# rdiff-backup is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with rdiff-backup; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307
# USA
"""Provide time related exceptions and functions"""

import time
import re
import calendar
from . import Globals


class TimeException(Exception):
    pass


_interval_conv_dict = {
    "s": 1,
    "m": 60,
    "h": 3600,
    "D": 86400,
    "W": 7 * 86400,
    "M": 30 * 86400,
    "Y": 365 * 86400
}
_integer_regexp = re.compile("^[0-9]+$")
_session_regexp = re.compile("^[0-9]+B$")
_interval_regexp = re.compile("^([0-9]+)([smhDWMY])")
_genstr_date_regexp1 = re.compile(
    "^(?P<year>[0-9]{4})[-/]"
    "(?P<month>[0-9]{1,2})[-/](?P<day>[0-9]{1,2})$")
_genstr_date_regexp2 = re.compile("^(?P<month>[0-9]{1,2})[-/]"
                                  "(?P<day>[0-9]{1,2})[-/](?P<year>[0-9]{4})$")
curtime = curtimestr = None


def setcurtime(curtime=None):
    """Sets the current time in curtime and curtimestr on all systems"""
    t = curtime or time.time()
    for conn in Globals.connections:
        conn.Time.setcurtime_local(int(t))


def setcurtime_local(timeinseconds):
    """Only set the current time locally"""
    global curtime, curtimestr
    curtime, curtimestr = timeinseconds, timetostring(timeinseconds)


def setprevtime(timeinseconds):
    """Sets the previous inc time in prevtime and prevtimestr"""
    assert 0 < timeinseconds < curtime, \
        "Time %s is out of bounds" % (timeinseconds,)
    timestr = timetostring(timeinseconds)
    for conn in Globals.connections:
        conn.Time.setprevtime_local(timeinseconds, timestr)


def setprevtime_local(timeinseconds, timestr):
    """Like setprevtime but only set the local version"""
    global prevtime, prevtimestr
    prevtime, prevtimestr = timeinseconds, timestr


def timetostring(timeinseconds):
    """Return w3 datetime compliant listing of timeinseconds, or one in
    which :'s have been replaced with -'s"""
    if not Globals.use_compatible_timestamps:
        format_string = "%Y-%m-%dT%H:%M:%S"
    else:
        format_string = "%Y-%m-%dT%H-%M-%S"
    s = time.strftime(format_string, time.localtime(timeinseconds))
    return s + gettzd(timeinseconds)


def timetobytes(timeinseconds):
    return timetostring(timeinseconds).encode('ascii')


def stringtotime(timestring):
    """Return time in seconds from w3 timestring

    If there is an error parsing the string, or it doesn't look
    like a w3 datetime string, return None.

    """

    regexp = re.compile('[-:]')

    try:
        date, daytime = timestring[:19].split("T")
        year, month, day = list(map(int, date.split("-")))
        hour, minute, second = list(map(int, regexp.split(daytime)))
        assert 1900 < year < 2100, year
        assert 1 <= month <= 12
        assert 1 <= day <= 31
        assert 0 <= hour <= 23
        assert 0 <= minute <= 59
        assert 0 <= second <= 61  # leap seconds
        timetuple = (year, month, day, hour, minute, second, -1, -1, 0)
        utc_in_secs = calendar.timegm(timetuple)

        return int(utc_in_secs) + tzdtoseconds(timestring[19:])
    except (TypeError, ValueError, AssertionError):
        return None


def bytestotime(timebytes):
    return stringtotime(timebytes.decode('ascii'))


def timetopretty(timeinseconds):
    """Return pretty version of time"""
    return time.asctime(time.localtime(timeinseconds))


def stringtopretty(timestring):
    """Return pretty version of time given w3 time string"""
    return timetopretty(stringtotime(timestring))


def prettytotime(prettystring):
    """Converts time like "Mon Jun 5 11:00:23" to epoch sec, or None"""
    try:
        return time.mktime(time.strptime(prettystring))
    except ValueError:
        return None


def inttopretty(seconds):
    """Convert num of seconds to readable string like "2 hours"."""
    partlist = []
    hours, seconds = divmod(seconds, 3600)
    if hours > 1:
        partlist.append("%d hours" % hours)
    elif hours == 1:
        partlist.append("1 hour")

    minutes, seconds = divmod(seconds, 60)
    if minutes > 1:
        partlist.append("%d minutes" % minutes)
    elif minutes == 1:
        partlist.append("1 minute")

    if seconds == 1:
        partlist.append("1 second")
    elif not partlist or seconds > 1:
        if isinstance(seconds, int) or isinstance(seconds, int):
            partlist.append("%s seconds" % seconds)
        else:
            partlist.append("%.2f seconds" % seconds)
    return " ".join(partlist)


def intstringtoseconds(interval_string):
    """Convert a string expressing an interval (e.g. "4D2s") to seconds"""

    def error():
        raise TimeException("""Bad interval string "%s"

Intervals are specified like 2Y (2 years) or 2h30m (2.5 hours).  The
allowed special characters are s, m, h, D, W, M, and Y.  See the man
page for more information.
""" % interval_string)

    if len(interval_string) < 2:
        error()

    total = 0
    while interval_string:
        match = _interval_regexp.match(interval_string)
        if not match:
            error()
        num, ext = int(match.group(1)), match.group(2)
        if ext not in _interval_conv_dict or num < 0:
            error()
        total += num * _interval_conv_dict[ext]
        interval_string = interval_string[match.end(0):]
    return total


def gettzd(timeinseconds=None):
    """Return w3's timezone identification string.

    Expressed as [+/-]hh:mm.  For instance, PDT is -07:00 during
    dayling savings and -08:00 otherwise.  Zone coincides with what
    localtime(), etc., use.  If no argument given, use the current
    time.

    """
    if timeinseconds is None:
        timeinseconds = time.time()
    dst_in_effect = time.daylight and time.localtime(timeinseconds)[8]
    if dst_in_effect:
        offset = -time.altzone / 60
    else:
        offset = -time.timezone / 60
    if offset > 0:
        prefix = "+"
    elif offset < 0:
        prefix = "-"
    else:
        return "Z"  # time is already in UTC

    if Globals.use_compatible_timestamps:
        time_separator = '-'
    else:
        time_separator = ':'
    hours, minutes = list(map(abs, divmod(offset, 60)))
    assert 0 <= hours <= 23
    assert 0 <= minutes <= 59
    return "%s%02d%s%02d" % (prefix, hours, time_separator, minutes)


def tzdtoseconds(tzd):
    """Given w3 compliant TZD, return how far ahead UTC is"""
    if tzd == "Z":
        return 0
    assert len(tzd) == 6  # only accept forms like +08:00 for now
    assert (tzd[0] == "-" or tzd[0] == "+") and (tzd[3] == ":"
                                                 or tzd[3] == "-")
    return -60 * (60 * int(tzd[:3]) + int(tzd[4:]))


def cmp(time1, time2):
    """Compare time1 and time2 and return -1, 0, or 1"""
    if type(time1) is str:
        time1 = stringtotime(time1)
        assert time1 is not None
    if type(time2) is str:
        time2 = stringtotime(time2)
        assert time2 is not None

    if time1 < time2:
        return -1
    elif time1 == time2:
        return 0
    else:
        return 1


def time_from_session(session_num, rp=None):
    """Return time in seconds of given backup

    The current mirror is session_num 0, the next oldest increment has
    number 1, etc.  Requires that the Globals.rbdir directory be set.

    """
    session_times = Globals.rbdir.conn.restore.MirrorStruct \
        .get_increment_times()
    session_times.sort()
    if len(session_times) <= session_num:
        return session_times[0]  # Use oldest if too few backups
    return session_times[-session_num - 1]


def genstrtotime(timestr, curtime=None, rp=None):
    """Convert a generic time string to a time in seconds

    rp is used when the time is of the form "4B" or similar.  Then the
    times of the increments of that particular file are used.

    """
    if curtime is None:
        curtime = globals()['curtime']
    if timestr == "now":
        return curtime

    def error():
        raise TimeException("""Bad time string "%s"

The acceptable time strings are intervals (like "3D64s"), w3-datetime
strings, like "2002-04-26T04:22:01-07:00" (strings like
"2002-04-26T04:22:01" are also acceptable - rdiff-backup will use the
current time zone), or ordinary dates like 2/4/1997 or 2001-04-23
(various combinations are acceptable, but the month always precedes
the day).""" % timestr)

    # Test for straight integer
    if _integer_regexp.search(timestr):
        return int(timestr)

    # Test for w3-datetime format, possibly missing tzd
    t = stringtotime(timestr) or stringtotime(timestr + gettzd())
    if t:
        return t

    # Test for time given as number of backups, like 3B
    if _session_regexp.search(timestr):
        return time_from_session(int(timestr[:-1]), rp)

    # Try for long time, like "Mon Jun 5 11:00:23 1990"
    t = prettytotime(timestr)
    if t is not None:
        return t

    try:  # test for an interval, like "2 days ago"
        return curtime - intstringtoseconds(timestr)
    except TimeException:
        pass

    # Now check for dates like 2001/3/23
    match = _genstr_date_regexp1.search(timestr) or \
        _genstr_date_regexp2.search(timestr)
    if not match:
        error()
    timestr = "%s-%02d-%02dT00:00:00%s" % (match.group('year'),
                                           int(match.group('month')),
                                           int(match.group('day')), gettzd())
    t = stringtotime(timestr)
    if t is not None:
        return t
    else:
        error()
