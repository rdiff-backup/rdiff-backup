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
A wrapper around the psutil library, because it might not be installed,
and also because, under Windows, it doesn't act as always expected.
"""
import os
import subprocess


def _get_pid_name_psutil(pid):
    """
    Internal function to return the process name of a pid

    The function uses the psutil Python module
    """
    try:
        proc = psutil.Process(int(pid))
        status = proc.status()
    except psutil.NoSuchProcess:
        return None
    if status in (psutil.STATUS_DEAD, psutil.STATUS_ZOMBIE):
        return None
    else:
        return proc.name()


def _get_pid_name_ps(pid):
    """
    Internal function to return the process name of a pid

    The function uses the ps utility or tasklist (under Windows)
    """
    if os.name == "nt":
        cmd = ("tasklist", "/nh", "/fi", "pid eq {pp}".format(pp=pid))
    else:
        cmd = ("ps", "-p", str(pid), "-o", "comm=,pid=")
    output = subprocess.run(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=False
    ).stdout.decode().split()
    if output and output[1] == str(pid):
        return output[0]  # image/process name
    else:
        return None


# depending if psutil is installed or not, we have another implementation
# of get_pid_name
try:
    import psutil
    get_pid_name = _get_pid_name_psutil
except ModuleNotFoundError:
    get_pid_name = _get_pid_name_ps
