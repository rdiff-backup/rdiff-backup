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

"""Misc statistics methods, pertaining to dir and session stat files"""

import time
import Globals, Hardlink, increment, log, statistics, Time

# This is the RPath of the directory statistics file, and the
# associated open file.  It will hold a line of statistics for
# each directory that is backed up.
_dir_stats_rp = None
_dir_stats_fp = None

# This goes at the beginning of the directory statistics file and
# explains the format.
_dir_stats_header = """# rdiff-backup directory statistics file
#
# Each line is in the following format:
# RelativeDirName %s
""" % " ".join(statistics.StatsObj.stat_file_attrs)

def open_dir_stats_file():
	"""Open directory statistics file, write header"""
	global _dir_stats_fp, _dir_stats_rp
	assert not _dir_stats_fp, "Directory file already open"

	if Globals.compression: suffix = "data.gz"
	else: suffix = "data"
	_dir_stats_rp = increment.get_inc(
		Globals.rbdir.append("directory_statistics"), suffix, Time.curtime)

	if _dir_stats_rp.lstat():
		log.Log("Warning, statistics file %s already exists, appending" %
				_dir_stats_rp.path, 2)
		_dir_stats_fp = _dir_stats_rp.open("ab", Globals.compression)
	else: _dir_stats_fp = _dir_stats_rp.open("wb", Globals.compression)
	_dir_stats_fp.write(_dir_stats_header)

def write_dir_stats_line(statobj, index):
	"""Write info from statobj about rpath to statistics file"""
	if Globals.null_separator:
		_dir_stats_fp.write(statobj.get_stats_line(index, None) + "\0")
	else: _dir_stats_fp.write(statobj.get_stats_line(index) + "\n")

def close_dir_stats_file():
	"""Close directory statistics file if its open"""
	global _dir_stats_fp
	if _dir_stats_fp:
		_dir_stats_fp.close()
		_dir_stats_fp = None

def write_session_statistics(statobj):
	"""Write session statistics into file, log"""
	stat_inc = increment.get_inc(
		Globals.rbdir.append("session_statistics"), "data", Time.curtime)
	statobj.StartTime = Time.curtime
	statobj.EndTime = time.time()

	# include hardlink data and dir stats in size of increments
	if Globals.preserve_hardlinks and Hardlink.final_inc:
		# include hardlink data in size of increments
		statobj.IncrementFiles += 1
		statobj.IncrementFileSize += Hardlink.final_inc.getsize()
	if _dir_stats_rp and _dir_stats_rp.lstat():
		statobj.IncrementFiles += 1
		statobj.IncrementFileSize += _dir_stats_rp.getsize()

	statobj.write_stats_to_rp(stat_inc)
	if Globals.print_statistics:
		message = statobj.get_stats_logstring("Session statistics")
		log.Log.log_to_file(message)
		Globals.client_conn.sys.stdout.write(message)



