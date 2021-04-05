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
A built-in rdiff-backup action plug-in to compare with multiple means
a back-up repository with the current state of a directory.
Comparaison can be done using metadata, file content or hashes.
"""

from rdiff_backup import (compare, selection)
from rdiffbackup import actions
from rdiffbackup.locations import (directory, repository)


class CompareAction(actions.BaseAction):
    """
    Compare the content of a source directory with a backup repository
    at a given time, using multiple methods.
    """
    name = "compare"
    security = "validate"
    parent_parsers = [actions.SELECTION_PARSER]

    @classmethod
    def add_action_subparser(cls, sub_handler):
        subparser = super().add_action_subparser(sub_handler)
        subparser.add_argument(
            "--method", choices=["meta", "full", "hash"], default="meta",
            help="use metadata, complete file or hash to compare directories")
        subparser.add_argument(
            "--at", metavar="TIME", default="now",
            help="compare with the backup at the given time, default is 'now'")
        subparser.add_argument(
            "locations", metavar="[[USER@]SERVER::]PATH", nargs=2,
            help="locations of SOURCE_DIR and backup REPOSITORY to compare"
                 " (same order as for a backup)")
        return subparser

    def connect(self):
        conn_value = super().connect()
        if conn_value:
            self.source = directory.ReadDir(self.connected_locations[0],
                                            self.log, self.values.force)
            self.target = repository.ReadRepo(self.connected_locations[1],
                                              self.log, self.values.force)
        return conn_value

    def check(self):
        # we try to identify as many potential errors as possible before we
        # return, so we gather all potential issues and return only the final
        # result
        return_code = super().check()

        # we verify that source directory and target repository are correct
        return_code |= self.source.check()
        return_code |= self.target.check()

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

        return_code = self.target.setup()
        if return_code != 0:
            return return_code

        # set the filesystem properties of the repository
        self.target.base_dir.conn.fs_abilities.single_set_globals(
            self.target.base_dir, 1)  # read_only=True
        self.target.init_quoting(self.values.chars_to_quote)

        (select_opts, select_data) = selection.get_prepared_selections(
            self.values.selections)
        self.source.set_select(select_opts, select_data)

        self.mirror_rpath = self.target.base_dir.new_index(
            self.target.restore_index)
        self.inc_rpath = self.target.data_dir.append_path(
            b'increments', self.target.restore_index)

        self.action_time = self._get_parsed_time(self.values.at,
                                                 ref_rp=self.inc_rpath)
        if self.action_time is None:
            return 1

        return 0  # all is good

    def run(self):
        # call the right comparaison function for the chosen method
        compare_funcs = {
            "meta": compare.Compare,
            "hash": compare.Compare_hash,
            "full": compare.Compare_full
        }
        ret_code = compare_funcs[self.values.method](self.source.base_dir,
                                                     self.mirror_rpath,
                                                     self.inc_rpath,
                                                     self.action_time)
        return ret_code


def get_action_class():
    return CompareAction
