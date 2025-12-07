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

import argparse

from rdiffbackup import actions
from rdiffbackup.locations import repository
from rdiffbackup.singletons import consts, log


class RemoveAction(actions.BaseAction):
    """
    Remove the oldest increments or a certain file from a backup repository.
    """

    name = "remove"
    security = "validate"  # FIXME doesn't sound right, rather backup

    @classmethod
    def add_action_subparser(cls, sub_handler):
        subparser = super().add_action_subparser(sub_handler)
        entity_parsers = cls._get_subparsers(subparser, "entity", "increments", "file")
        entity_parsers["increments"].add_argument(
            "--older-than",
            metavar="TIME",
            required=True,
            help="remove increments older than given time",
        )
        entity_parsers["increments"].add_argument(
            "--size",
            action=argparse.BooleanOptionalAction,
            default=False,
            help="also output size of each increment (might take longer)",
        )
        entity_parsers["increments"].add_argument(
            "locations",
            metavar="[[USER@]SERVER::]PATH",
            nargs=1,
            help="location of repository to remove increments from",
        )
        entity_parsers["file"].add_argument(
            "--dry-run",
            action="store_true",
            help="don't remove anything, just check what would be removed",
        )
        entity_parsers["file"].add_argument(
            "locations",
            metavar="[[USER@]SERVER::]PATH",
            nargs=1,
            help="which file to remove",
        )
        return subparser

    def connect(self):
        conn_value = super().connect()
        if conn_value.is_connection_ok():
            self.repo = repository.Repo(
                self.connected_locations[0],
                self.values,
                must_be_writable=True,
                must_exist=True,
                can_be_sub_path=(self.values["entity"] == "file"),
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
        if self.values["entity"] == "increments" and self.repo.ref_index:
            log.Log(
                "Increments for sub-directory '{sd}' cannot be removed "
                "separately. "
                "Instead run on entire directory '{ed}'.".format(
                    sd=self.repo.orig_path, ed=self.repo.base_dir
                ),
                log.ERROR,
            )
            ret_code |= consts.RET_CODE_ERR

        if self.values["entity"] == "file":
            if not self.repo.ref_index:
                log.Log(
                    "File to remove must be within the repository, "
                    "it can't be the repository itself",
                    log.ERROR,
                )
                ret_code |= consts.RET_CODE_ERR
            elif b"rdiff-backup-data" in self.repo.ref_index:
                # FIXME This is knowledge of the internal structure of the repository
                log.Log(
                    "File to remove {fr} can't be an increment "
                    "or a part of the repository structure".format(
                        fr=self.values["locations"][0]
                    ),
                    log.ERROR,
                )
                ret_code |= consts.RET_CODE_ERR
            if self.values["dry_run"]:
                log.Log("Running in dry-run mode, nothing will be modified", log.NOTE)

        return ret_code

    def setup(self):
        # in setup we return as soon as we detect an issue to avoid changing
        # too much
        ret_code = super().setup()
        if ret_code & consts.RET_CODE_ERR:
            return ret_code

        ret_code = self.repo.setup()
        if ret_code & consts.RET_CODE_ERR:
            return ret_code

        return ret_code

    def run(self):
        """
        Check the given repository and remove old increments
        """
        ret_code = super().run()
        if ret_code & consts.RET_CODE_ERR:
            return ret_code

        if self.values["entity"] == "increments":
            ret_code |= self.repo.remove_increments_older_than()
        elif self.values["entity"] == "file":
            ret_code |= self.repo.remove_file()

        return ret_code


def get_plugin_class():
    return RemoveAction
