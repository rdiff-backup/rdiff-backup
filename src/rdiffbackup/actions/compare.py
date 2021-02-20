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

from rdiffbackup import actions


class CompareAction(actions.BaseAction):
    """
    Compare the content of a source directory with a backup repository
    at a given time, using multiple methods.
    """
    name = "compare"
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


def get_action_class():
    return CompareAction
