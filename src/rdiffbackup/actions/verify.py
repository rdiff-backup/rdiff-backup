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
A built-in rdiff-backup action plug-in to verify that servers are properly
reachables or files' hashes in a repository correct.
"""

from rdiffbackup import actions


class VerifyAction(actions.BaseAction):
    """
    Verify that files in a backup repository correspond to their stored hash,
    or that servers are properly reachable.
    """
    name = "verify"

    @classmethod
    def add_action_subparser(cls, sub_handler):
        subparser = super().add_action_subparser(sub_handler)
        entity_parsers = cls._get_subparsers(
            subparser, "entity", "files", "servers")
        entity_parsers["files"].add_argument(
            "--at", metavar="TIME", default="now",
            help="as of which time to check the files' hashes (default is now/latest)")
        entity_parsers["files"].add_argument(
            "locations", metavar="[[USER@]SERVER::]PATH", nargs=1,
            help="location of repository where to check files' hashes")
        entity_parsers["servers"].add_argument(
            "locations", metavar="[[USER@]SERVER::]PATH", nargs="+",
            help="location of remote repositories to check for connection")
        return subparser


def get_action_class():
    return VerifyAction
