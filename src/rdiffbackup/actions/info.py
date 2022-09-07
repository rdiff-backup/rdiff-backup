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
A built-in rdiff-backup action plug-in to output info, especially useful
for documenting an issue.
"""

import yaml

from rdiffbackup import actions
from rdiff_backup import Globals


class InfoAction(actions.BaseAction):
    """
    Output information about the current system, so that it can be used in
    in a bug report, and exits.
    """
    name = "info"
    security = None
    # information has no specific sub-options

    def setup(self):
        # there is nothing to setup for the info action
        return Globals.RET_CODE_OK

    def run(self):
        ret_code = super().run()
        if ret_code & Globals.RET_CODE_ERR:
            return ret_code

        runtime_info = Globals.get_runtime_info()
        print(yaml.safe_dump(runtime_info,
                             explicit_start=True, explicit_end=True))
        return ret_code


def get_plugin_class():
    return InfoAction
