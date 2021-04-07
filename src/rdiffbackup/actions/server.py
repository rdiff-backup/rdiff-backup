# Copyright 2021 the rdiff-backup project
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
A built-in rdiff-backup action plug-in to start a remote server process.
"""

import sys

from rdiffbackup import actions
from rdiff_backup import connection


class ServerAction(actions.BaseAction):
    """
    Start rdiff-backup in server mode (only meant for internal use).
    """
    name = "server"
    security = "server"
    # server has no specific sub-options

    def run(self):
        return connection.PipeConnection(sys.stdin.buffer,
                                         sys.stdout.buffer).Server()


def get_action_class():
    return ServerAction
