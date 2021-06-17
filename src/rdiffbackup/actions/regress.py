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

from rdiff_backup import (Globals, log, Security)
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

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.repo.exit()
        return super().__exit__(exc_type, exc_val, exc_tb)

    def connect(self):
        conn_value = super().connect()
        if conn_value:
            self.repo = repository.Repo(
                self.connected_locations[0], self.values.force,
                must_be_writable=True, must_exist=True
            )
        return conn_value

    def check(self):
        # we try to identify as many potential errors as possible before we
        # return, so we gather all potential issues and return only the final
        # result
        return_code = super().check()

        # we verify that the source repository is correct
        return_code |= self.repo.check()

        return return_code

    def setup(self):
        # in setup we return as soon as we detect an issue to avoid changing
        # too much
        return_code = super().setup()
        if return_code != 0:
            return return_code

        return_code = self._set_no_compression_regexp()
        if return_code != 0:
            return return_code

        owners_map = {
            "users_map": self.values.user_mapping_file,
            "groups_map": self.values.group_mapping_file,
            "preserve_num_ids": self.values.preserve_numerical_ids
        }
        return_code = self.repo.setup(owners_map=owners_map)
        if return_code != 0:
            return return_code

        # set the filesystem properties of the repository
        if Globals.get_api_version() < 201:  # compat200
            self.repo.base_dir.conn.fs_abilities.single_set_globals(
                self.repo.base_dir, 0)  # read_only=False
            self.repo.setup_quoting()

        # TODO validate how much of the following lines and methods
        # should go into the directory/repository modules
        if log.Log.verbosity > 0:
            try:  # the source repository must be writable
                log.Log.open_logfile(
                    self.repo.data_dir.append(self.name + ".log"))
            except (log.LoggerError, Security.Violation) as exc:
                log.Log("Unable to open logfile due to exception '{ex}'".format(
                    ex=exc), log.ERROR)
                return 1

        return 0

    def run(self):
        """
        Check the given repository and regress it if necessary
        """
        return self._operate_regress(noticeable=True)


def get_plugin_class():
    return RegressAction
