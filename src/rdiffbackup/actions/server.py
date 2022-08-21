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

import os
import sys

from rdiffbackup import actions
from rdiff_backup import (connection, Globals, log, Security)


class ServerAction(actions.BaseAction):
    """
    Start rdiff-backup in server mode (only meant for internal use).
    """
    name = "server"
    security = "server"
    parent_parsers = [actions.RESTRICT_PARSER]

    @classmethod
    def add_action_subparser(cls, sub_handler):
        subparser = super().add_action_subparser(sub_handler)
        subparser.add_argument(
            "--debug", action="store_true",
            help="Allow for remote python debugging (rpdb) using netcat")
        return subparser

    def __init__(self, values):
        super().__init__(values)
        if 'debug' in self.values and self.values.debug:
            self._set_breakpoint()

    def connect(self):
        conn_value = super().connect()
        if conn_value:
            Security.initialize(self.get_security_class(), [],
                                security_level=self.values.restrict_mode,
                                restrict_path=self.values.restrict_path)
        return conn_value

    def run(self):
        ret_code = super().run()
        if ret_code & Globals.RET_CODE_ERR:
            return ret_code

        ret_code |= connection.PipeConnection(sys.stdin.buffer,
                                              sys.stdout.buffer).Server()
        return ret_code

    def _set_breakpoint(self):  # pragma: no cover
        """
        Set a breakpoint for remote debugging

        Use the environment variable RDIFF_BACKUP_DEBUG to set a non-default
        listening address and/or port (default is 127.0.0.1:4444).
        Valid values are 'addr', 'addr:port' or ':port'.
        """
        try:
            import rpdb
            debug_values = os.getenv("RDIFF_BACKUP_DEBUG", "").split(":")
            if debug_values != [""]:
                if debug_values[0]:
                    debug_addr = debug_values[0]
                else:
                    debug_addr = "127.0.0.1"
                if len(debug_values) > 1:
                    debug_port = int(debug_values[1])
                else:
                    debug_port = 4444
                rpdb.set_trace(addr=debug_addr, port=debug_port)
            else:
                # connect to the default 127.0.0.1:4444
                rpdb.set_trace()
        except ImportError:
            log.Log("Remote debugging impossible, please install rpdb",
                    log.Log.WARNING)


def get_plugin_class():
    return ServerAction
