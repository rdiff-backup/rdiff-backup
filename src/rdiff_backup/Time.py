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
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA
"""Provide time related exceptions and functions"""

import calendar
import re
import time
from rdiff_backup import Globals


curtime = curtimestr = None  # compat200
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

# constants defining the format string for time dates (without timezone)
TIMEDATE_FORMAT_STRING = "%Y-%m-%dT%H:%M:%S"
TIMEDATE_FORMAT_COMPAT = TIMEDATE_FORMAT_STRING.replace(":", "-")
TIMEDATE_FORMAT_LENGTH = 19  # 19 chars with 4 digits year
# separators in a string looking like the above
TIMEDATE_FORMAT_REGEXP = re.compile('[T:-]')


class TimeException(Exception):
    pass


def set_current_time(reftime=None):
    """
    Sets the current time in curtime and curtimestr on all systems
    """
    if reftime is None:
        reftime = time.time()
    if Globals.get_api_version() < 201:  # compat200
        for conn in Globals.connections:
            conn.Time.setcurtime_local(int(reftime))
    else:
        Globals.set_all("current_time", reftime)
        Globals.set_all("current_time_string", timetostring(reftime))


# @API(setcurtime_local, 200, 200)
def setcurtime_local(timeinseconds):
    """
    Only set the current time locally
    """
    global curtime, curtimestr
    curtime, curtimestr = timeinseconds, timetostring(timeinseconds)


# compat200 - replace through direct reference to Globals.current_time
def getcurtime():
    if Globals.get_api_version() < 201:
        return curtime
    else:
        return Globals.current_time


# compat200 - replace through direct reference to Globals.current_time_string
def getcurtimestr():
    if Globals.get_api_version() < 201:
        return curtimestr
    else:
        return Globals.current_time_string


def setprevtime_compat200(timeinseconds):
    """
    Sets the previous inc time in prevtime and prevtimestr on all connections
    """
    assert 0 < timeinseconds < getcurtime(), (
        "Time {secs} is either negative or in the future".format(
            secs=timeinseconds))
    timestr = timetostring(timeinseconds)
    for conn in Globals.connections:
        conn.Time.setprevtime_local(timeinseconds, timestr)


# @API(setprevtime_local, 200, 200)
def setprevtime_local(timeinseconds, timestr):
    """
    Like setprevtime but only set the local version
    """
    global prevtime, prevtimestr
    prevtime, prevtimestr = timeinseconds, timestr


def timetostring(timeinseconds):
    """
    Return w3 datetime compliant listing of timeinseconds, or one in
    which :'s have been replaced with -'s
    """
    if not Globals.use_compatible_timestamps:
        format_string = TIMEDATE_FORMAT_STRING
    else:
        format_string = TIMEDATE_FORMAT_COMPAT
    s = time.strftime(format_string, time.localtime(timeinseconds))
    return s + _get_tzd(timeinseconds)


def timetobytes(timeinseconds):
    return timetostring(timeinseconds).encode('ascii')


def stringtotime(timestring):
    """
    Return time in seconds from w3 timestring

    If there is an error parsing the string, or it doesn't look
    like a w3 datetime string, return None.
    """
    try:
        year, month, day, hour, minute, second = list(
            map(int, TIMEDATE_FORMAT_REGEXP.split(
                timestring[:TIMEDATE_FORMAT_LENGTH])))
        timetuple = (year, month, day, hour, minute, second, -1, -1, 0)
        if not (1900 < year < 2100
                and 1 <= month <= 12
                and 1 <= day <= 31
                and 0 <= hour <= 23
                and 0 <= minute <= 59
                and 0 <= second <= 61):  # leap seconds
            # "Time string {tstr} couldn't be parsed correctly to "
            # "year/month/day/hour/minute/second/... {ttup}.".format(
            #    tstr=timestring, ttup=timetuple), 2)
            return None

        utc_in_secs = calendar.timegm(timetuple)

        return int(utc_in_secs) + _tzd_to_seconds(
            timestring[TIMEDATE_FORMAT_LENGTH:])
    except (TypeError, ValueError):
        return None


def bytestotime(timebytes):
    try:
        return stringtotime(timebytes.decode('ascii'))
    except UnicodeDecodeError:
        return None


def timetopretty(timeinseconds):
    """
    Return pretty version of time
    """
    return time.asctime(time.localtime(timeinseconds))


def prettytotime(prettystring):
    """
    Converts time like "Mon Jun 5 11:00:23" to epoch sec, or None
    """
    try:
        return time.mktime(time.strptime(prettystring))
    except ValueError:
        return None


def inttopretty(seconds):
    """
    Convert num of seconds to readable string like "2 hours".
    """
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


def genstrtotime(timestr, ref_time=None, rp=None, session_times=None):
    """
    Convert a generic time string to a time in seconds

    rp is used when the time is of the form "4B" or similar.  Then the
    times of the increments of that particular file are used.
    """
    if ref_time is None:
        ref_time = getcurtime()
    if timestr == "now":
        return ref_time

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
    t = stringtotime(timestr) or stringtotime(timestr + _get_tzd())
    if t:
        return t

    # Test for time given as number of backups, like 3B
    if _session_regexp.search(timestr):
        return _time_from_session(int(timestr[:-1]), rp, session_times)

    # Try for long time, like "Mon Jun 5 11:00:23 1990"
    t = prettytotime(timestr)
    if t is not None:
        return t

    try:  # test for an interval, like "2 days ago"
        return ref_time - _intervalstr_to_seconds(timestr)
    except TimeException:
        pass

    # Now check for dates like 2001/3/23
    match = _genstr_date_regexp1.search(timestr) or \
        _genstr_date_regexp2.search(timestr)
    if not match:
        error()
    timestr = "%s-%02d-%02dT00:00:00%s" % (match.group('year'),
                                           int(match.group('month')),
                                           int(match.group('day')), _get_tzd())
    t = stringtotime(timestr)
    if t is not None:
        return t
    else:
        error()


def _intervalstr_to_seconds(interval_string):
    """
    Convert a string expressing an interval (e.g. "4D2s") to seconds
    """

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


def _get_tzd(timeinseconds=None):
    """
    Return w3's timezone identification string.

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
    assert 0 <= hours <= 23, (
        "Hours {hrs} must be between 0 and 23".format(hrs=hours))
    assert 0 <= minutes <= 59, (
        "Minutes {mins} must be between 0 and 59".format(mins=minutes))
    return "%s%02d%s%02d" % (prefix, hours, time_separator, minutes)


def _tzd_to_seconds(tzd):
    """
    Given w3c compliant TZD, return how far ahead UTC is, else raise
    ValueError exception.
    """
    if tzd == "Z":
        return 0
    if not (len(tzd) == 6
            and (tzd[0] == "-" or tzd[0] == "+")
            and (tzd[3] == ":" or tzd[3] == "-")):
        raise ValueError(
            "Only timezones like +08:00 are accepted and not '{tzd}'.".format(
                tzd=tzd))
    return -60 * (60 * int(tzd[:3]) + int(tzd[4:]))


def _time_from_session(session_num, rp=None, session_times=None):
    """
    Return time in seconds of given backup

    The current mirror is session_num 0, the next oldest increment has
    number 1, etc.  Requires that the Globals.rbdir directory be set by default.

    session_times is assumed to be a pre-sorted list of times as epochs.
    """
    if session_times is None:  # compat200
        if rp is None:
            rp = Globals.rbdir
        session_times = rp.conn.restore.MirrorStruct.get_increment_times()
    if len(session_times) <= session_num:
        return session_times[0]  # Use oldest if too few backups
    return session_times[-session_num - 1]
