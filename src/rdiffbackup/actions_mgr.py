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
rdiff-backup Actions Manager

A module to discover and return built-in and 3rd party plugins for
actions (used on the command line), like backup or restore.
"""

import rdiffbackup.actions
from rdiffbackup.utils import plugins


def get_actions_dict():
    """
    Discover all rdiff-backup action plug-ins

    They may come either from the 'rdiffbackup.actions' spacename, or
    top-level modules with a name starting with 'rdb_action_'.
    Returns a dictionary with the name of each Action-class as key, and
    the class returned by get_plugin_class() as value.
    """
    if not hasattr(get_actions_dict, 'plugins'):
        get_actions_dict.plugins = plugins.get_discovered_plugins(
            rdiffbackup.actions, "rdb_action_")
    return get_actions_dict.plugins


def get_generic_parsers():
    """
    Return a list of generic parsers

    This list is used to parse generic options common to all actions.
    """
    return rdiffbackup.actions.GENERIC_PARSERS


def get_parent_parsers_compat200():
    """
    Return a list of all parent sub-options used by all actions

    This list is solely used to simulate the old command line interface.
    """
    return rdiffbackup.actions.PARENT_PARSERS


if __name__ == "__main__":  # pragma: no cover
    actions = get_actions_dict()
    for name, action_class in actions.items():
        print(name + ": " + action_class.get_version())
