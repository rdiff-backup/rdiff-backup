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

from rdiff_backup import Globals
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
            self.repo = repository.Repo(
                self.connected_locations[0], self.values.force,
                must_be_writable=False, must_exist=True, can_be_sub_path=True
            )
        return conn_value

    def check(self):
        # we try to identify as many potential errors as possible before we
        # return, so we gather all potential issues and return only the final
        # result
        ret_code = super().check()

        # we verify that source repository is correct
        ret_code |= self.repo.check()

        return ret_code

    def setup(self):
        # in setup we return as soon as we detect an issue to avoid changing
        # too much
        ret_code = super().setup()
        if ret_code & Globals.RET_CODE_ERR:
            return ret_code

        ret_code = self.repo.setup()
        if ret_code & Globals.RET_CODE_ERR:
            return ret_code

        if Globals.get_api_version() < 201:  # compat200
            # set the filesystem properties of the repository
            self.repo.base_dir.conn.fs_abilities.single_set_globals(
                self.repo.base_dir, 1)  # read_only=True
            self.repo.setup_quoting()

        self.action_time = self.repo.get_parsed_time(self.values.at)
        if self.action_time is None:
            return Globals.RET_CODE_ERR

        return Globals.RET_CODE_OK

    def run(self):
        ret_code = super().run()
        if ret_code & Globals.RET_CODE_ERR:
            return ret_code

        if Globals.get_api_version() < 201:  # compat200
            return self.repo.base_dir.conn.compare.Verify(
                self.repo.ref_path, self.repo.ref_inc, self.action_time)
        else:
            return self.repo.verify(self.action_time)

        return ret_code


def get_plugin_class():
    return VerifyAction
