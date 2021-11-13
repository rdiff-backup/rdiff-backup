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
"""list, delete, and otherwise manage increments"""

from . import Globals, log


def delete_earlier_than(baserp, time):  # compat200
    """Deleting increments older than time in directory baserp

    time is in seconds.  It will then delete any empty directories
    in the tree.  To process the entire backup area, the
    rdiff-backup-data directory should be the root of the tree.

    """
    baserp.conn.manage.delete_earlier_than_local(baserp, time)


# @API(delete_earlier_than_local, 200, 200)
def delete_earlier_than_local(baserp, time):
    """Like delete_earlier_than, but run on local connection for speed"""
    assert baserp.conn is Globals.local_connection, (
        "Function should be called only locally and not over '{conn}'.".format(
            conn=baserp.conn))

    def yield_files(rp):
        if rp.isdir():
            for filename in rp.listdir():
                for sub_rp in yield_files(rp.append(filename)):
                    yield sub_rp
        yield rp

    for rp in yield_files(baserp):
        if ((rp.isincfile() and rp.getinctime() < time)
                or (rp.isdir() and not rp.listdir())):
            log.Log("Deleting increment file {fi}".format(fi=rp), log.INFO)
            rp.delete()
