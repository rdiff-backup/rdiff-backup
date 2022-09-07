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

import yaml
from rdiff_backup import Globals, statistics, Time
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

        # set the filesystem properties of the repository
        if Globals.get_api_version() < 201:  # compat200
            self.repo.base_dir.conn.fs_abilities.single_set_globals(
                self.repo.base_dir, 1)  # read_only=True
            self.repo.setup_quoting()

        if self.values.entity == "files":
            self.action_time = self.repo.get_parsed_time(
                self.values.changed_since or self.values.at)
            if self.action_time is None:
                return ret_code | Globals.RET_CODE_ERR

        return ret_code

    def run(self):
        ret_code = super().run()
        if ret_code & Globals.RET_CODE_ERR:
            return ret_code

        if self.values.entity == "increments":
            if self.values.size:
                ret_code |= self._list_increments_sizes()
            else:
                ret_code |= self._list_increments()
        elif self.values.entity == "files":
            if self.values.changed_since:
                ret_code |= self._list_files_changed_since()
            elif self.values.at:
                ret_code |= self._list_files_at_time()
        return ret_code

    def _list_increments_sizes(self):
        """
        Print out a summary of the increments with their size and
        cumulative size
        """
        triples = self.repo.get_increments_sizes()

        if self.values.parsable_output:
            print(yaml.safe_dump(triples,
                                 explicit_start=True, explicit_end=True))
        else:
            stat_obj = statistics.StatsObj()  # used for byte summary string

            print("{: ^24} {: ^17} {: ^17}".format("Time", "Size",
                                                   "Cumulative size"))
            print("{:-^24} {:-^17} {:-^17}".format("", "", ""))
            # print the normal increments then the mirror
            for triple in triples[:-1]:
                print("{: <24} {: >17} {: >17}".format(
                    Time.timetopretty(triple["time"]),
                    stat_obj.get_byte_summary_string(triple["size"]),
                    stat_obj.get_byte_summary_string(triple["total_size"])))
            print("{: <24} {: >17} {: >17}  (current mirror)".format(
                Time.timetopretty(triples[-1]["time"]),
                stat_obj.get_byte_summary_string(triples[-1]["size"]),
                stat_obj.get_byte_summary_string(triples[-1]["total_size"])))
        return Globals.RET_CODE_OK

    def _list_increments(self):
        """
        Print out a summary of the increments and their times
        """
        incs = self.repo.get_increments()
        if self.values.parsable_output:
            if Globals.get_api_version() < 201:
                for inc in incs:
                    print("{ti} {it}".format(ti=inc["time"], it=inc["type"]))
            else:
                print(yaml.safe_dump(incs,
                                     explicit_start=True, explicit_end=True))
        else:
            print("Found {ni} increments:".format(ni=len(incs) - 1))
            for inc in incs[:-1]:
                print("    {ib}   {ti}".format(
                    ib=inc["base"], ti=Time.timetopretty(inc["time"])))
            print("Current mirror: {ti}".format(
                ti=Time.timetopretty(incs[-1]["time"])))  # time of the mirror
        return Globals.RET_CODE_OK

    def _list_files_changed_since(self):
        """List all the files under rp that have changed since restoretime"""
        if Globals.get_api_version() < 201:
            rorp_iter = self.repo.base_dir.conn.restore.ListChangedSince(
                self.repo.ref_path, self.repo.ref_inc, self.action_time)
        else:
            rorp_iter = self.repo.list_files_changed_since(self.action_time)
        for rorp in rorp_iter:
            # This is a hack, see restore.ListChangedSince for rationale
            print(str(rorp))
        return Globals.RET_CODE_OK

    def _list_files_at_time(self):
        """List files in archive under rp that are present at restoretime"""
        if Globals.get_api_version() < 201:
            rorp_iter = self.repo.base_dir.conn.restore.ListAtTime(
                self.repo.ref_path, self.repo.ref_inc, self.action_time)
        else:
            rorp_iter = self.repo.list_files_at_time(self.action_time)
        for rorp in rorp_iter:
            print(str(rorp))
        return Globals.RET_CODE_OK


def get_plugin_class():
    return ListAction
