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
A module to handle plugins
"""

import importlib
import pkgutil


def get_discovered_plugins(namespace, prefix):
    """
    discover and return plugins with the given prefix or in the namespace

    Returns a dictionary with the name of each Plugin-class as key, and
    the class returned by get_plugin_class() as value.
    """
    # we discover first potential 3rd party plugins, based on name
    discovered_modules = {
        name: importlib.import_module(name)
        for finder, name, ispkg
        in pkgutil.iter_modules()
        if name.startswith(prefix)
    }
    # and we complete/overwrite with modules delivered in the namespace
    discovered_modules.update({
        name: importlib.import_module(name)
        for name in _iter_namespace(namespace)
    })

    # then we create the dictionary of {name: Class}
    discovered_plugins = {
        plugin.get_plugin_class().get_name(): plugin.get_plugin_class()
        for plugin
        in discovered_modules.values()
    }

    return discovered_plugins


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
