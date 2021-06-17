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
The well known psutil library isn't really working the way I expect,
especially not under Windows, hence our own implementation is used.

It's perhaps not the most efficient approach but it doesn't need to be as
it's called only seldomly.
"""
import os
import subprocess


def get_pid_name(pid):
    """
    Gets a Process ID as integer or string and returns a process/image name
    Returns None if no process is running with the given PID
    """
    if os.name == "nt":
        cmd = ("tasklist", "/nh", "/fi", "pid eq {pp}".format(pp=pid))
    else:
        cmd = ("ps", "q", str(pid), "o", "comm=", "o", "pid=")
    output = subprocess.run(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=False
    ).stdout.decode().split()
    if output and output[1] == str(pid):
        return output[0]  # image/process name
    else:
        return None
