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

import io
import pickle as _pickle


class RestrictedUnpickler(_pickle.Unpickler):
    """
    A secure unpickler.
    """

    # All primitives are allowed by default.
    # Flat set of "<module>.<qualname>" strings that are allowed to
    # be resolved by pickle.
    ALLOWED_CLASSES = {
        "rdiff_backup.connection.ConnectionRequest",
        "rdiff_backup.hash.Report",
        "rdiff_backup.iterfile.MiscIterFlushRepeat",
        "rdiff_backup.rpath.RORPath",
        "rdiff_backup.rpath.RPath",
        "rdiff_backup.Security.Violation",
        "rdiffbackup.locations._dir_shadow._CompareReport",
        "rdiffbackup.locations.fs_abilities.FSAbilities",
        "rdiffbackup.locations.increment.StoredRPath",
        "rdiffbackup.locations.map.filenames.QuotedRPath",
        "rdiffbackup.meta.acl_posix.AccessControlLists",
        "rdiffbackup.meta.acl_win.ACL",
        "rdiffbackup.meta.ea.ExtendedAttributes",
        "re._compile",
        # rdiff-backup custom exceptions
        "rdiff_backup.Security.Violation",
        "rdiff_backup.connection.ConnectionReadError",
        "rdiff_backup.selection.GlobbingError",
        "rdiff_backup.selection.FilePrefixError",
        "rdiff_backup.librsync.librsyncError",
        "rdiff_backup.selection.SelectError",
        "rdiff_backup.connection.ConnectionQuit",
        "rdiff_backup.connection.ConnectionError",
        "rdiff_backup.connection.ConnectionWriteError",
        "rdiff_backup.robust.SignalException",
        "rdiff_backup.Time.TimeException",
        "rdiffbackup.locations.map.filenames.QuotingException",
        "rdiffbackup.meta.ParsingError",
        "rdiff_backup.rpath.RPathException",
        "rdiff_backup.SetConnections.SetConnectionsException",
        "rdiff_backup.rpath.SkipFileException",
        "rdiff_backup.iterfile.IterFileException",
        # Required for test.
        "__main__.ITRBadder",
        "__main__.ITRBadder2",
        "rdiff_backup.rorpiter.IterTreeReducer",
    }

    def find_class(self, module, name):
        request = f"{module}.{name}"
        if request in self.ALLOWED_CLASSES:
            return super().find_class(module, name)

        # Wildcard: any built-in exception class
        if module == "builtins":
            obj = super().find_class(module, name)
            if isinstance(obj, type) and issubclass(obj, BaseException):
                return obj

        raise _pickle.UnpicklingError(
            f"'{request}' is neither in the allowed whitelist nor a builtin exception"
        )


def dumps(*args, **kwargs):
    return _pickle.dumps(*args, **kwargs)


def loads(data):
    """
    Drop-in replacement for pickle.loads(), to be used anywhere we
    receive potentially untrusted data.
    """
    return RestrictedUnpickler(io.BytesIO(data)).load()
