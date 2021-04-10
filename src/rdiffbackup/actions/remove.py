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
A built-in rdiff-backup action plug-in to remove increments from a back-up
repository.
"""

from rdiff_backup import (log, manage, restore, Security, Time)
from rdiffbackup import actions
from rdiffbackup.locations import repository


class RemoveAction(actions.BaseAction):
    """
    Remove the oldest increments from a backup repository.
    """
    name = "remove"
    security = "validate"  # FIXME doesn't sound right, rather backup

    @classmethod
    def add_action_subparser(cls, sub_handler):
        subparser = super().add_action_subparser(sub_handler)
        entity_parsers = cls._get_subparsers(
            subparser, "entity", "increments")
        entity_parsers["increments"].add_argument(
            "--older-than", metavar="TIME",
            help="remove increments older than given time")
        entity_parsers["increments"].add_argument(
            "locations", metavar="[[USER@]SERVER::]PATH", nargs=1,
            help="location of repository to remove increments from")
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

        # the source directory must directly point at the base directory of
        # the repository
        if self.source.restore_index:
            self.log("Increments for directory '{odir}' cannot be removed "
                     "separately.\n"
                     "Instead run on entire directory '{bdir}'.".format(
                         odir=self.source.orig_path.get_safepath(),
                         bdir=self.source.base_dir.get_safepath()),
                     self.log.ERROR)
            return_code |= 1

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
        Check the given repository and remove old increments
        """

        action_time = self._get_parsed_time(self.values.older_than)
        if action_time is None:
            return 1
        manage.delete_earlier_than(self.source.base_dir, action_time)

        return 0

    def _get_parsed_time(self, time_string):
        """
        Check remove older than time_string, return time in seconds

        Return None if the time string can't be interpreted as such, or
        if more than one increment would be removed, without the force option,
        or if no increment would be removed.
        """
        action_time = super()._get_parsed_time(time_string)
        if action_time is None:
            return None

        times_in_secs = [
            inc.getinctime() for inc in restore.get_inclist(
                self.source.incs_dir)
        ]
        times_in_secs = [t for t in times_in_secs if t < action_time]
        if not times_in_secs:
            self.log("No increments older than {atim} found, exiting.".format(
                atim=Time.timetopretty(action_time)), self.log.NOTE)
            return None

        times_in_secs.sort()
        pretty_times = "\n".join(map(Time.timetopretty, times_in_secs))
        if len(times_in_secs) > 1:
            if not self.values.force:
                self.log(
                    "Found {lent} relevant increments, dated:\n{ptim}\n"
                    "If you want to delete multiple increments in this way, "
                    "use the --force option.".format(lent=len(times_in_secs),
                                                     ptim=pretty_times),
                    self.log.ERROR)
                return None
            else:
                self.log("Deleting increments at times:\n{ptim}".format(
                    ptim=pretty_times), self.log.NOTE)
        else:
            self.log("Deleting increment at time:\n{ptim}".format(
                ptim=pretty_times), self.log.NOTE)
        # make sure we don't delete current increment
        return times_in_secs[-1] + 1


def get_action_class():
    return RemoveAction
