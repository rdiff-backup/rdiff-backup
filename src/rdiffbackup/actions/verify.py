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
A built-in rdiff-backup action plug-in to verify a repository.

This plug-in verifies that files in a repository at a given time
have the correct hash.
"""

from rdiffbackup import actions
from rdiffbackup.locations import repository


class VerifyAction(actions.BaseAction):
    """
    Verify that files in a backup repository correspond to their stored hash,
    or that servers are properly reachable.
    """
    name = "verify"
    security = "validate"

    @classmethod
    def add_action_subparser(cls, sub_handler):
        subparser = super().add_action_subparser(sub_handler)
        subparser.add_argument(
            "--at", metavar="TIME", default="now",
            help="as of which time to check the files' hashes (default is now/latest)")
        subparser.add_argument(
            "locations", metavar="[[USER@]SERVER::]PATH", nargs=1,
            help="location of repository where to check files' hashes")
        return subparser

    def connect(self):
        conn_value = super().connect()
        if conn_value:
            self.source = repository.ReadRepo(self.connected_locations[0],
                                              self.log, self.values.force)
        return conn_value

    def check(self):
        # we try to identify as many potential errors as possible before we
        # return, so we gather all potential issues and return only the final
        # result
        return_code = super().check()

        # we verify that source repository is correct
        return_code |= self.source.check()

        return return_code

    def setup(self):
        # in setup we return as soon as we detect an issue to avoid changing
        # too much
        return_code = super().setup()
        if return_code != 0:
            return return_code

        return_code = self.source.setup()
        if return_code != 0:
            return return_code

        # set the filesystem properties of the repository
        self.source.base_dir.conn.fs_abilities.single_set_globals(
            self.source.base_dir, 1)  # read_only=True
        self.source.init_quoting(self.values.chars_to_quote)

        self.mirror_rpath = self.source.base_dir.new_index(
            self.source.restore_index)
        self.inc_rpath = self.source.data_dir.append_path(
            b'increments', self.source.restore_index)

        self.action_time = self._get_parsed_time(self.values.at,
                                                 ref_rp=self.inc_rpath)
        if self.action_time is None:
            return 1

        return 0  # all is good

    def run(self):
        return self.source.base_dir.conn.compare.Verify(
            self.mirror_rpath, self.inc_rpath, self.action_time)


def get_action_class():
    return VerifyAction
