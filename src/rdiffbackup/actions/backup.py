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
A built-in rdiff-backup action plug-in to backup a source to a target directory.
"""

import time

from rdiff_backup import (
    backup,
    Globals,
    log,
    selection,
    SetConnections,
    Time,
)
from rdiffbackup import actions
from rdiffbackup.locations import (directory, repository)


class BackupAction(actions.BaseAction):
    """
    Backup a source directory to a target backup repository.
    """
    name = "backup"
    security = "backup"
    parent_parsers = [
        actions.CREATION_PARSER, actions.COMPRESSION_PARSER,
        actions.SELECTION_PARSER, actions.FILESYSTEM_PARSER,
        actions.USER_GROUP_PARSER, actions.STATISTICS_PARSER,
    ]

    @classmethod
    def add_action_subparser(cls, sub_handler):
        subparser = super().add_action_subparser(sub_handler)
        subparser.add_argument(
            "locations", metavar="[[USER@]SERVER::]PATH", nargs=2,
            help="locations of SOURCE_DIR and to which REPOSITORY to backup")
        return subparser

    def connect(self):
        conn_value = super().connect()
        if conn_value:
            self.dir = directory.ReadDir(self.connected_locations[0],
                                         self.values.force)
            self.repo = repository.Repo(
                self.connected_locations[1], self.values.force,
                must_be_writable=True, must_exist=False,
                create_full_path=self.values.create_full_path
            )
        return conn_value

    def check(self):
        # we try to identify as many potential errors as possible before we
        # return, so we gather all potential issues and return only the final
        # result
        ret_code = super().check()

        # we verify that source directory and target repository are correct
        ret_code |= self.dir.check()
        ret_code |= self.repo.check()

        return ret_code

    def setup(self):
        # in setup we return as soon as we detect an issue to avoid changing
        # too much
        ret_code = super().setup()
        if ret_code & Globals.RET_CODE_ERR:
            return ret_code

        ret_code = self._set_no_compression_regexp()
        if ret_code & Globals.RET_CODE_ERR:
            return ret_code

        ret_code = self.dir.setup()
        if ret_code & Globals.RET_CODE_ERR:
            return ret_code

        owners_map = {
            "users_map": self.values.user_mapping_file,
            "groups_map": self.values.group_mapping_file,
            "preserve_num_ids": self.values.preserve_numerical_ids
        }
        ret_code = self.repo.setup(self.dir, owners_map=owners_map,
                                   action_name=self.name)
        if ret_code & Globals.RET_CODE_ERR:
            return ret_code

        # TODO validate how much of the following lines and methods
        # should go into the directory/repository modules
        if Globals.get_api_version() < 201:  # compat200
            SetConnections.BackupInitConnections(self.dir.base_dir.conn,
                                                 self.repo.base_dir.conn)
            self.repo.base_dir.conn.fs_abilities.backup_set_globals(
                self.dir.base_dir, self.values.force)
            self.repo.setup_quoting()

        previous_time = self.repo.get_mirror_time()
        if previous_time >= Time.getcurtime():
            log.Log("The last backup is not in the past. Aborting.",
                    log.ERROR)
            return ret_code | Globals.RET_CODE_ERR

        log.ErrorLog.open(Time.getcurtimestr(),
                          compress=self.values.compression)

        (select_opts, select_data) = selection.get_prepared_selections(
            self.values.selections)
        self.dir.set_select(select_opts, select_data)
        ret_code |= self._warn_if_infinite_recursion(self.dir.base_dir,
                                                     self.repo.base_dir)

        return ret_code

    def run(self):
        ret_code = super().run()
        if ret_code & Globals.RET_CODE_ERR:
            return ret_code

        # do regress the target directory if necessary
        ret_code |= self._operate_regress()
        if ret_code & Globals.RET_CODE_ERR:
            # regress was necessary and failed
            return ret_code
        previous_time = self.repo.get_mirror_time(refresh=True)
        if previous_time < 0 or previous_time >= Time.getcurtime():
            log.Log("Either there is more than one current_mirror or "
                    "the last backup is not in the past. Aborting.",
                    log.ERROR)
            return ret_code | Globals.RET_CODE_ERR
        if Globals.get_api_version() < 201:  # compat200
            if previous_time:
                Time.setprevtime_compat200(previous_time)
                self.repo.base_dir.conn.Main.backup_touch_curmirror_local(
                    self.dir.base_dir, self.repo.base_dir)
                backup.mirror_and_increment_compat200(
                    self.dir.base_dir, self.repo.base_dir,
                    self.repo.incs_dir)
                self.repo.base_dir.conn.Main.backup_remove_curmirror_local()
            else:
                backup.mirror_compat200(
                    self.dir.base_dir, self.repo.base_dir)
                self.repo.base_dir.conn.Main.backup_touch_curmirror_local(
                    self.dir.base_dir, self.repo.base_dir)
            self.repo.base_dir.conn.Main.backup_close_statistics(time.time())
        else:  # API 201 and higher
            ret_code |= self._operate_backup(previous_time)

        return ret_code

    def _operate_backup(self, previous_time=None):
        """
        Execute the actual backup operation
        """
        log.Log(
            "Starting backup operation from source path {sp} to destination "
            "path {dp}".format(sp=self.dir.base_dir,
                               dp=self.repo.base_dir), log.NOTE)

        if previous_time:
            self.repo.touch_current_mirror(Time.getcurtimestr())

        source_rpiter = self.dir.get_select()
        dest_sigiter = self.repo.get_sigs(source_rpiter, previous_time)
        source_diffiter = self.dir.get_diffs(dest_sigiter)
        self.repo.apply(source_diffiter, previous_time)

        if previous_time:
            self.repo.remove_current_mirror()
        else:
            self.repo.touch_current_mirror(Time.getcurtimestr())

        self.repo.close_statistics(time.time())

        return Globals.RET_CODE_OK

    def _warn_if_infinite_recursion(self, rpin, rpout):
        """
        Warn user if target location is contained in source location
        """
        # Just a few heuristics, we don't have to get every case
        if rpout.conn is not rpin.conn:
            return Globals.RET_CODE_OK
        if len(rpout.path) <= len(rpin.path) + 1:
            return Globals.RET_CODE_OK
        if rpout.path[:len(rpin.path) + 1] != rpin.path + b'/':
            return Globals.RET_CODE_OK

        log.Log("The target directory '{td}' may be contained in the "
                "source directory '{sd}'. "
                "This could cause an infinite recursion. "
                "You may need to use the --exclude option "
                "(which you might already have done).".format(
                    td=rpout, sd=rpin), log.WARNING)
        return Globals.RET_CODE_WARN


def get_plugin_class():
    return BackupAction
