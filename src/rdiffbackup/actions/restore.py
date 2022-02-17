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

from rdiff_backup import (Globals, log, restore, selection, Security)
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
            self.repo = repository.Repo(
                self.connected_locations[0], self.values.force,
                must_be_writable=False, must_exist=True, can_be_sub_path=True
            )
            self.dir = directory.WriteDir(self.connected_locations[1],
                                          self.values.force,
                                          self.values.create_full_path)
        return conn_value

    def check(self):
        # we try to identify as many potential errors as possible before we
        # return, so we gather all potential issues and return only the final
        # result
        return_code = super().check()

        # we validate that the discovered restore type and the given options
        # fit together
        if self.repo.restore_type == "inc":
            if self.values.at:
                log.Log("You can't give an increment file and a time to "
                        "restore at the same time.", log.ERROR)
                return_code |= 1
            elif not self.values.increment:
                self.values.increment = True
        elif self.repo.restore_type in ("base", "subdir"):
            if self.values.increment:
                log.Log("You can't use the --increment option and _not_ "
                        "give an increment file", log.ERROR)
                return_code |= 1
            elif not self.values.at:
                self.values.at = "now"

        # we verify that source directory and target repository are correct
        return_code |= self.repo.check()
        return_code |= self.dir.check()

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

        return_code = self.repo.setup()
        if return_code != 0:
            return return_code

        owners_map = {
            "users_map": self.values.user_mapping_file,
            "groups_map": self.values.group_mapping_file,
            "preserve_num_ids": self.values.preserve_numerical_ids
        }
        return_code = self.dir.setup(self.repo, owners_map=owners_map)
        if return_code != 0:
            return return_code

        # TODO validate how much of the following lines and methods
        # should go into the directory/repository modules

        # set the filesystem properties of the repository
        if Globals.get_api_version() < 201:  # compat200
            self.dir.base_dir.conn.fs_abilities.restore_set_globals(
                self.dir.base_dir)
            self.repo.setup_quoting()

        if log.Log.verbosity > 0:
            try:  # the source repository could be read-only
                log.Log.open_logfile(
                    self.repo.data_dir.append("restore.log"))
            except (log.LoggerError, Security.Violation) as exc:
                log.Log(
                    "Unable to open logfile due to exception '{ex}'".format(
                        ex=exc), log.WARNING)

        # we need now to identify the actual time of restore
        self.inc_rpath = self.repo.data_dir.append_path(
            b'increments', self.repo.restore_index)
        if self.values.at:
            self.action_time = self._get_parsed_time(self.values.at,
                                                     ref_rp=self.inc_rpath)
            if self.action_time is None:
                return 1
        elif self.values.increment:
            self.action_time = self.repo.orig_path.getinctime()
        else:  # this should have been catched in the check method
            log.Log("This shouldn't happen but neither restore time nor "
                    "an increment have been identified so far", log.ERROR)
            return 1
        (select_opts, select_data) = selection.get_prepared_selections(
            self.values.selections)
        # We must set both sides because restore filtering is different from
        # select filtering.  For instance, if a file is excluded it should
        # not be deleted from the target directory.
        self.repo.set_select(select_opts, select_data, self.dir.base_dir)
        self.dir.set_select(select_opts, select_data)

        return 0  # all is good

    def run(self):

        # This is more a check than a part of run, but because backup does
        # the regress in the run section, we also do the check here...
        if self._operate_regress(try_regress=False):
            # source could be read-only, so we don't try to regress it
            log.Log("Previous backup to {rp} seems to have failed. "
                    "Use rdiff-backup to 'regress' first the failed backup, "
                    "then try again to restore".format(
                        rp=self.repo.base_dir), log.ERROR)
            return 1
        try:
            if Globals.get_api_version() < 201:  # compat200
                restore.Restore(
                    self.repo.base_dir.new_index(self.repo.restore_index),
                    self.inc_rpath, self.dir.base_dir, self.action_time)
            else:
                self._operate_restore()
        except OSError as exc:
            log.Log("Could not complete restore due to exception '{ex}'".format(
                ex=exc), log.ERROR)
            return 1
        else:
            log.Log("Restore successfully finished", log.INFO)
            return 0

    def _operate_restore(self):
        """
        Execute the actual restore operation
        """
        log.Log(
            "Starting restore operation from source path {sp} to destination "
            "path {dp}".format(sp=self.repo.base_dir,
                               dp=self.dir.base_dir), log.NOTE)

        self.repo.initialize_restore(self.action_time)
        self.repo.initialize_rf_cache(self.inc_rpath)
        target_iter = self.dir.get_initial_iter()
        src_diff_iter = self.repo.get_diffs(target_iter)
        self.dir.patch(src_diff_iter)
        self.repo.close_rf_cache()


def get_plugin_class():
    return RestoreAction
