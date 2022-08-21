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
A built-in rdiff-backup action plug-in to test servers.

This plug-in tests that all remote locations are properly reachable and
usable for a back-up.
"""

from rdiffbackup import actions
from rdiff_backup import Globals, log, SetConnections


class TestAction(actions.BaseAction):
    """
    Test that servers are properly reachable and usable for back-ups.
    """
    name = "test"
    security = "validate"

    @classmethod
    def add_action_subparser(cls, sub_handler):
        subparser = super().add_action_subparser(sub_handler)
        subparser.add_argument(
            "locations", metavar="[USER@]SERVER::PATH", nargs="+",
            help="location of remote repositories to check for connection")
        return subparser

    def pre_check(self):
        ret_code = super().pre_check()
        # validate that all locations are remote
        for location in self.values.locations:
            (file_host, file_path, err) = SetConnections.parse_location(location)
            if err:
                log.Log(err, log.ERROR)
                ret_code |= Globals.RET_CODE_ERR
            elif not file_host:
                log.Log("Only remote locations can be tested but location "
                        "'{lo}' isn't remote".format(lo=location), log.ERROR)
                ret_code |= Globals.RET_CODE_ERR

        return ret_code

    def check(self):
        # we call the parent check only to output the failed connections
        ret_code = super().check()

        # even if some connections are bad, we want to validate the remaining
        # ones later on. The 'None' filter keeps only trueish values.
        self.connected_locations = list(filter(None, self.connected_locations))
        if ret_code & Globals.RET_CODE_ERR:
            # at least one connection has failed
            if self.connected_locations:
                # at least one location is apparently valid, so no error
                return Globals.RET_CODE_WARN
            else:
                return ret_code
        else:
            return ret_code

    def run(self):
        ret_code = super().run()
        if ret_code & Globals.RET_CODE_ERR:
            return ret_code

        ret_code |= SetConnections.test_connections(self.connected_locations)
        return ret_code


def get_plugin_class():
    return TestAction
