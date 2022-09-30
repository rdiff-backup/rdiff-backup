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

from rdiff_backup import (Globals, log, restore, selection)
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
        ret_code = super().check()

        # we validate that the discovered restore type and the given options
        # fit together
        if self.repo.ref_type == "inc":
            if self.values.at:
                log.Log("You can't give an increment file and a time to "
                        "restore at the same time.", log.ERROR)
                ret_code |= Globals.RET_CODE_ERR
            elif not self.values.increment:
                self.values.increment = True
        elif self.repo.ref_type in ("base", "subpath"):
            if self.values.increment:
                log.Log("You can't use the --increment option and _not_ "
                        "give an increment file", log.ERROR)
                ret_code |= Globals.RET_CODE_ERR
            elif not self.values.at:
                self.values.at = "now"

        # it's dangerous to restore a sub-path and use selection at the same
        # time, rdiff-backup might remove files in the target directory
        # see issue #463
        if self.values.selections and self.repo.ref_index:
            possible_file_selections = set((
                'include', 'exclude',
                'exclude-filelist', 'include-filelist',
                'exclude-filelist-stdin', 'include-filelist-stdin',
                'exclude-globbing-filelist', 'include-globbing-filelist',
                'exclude-globbing-filelist-stdin',
                'include-globbing-filelist-stdin',
                'exclude-regexp', 'include-regexp'))
            file_selections = [x[0] for x in self.values.selections
                               if x[0] in possible_file_selections]
            if file_selections:
                log.Log("You can't combine restoring of a sub-path and file "
                        "selection, result would be unpredictable and "
                        "could lead to data loss", log.ERROR)
                ret_code |= Globals.RET_CODE_ERR

        # we verify that source directory and target repository are correct
        ret_code |= self.repo.check()
        ret_code |= self.dir.check()

        return ret_code

    def setup(self):
        # in setup we return as soon as we detect an issue to avoid changing
        # too much
        ret_code = super().setup()
        if ret_code & Globals.RET_CODE_ERR:
            return ret_code

        ret_code |= self._set_no_compression_regexp()
        if ret_code & Globals.RET_CODE_ERR:
            return ret_code

        ret_code |= self.repo.setup(action_name=self.name)
        if ret_code & Globals.RET_CODE_ERR:
            return ret_code

        owners_map = {
            "users_map": self.values.user_mapping_file,
            "groups_map": self.values.group_mapping_file,
            "preserve_num_ids": self.values.preserve_numerical_ids
        }
        ret_code |= self.dir.setup(self.repo, owners_map=owners_map)
        if ret_code & Globals.RET_CODE_ERR:
            return ret_code

        # TODO validate how much of the following lines and methods
        # should go into the directory/repository modules

        # set the filesystem properties of the repository
        if Globals.get_api_version() < 201:  # compat200
            self.dir.base_dir.conn.fs_abilities.restore_set_globals(
                self.dir.base_dir)
            self.repo.setup_quoting()

        if self.values.at:
            self.action_time = self.repo.get_parsed_time(self.values.at)
            if self.action_time is None:
                return ret_code | Globals.RET_CODE_ERR
        elif self.values.increment:
            self.action_time = self.repo.orig_path.getinctime()
        else:  # this should have been catched in the check method
            log.Log("This shouldn't happen but neither restore time nor "
                    "an increment have been identified so far", log.ERROR)
            return ret_code | Globals.RET_CODE_ERR
        (select_opts, select_data) = selection.get_prepared_selections(
            self.values.selections)
        # We must set both sides because restore filtering is different from
        # select filtering.  For instance, if a file is excluded it should
        # not be deleted from the target directory.
        self.repo.set_select(select_opts, select_data, self.dir.base_dir)
        self.dir.set_select(select_opts, select_data)

        return ret_code

    def run(self):
        ret_code = super().run()
        if ret_code & Globals.RET_CODE_ERR:
            return ret_code

        # This is more a check than a part of run, but because backup does
        # the regress in the run section, we also do the check here...
        ret_code |= self._operate_regress(try_regress=False)
        if ret_code & Globals.RET_CODE_ERR:
            # source could be read-only, so we don't try to regress it
            log.Log("Previous backup to {rp} seems to have failed. "
                    "Use rdiff-backup to 'regress' first the failed backup, "
                    "then try again to restore".format(
                        rp=self.repo.base_dir), log.ERROR)
            return ret_code
        try:
            if Globals.get_api_version() < 201:  # compat200
                restore.Restore(self.repo.ref_path, self.repo.ref_inc,
                                self.dir.base_dir, self.action_time)
            else:
                ret_code |= self._operate_restore()
        except OSError as exc:
            log.Log("Could not complete restore due to exception '{ex}'".format(
                ex=exc), log.ERROR)
            return ret_code | Globals.RET_CODE_ERR
        else:
            if ret_code & Globals.RET_CODE_ERR:
                log.Log("Restore somehow failed", log.ERROR)
            else:
                log.Log("Restore successfully finished", log.INFO)
            return ret_code

    def _operate_restore(self):
        """
        Execute the actual restore operation
        """
        log.Log(
            "Starting restore operation from source path {sp} to destination "
            "path {dp}".format(sp=self.repo.base_dir,
                               dp=self.dir.base_dir), log.NOTE)

        self.repo.init_loop(self.action_time)
        target_iter = self.dir.get_sigs_select()
        src_diff_iter = self.repo.get_diffs(target_iter)
        self.dir.apply(src_diff_iter)
        self.repo.finish_loop()

        return Globals.RET_CODE_OK


def get_plugin_class():
    return RestoreAction
