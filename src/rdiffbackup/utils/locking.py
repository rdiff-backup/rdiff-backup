# Copyright 2022 Eric Lavarde
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
"""
Portable locking utilities, defining lock and unlock functions
"""

# Shamelessly adapted from O'Reilly's Python Cookbook
# by Jonathan Feinberg, John Nielsen:
# https://www.oreilly.com/library/view/python-cookbook/0596001673/ch04s25.html

import os

# needs win32all to work on Windows
if os.name == 'nt':
    import pywintypes
    import win32con
    import win32file
    LOCK_EX = win32con.LOCKFILE_EXCLUSIVE_LOCK
    LOCK_SH = 0  # the default
    LOCK_NB = win32con.LOCKFILE_FAIL_IMMEDIATELY
    __overlapped = pywintypes.OVERLAPPED()

    def lock(file, flags):
        hfile = win32file._get_osfhandle(file.fileno())
        try:
            win32file.LockFileEx(hfile, flags, 0, 0xffff0000, __overlapped)
        except pywintypes.error as exc:
            if exc.winerror == 33 and exc.funcname == "LockFileEx":
                raise BlockingIOError(-1, exc.strerror,
                                      file.name, exc.winerror)
            else:
                raise

    def unlock(file):
        hfile = win32file._get_osfhandle(file.fileno())
        win32file.UnlockFileEx(hfile, 0, 0xffff0000, __overlapped)

elif os.name == 'posix':
    from fcntl import LOCK_EX, LOCK_SH, LOCK_NB  # noqa: F401 implicitly used
    import fcntl

    def lock(file, flags):
        fcntl.flock(file, flags)

    def unlock(file):
        fcntl.flock(file, fcntl.LOCK_UN)
else:  # pragma: no cover  # we will never test on other platforms
    raise RuntimeError(
        "Portable locking only defined for nt and posix platforms")
