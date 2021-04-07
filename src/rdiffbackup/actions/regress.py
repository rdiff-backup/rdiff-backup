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
A built-in rdiff-backup action plug-in to regress a failed back-up from a
back-up repository.
"""

from rdiff_backup import (log, Security)
from rdiffbackup import actions
from rdiffbackup.locations import repository


class RegressAction(actions.BaseAction):
    """
    Regress a backup repository, i.e. remove the last (failed) incremental
    backup and reverse to the last known good mirror.
    """
    name = "regress"
    security = "backup"
    parent_parsers = [actions.COMPRESSION_PARSER, actions.TIMESTAMP_PARSER,
                      actions.USER_GROUP_PARSER]

    @classmethod
    def add_action_subparser(cls, sub_handler):
        subparser = super().add_action_subparser(sub_handler)
        subparser.add_argument(
            "locations", metavar="[[USER@]SERVER::]PATH", nargs=1,
            help="location of repository to check and possibly regress")
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

        # we verify that the source repository is correct
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
            self.source.base_dir, 0)  # read_only=False
        self.source.init_quoting(self.values.chars_to_quote)

        # TODO validate how much of the following lines and methods
        # should go into the directory/repository modules
        self._init_user_group_mapping(self.source.base_dir.conn)
        if self.log.verbosity > 0:
            try:  # the source repository must be writable
                self.log.open_logfile(
                    self.source.data_dir.append(self.name + ".log"))
            except (log.LoggerError, Security.Violation) as exc:
                self.log("Unable to open logfile due to '{exc}'".format(
                    exc=exc), self.log.ERROR)
                return 1

        return 0

    def run(self):
        """
        Check the given repository and regress it if necessary
        """
        if self.source.needs_regress():
            return self.source.regress()
        else:
            self.log("Given repository doesn't need to be regressed",
                     self.log.NOTE)
            return 0  # all is good


def get_action_class():
    return RegressAction
