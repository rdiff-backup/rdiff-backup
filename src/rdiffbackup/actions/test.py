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
from rdiff_backup import SetConnections


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
        return_code = super().pre_check()
        # validate that all locations are remote
        for location in self.values.locations:
            (file_host, file_path, err) = SetConnections.parse_location(location)
            if err:
                self.log(err, self.log.ERROR)
                return_code |= 1  # binary 'or' to always get 1
            elif not file_host:
                self.log("Only remote locations can be tested but '{loc}' "
                         "isn't remote.".format(loc=location), self.log.ERROR)
                return_code |= 1  # binary 'or' to always get 1

        return return_code

    def check(self):
        # we call the parent check only to output the failed connections
        return_code = super().check()

        # even if some connections are bad, we want to validate the remaining
        # ones later on. The 'None' filter keeps only trueish values.
        self.connected_locations = list(filter(None, self.connected_locations))
        if self.connected_locations:
            # at least one location is apparently valid
            return 0
        else:
            return return_code

    def run(self):
        result = SetConnections.TestConnections(self.connected_locations)
        return result

def get_action_class():
    return TestAction
