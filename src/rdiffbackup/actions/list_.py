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
A built-in rdiff-backup action plug-in to list increments and files in a
back-up repository.

The module is named with an underscore at the end to avoid overwriting the
builtin 'list' class.
"""

from rdiff_backup import (manage, restore)
from rdiffbackup import actions
from rdiffbackup.locations import repository
from rdiffbackup.utils.argopts import BooleanOptionalAction


class ListAction(actions.BaseAction):
    """
    List files at a given time, files changed since a certain time, or
    increments, with or without size, in a given backup repository.
    """
    name = "list"
    security = "validate"

    @classmethod
    def add_action_subparser(cls, sub_handler):
        subparser = super().add_action_subparser(sub_handler)
        entity_parsers = cls._get_subparsers(
            subparser, "entity", "files", "increments")
        time_group = entity_parsers["files"].add_mutually_exclusive_group()
        time_group.add_argument(
            "--changed-since", metavar="TIME",
            help="list files modified since given time")
        time_group.add_argument(
            "--at", metavar="TIME", default="now",
            help="list files at given time (default is now/latest)")
        entity_parsers["files"].add_argument(
            "locations", metavar="[[USER@]SERVER::]PATH", nargs=1,
            help="location of repository to list files from")
        entity_parsers["increments"].add_argument(
            "--size", action=BooleanOptionalAction, default=False,
            help="also output size of each increment (might take longer)")
        entity_parsers["increments"].add_argument(
            "locations", metavar="[[USER@]SERVER::]PATH", nargs=1,
            help="location of repository to list increments from")
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

        if self.values.entity == "files":
            if self.values.changed_since:
                self.action_time = self._get_parsed_time(
                    self.values.changed_since, ref_rp=self.inc_rpath)
            elif self.values.at:
                self.action_time = self._get_parsed_time(
                    self.values.at, ref_rp=self.inc_rpath)
            if self.action_time is None:
                return 1

        return 0  # all is good

    def run(self):
        if self.values.entity == "increments":
            if self.values.size:
                self._list_increments_sizes()
            else:
                self._list_increments()
        elif self.values.entity == "files":
            if self.values.changed_since:
                self._list_files_changed_since()
            elif self.values.at:
                self._list_files_at_time()
        return 0  # all is good

    def _list_increments_sizes(self):
        """
        Print out a summary of the increments
        """
        print(manage.list_increment_sizes(self.source.base_dir,
                                          self.source.restore_index))

    def _list_increments(self):
        """Print out a summary of the increments and their times"""
        incs = restore.get_inclist(self.inc_rpath)
        mirror_time = restore.MirrorStruct.get_mirror_time()
        if self.values.parsable_output:
            print(manage.describe_incs_parsable(incs, mirror_time,
                                                self.mirror_rpath))
        else:
            print(manage.describe_incs_human(incs, mirror_time,
                                             self.mirror_rpath))

    def _list_files_changed_since(self):
        """List all the files under rp that have changed since restoretime"""
        for rorp in self.source.base_dir.conn.restore.ListChangedSince(
                self.mirror_rpath, self.inc_rpath, self.action_time):
            # This is a hack, see restore.ListChangedSince for rationale
            print(str(rorp))

    def _list_files_at_time(self):
        """List files in archive under rp that are present at restoretime"""
        for rorp in self.source.base_dir.conn.restore.ListAtTime(
                self.mirror_rpath, self.inc_rpath, self.action_time):
            print(str(rorp))


def get_action_class():
    return ListAction
