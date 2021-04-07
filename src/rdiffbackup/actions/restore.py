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
A built-in rdiff-backup action plug-in to restore a certain state of a back-up
repository to a directory.
"""

from rdiff_backup import (log, restore, selection, Security)
from rdiffbackup import actions
from rdiffbackup.locations import (directory, repository)


class RestoreAction(actions.BaseAction):
    """
    Restore a backup at a given time (default is latest) from a repository
    to a target directory.
    """
    name = "restore"
    security = "restore"
    parent_parsers = [
        actions.CREATION_PARSER, actions.COMPRESSION_PARSER,
        actions.SELECTION_PARSER, actions.FILESYSTEM_PARSER,
        actions.USER_GROUP_PARSER,
    ]

    @classmethod
    def add_action_subparser(cls, sub_handler):
        subparser = super().add_action_subparser(sub_handler)
        restore_group = subparser.add_mutually_exclusive_group()
        restore_group.add_argument(
            "--at", metavar="TIME",
            help="restore files as of a specific time")
        restore_group.add_argument(
            "--increment", action="store_true",
            help="restore from a specific increment as first parameter")
        subparser.add_argument(
            "locations", metavar="[[USER@]SERVER::]PATH", nargs=2,
            help="locations of backup REPOSITORY/INCREMENT and to which TARGET_DIR to restore")
        return subparser

    def connect(self):
        conn_value = super().connect()
        if conn_value:
            self.source = repository.ReadRepo(self.connected_locations[0],
                                              self.log, self.values.force)
            self.target = directory.WriteDir(self.connected_locations[1],
                                             self.log, self.values.force,
                                             self.values.create_full_path)
        return conn_value

    def check(self):
        # we try to identify as many potential errors as possible before we
        # return, so we gather all potential issues and return only the final
        # result
        return_code = super().check()

        # we validate that the discovered restore type and the given options
        # fit together
        if self.source.restore_type == "inc":
            if self.values.at:
                self.log("You can't give an increment file and a time to restore "
                         "at the same time.", self.log.ERROR)
                return_code |= 1
            elif not self.values.increment:
                self.values.increment = True
        elif self.source.restore_type in ("base", "subdir"):
            if self.values.increment:
                self.log("You can't use the --increment option and _not_ "
                         "give an increment file", self.log.ERROR)
                return_code |= 1
            elif not self.values.at:
                self.values.at = "now"

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

        # TODO validate how much of the following lines and methods
        # should go into the directory/repository modules
        try:
            self.target.base_dir.conn.fs_abilities.restore_set_globals(
                self.target.base_dir)
        except IOError as exc:
            self.log("Could not begin restore due to\n{exc}".format(exc=exc),
                     self.log.ERROR)
            return 1
        self.source.init_quoting(self.values.chars_to_quote)
        self._init_user_group_mapping(self.target.base_dir.conn)
        if self.log.verbosity > 0:
            try:  # the source repository could be read-only
                self.log.open_logfile(
                    self.source.data_dir.append("restore.log"))
            except (log.LoggerError, Security.Violation) as exc:
                self.log("Unable to open logfile due to '{exc}'".format(
                    exc=exc), self.log.WARNING)

        # we need now to identify the actual time of restore
        self.inc_rpath = self.source.data_dir.append_path(
            b'increments', self.source.restore_index)
        if self.values.at:
            self.action_time = self._get_parsed_time(self.values.at,
                                                     ref_rp=self.inc_rpath)
            if self.action_time is None:
                return 1
        elif self.values.increment:
            self.action_time = self.source.orig_path.getinctime()
        else:  # this should have been catched in the check method
            self.log("This shouldn't happen but neither restore time nor "
                     "an increment have been identified so far", self.log.ERROR)
            return 1
        (select_opts, select_data) = selection.get_prepared_selections(
            self.values.selections)
        # We must set both sides because restore filtering is different from
        # select filtering.  For instance, if a file is excluded it should
        # not be deleted from the target directory.
        self.source.set_select(select_opts, select_data, self.target.base_dir)
        self.target.set_select(select_opts, select_data)

        return 0  # all is good

    def run(self):

        # This is more a check than a part of run, but because backup does
        # the regress in the run section, we also do the check here...
        if self.source.needs_regress():
            # source could be read-only, so we don't try to regress it
            self.log("Previous backup to {rp} seems to have failed. "
                     "Use rdiff-backup to 'regress' first the failed backup, "
                     "then try again to restore.".format(
                         rp=self.source.base_dir.get_safepath()),
                     self.log.ERROR)
            return 1
        try:
            restore.Restore(
                self.source.base_dir.new_index(self.source.restore_index),
                self.inc_rpath, self.target.base_dir, self.action_time)
        except IOError as exc:
            self.log("Could not complete restore due to\n{exc}".format(exc=exc),
                     self.log.ERROR)
            return 1
        else:
            self.log("Restore successfully finished", self.log.INFO)
            return 0


def get_action_class():
    return RestoreAction
