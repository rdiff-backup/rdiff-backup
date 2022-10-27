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

from rdiff_backup import (Globals, log, manage, Time)
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
            self.repo = repository.Repo(
                self.connected_locations[0], self.values.force,
                must_be_writable=True, must_exist=True
            )
        return conn_value

    def check(self):
        # we try to identify as many potential errors as possible before we
        # return, so we gather all potential issues and return only the final
        # result
        ret_code = super().check()

        # we verify that the source repository is correct
        ret_code |= self.repo.check()

        # the source directory must directly point at the base directory of
        # the repository
        if self.repo.ref_index:
            log.Log("Increments for sub-directory '{sd}' cannot be removed "
                    "separately. "
                    "Instead run on entire directory '{ed}'.".format(
                        sd=self.repo.orig_path,
                        ed=self.repo.base_dir), log.ERROR)
            ret_code |= Globals.RET_CODE_ERR

        return ret_code

    def setup(self):
        # in setup we return as soon as we detect an issue to avoid changing
        # too much
        ret_code = super().setup()
        if ret_code & Globals.RET_CODE_ERR:
            return ret_code

        ret_code = self.repo.setup(action_name=self.name)
        if ret_code & Globals.RET_CODE_ERR:
            return ret_code

        # set the filesystem properties of the repository
        if Globals.get_api_version() < 201:  # compat200
            self.repo.base_dir.conn.fs_abilities.single_set_globals(
                self.repo.data_dir, 0)  # read_only=False
            self.repo.setup_quoting()

        self.action_time = self._get_removal_time(self.values.older_than)
        if self.action_time is None:
            return ret_code | Globals.RET_CODE_ERR

        return ret_code

    def run(self):
        """
        Check the given repository and remove old increments
        """
        ret_code = super().run()
        if ret_code & Globals.RET_CODE_ERR:
            return ret_code

        if self.action_time < 0:  # no increment is old enough
            log.Log("No increment is older than '{ot}'".format(
                ot=self.values.older_than), log.WARNING)
            return ret_code | Globals.RET_CODE_WARN

        if Globals.get_api_version() < 201:
            manage.delete_earlier_than(self.repo.data_dir, self.action_time)
        else:
            self.repo.remove_increments_older_than(self.action_time)

        return ret_code

    def _get_removal_time(self, time_string):
        """
        Check remove older than time_string, return time in seconds

        Return None if the time string can't be interpreted as such, or
        if more than one increment would be removed, without the force option;
        or -1 if no increment would be removed.
        """
        action_time = self.repo.get_parsed_time(time_string)
        if action_time is None:
            return None

        times_in_secs = [
            inc.getinctime() for inc in self.repo.incs_dir.get_incfiles_list()
        ]
        times_in_secs = [t for t in times_in_secs if t < action_time]
        if not times_in_secs:
            log.Log("No increments older than {at} found, exiting.".format(
                at=Time.timetopretty(action_time)), log.NOTE)
            return -1

        times_in_secs.sort()
        pretty_times = "\n".join(map(Time.timetopretty, times_in_secs))
        if len(times_in_secs) > 1:
            if not self.values.force:
                log.Log(
                    "Found {ri} relevant increments, dates/times:\n{dt}\n"
                    "If you want to delete multiple increments in this way, "
                    "use the --force option.".format(
                        ri=len(times_in_secs), dt=pretty_times), log.ERROR)
                return None
            else:
                log.Log("Deleting increments at dates/times:\n{dt}".format(
                    dt=pretty_times), log.NOTE)
        else:
            log.Log("Deleting increment at date/time: {dt}".format(
                dt=pretty_times), log.NOTE)
        # make sure we don't delete current increment
        return times_in_secs[-1] + 1


def get_plugin_class():
    return RemoveAction
