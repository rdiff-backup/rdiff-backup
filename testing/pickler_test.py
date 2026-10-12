# Copyright 2026 Patrik Dufresne <patrik@ikus-soft.com>
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

import os
import unittest
import inspect
import importlib
import pkgutil
from rdiffbackup.utils import pickle


def _collect_exceptions(*packages):
    """Collect all custom exception recursively."""
    found = set()
    for package in packages:
        if isinstance(package, str):
            package = importlib.import_module(package)

        modules = [package]
        if hasattr(package, "__path__"):  # it's a package, not a plain module
            for info in pkgutil.walk_packages(
                package.__path__, prefix=package.__name__ + "."
            ):
                try:
                    modules.append(importlib.import_module(info.name))
                except ImportError:
                    # optional deps (e.g. xattr, pylibacl) or platform-specific modules
                    continue

        for mod in modules:
            for name, obj in inspect.getmembers(mod, inspect.isclass):
                if (
                    issubclass(obj, BaseException)
                    and obj.__module__ == mod.__name__  # defined here, not imported
                ):
                    found.add(f"{mod.__name__}.{name}")
    return found


class _ReduceOsGetcwd:
    def __reduce__(self):
        return (os.getcwd, ())


class PickleTest(unittest.TestCase):

    def test_all_custom_exceptions_are_whitelisted(self):
        exceptions = _collect_exceptions("rdiff_backup", "rdiffbackup")
        for e in exceptions:
            self.assertIn(e, pickle.RestrictedUnpickler.ALLOWED_CLASSES)

    def test_not_allowed_class(self):
        with self.assertRaises(pickle._pickle.UnpicklingError):
            obj = _ReduceOsGetcwd()
            pickle.loads(pickle.dumps(obj))


if __name__ == "__main__":
    unittest.main()
