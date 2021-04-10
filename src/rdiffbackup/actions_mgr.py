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

import importlib
import pkgutil

import rdiffbackup.actions


def get_discovered_actions():
    """
    Discover all rdiff-backup action plug-ins

    They may come either from the 'rdiffbackup.actions' spacename, or
    top-level modules with a name starting with 'rdb_action_'.
    Returns a dictionary with the name of each Action-class as key, and
    the class returned by get_action_class() as value.
    """
    # we discover first potential 3rd party plugins, based on name
    discovered_action_plugins = {
        name: importlib.import_module(name)
        for finder, name, ispkg
        in pkgutil.iter_modules()
        if name.startswith("rdb_action_")
    }
    # and we complete/overwrite with modules delivered in the namespace
    discovered_action_plugins.update({
        name: importlib.import_module(name)
        for name
        in _iter_namespace(rdiffbackup.actions)
    })
    # then we create the dictionary of {action_name: ActionClass}
    disc_actions = {
        action.get_action_class().get_name(): action.get_action_class()
        for action
        in discovered_action_plugins.values()
    }
    return disc_actions


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


def _iter_namespace(nsp):
    """
    Return an iterator of names of modules found in a specific namespace.

    The names are made absolute, with the namespace as prefix, to simplify
    import.
    """
    # Specifying the second argument (prefix) to iter_modules makes the
    # returned name an absolute name instead of a relative one. This allows
    # import_module to work without having to do additional modification to
    # the name.
    prefix = nsp.__name__ + "."
    for pkg in pkgutil.iter_modules(nsp.__path__, prefix):
        yield pkg[1]  # pkg is (finder, name, ispkg)
    # special handling when the package is bundled with PyInstaller
    # See https://github.com/pyinstaller/pyinstaller/issues/1905
    toc = set()  # table of content
    for importer in pkgutil.iter_importers(nsp.__name__.partition(".")[0]):
        if hasattr(importer, 'toc'):
            toc |= importer.toc
    for name in toc:
        if name.startswith(prefix):
            yield name


if __name__ == "__main__":
    actions = get_discovered_actions()
    for name, action_class in actions.items():
        print(name + ": " + action_class.get_version())
