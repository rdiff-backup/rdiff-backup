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


try:
    import copyreg
except ImportError:
    import copy_reg as copyreg

MAX_ENCODE_LENGTH = 32 * 1024 * 1024  # 32 MiB

# All primitive are allowed by default.
# Flat set of "<module>.<qualname>" strings that are allowed to
# be resolved by pickle.
ALLOWED_CLASSES = {
    "rdiff_backup.connection.ConnectionRequest",
    "rdiff_backup.eas_acls.AccessControlLists",
    "rdiff_backup.eas_acls.ExtendedAttributes",
    "rdiff_backup.fs_abilities.FSAbilities",
    "rdiff_backup.hash.Report",
    "rdiff_backup.iterfile.MiscIterFlushRepeat",
    "rdiff_backup.rpath.RORPath",
    "rdiff_backup.rpath.RPath",
    "rdiffbackup.locations._dir_shadow._CompareReport",
    "rdiffbackup.locations.fs_abilities.FSAbilities",
    "rdiffbackup.meta.acl_posix.AccessControlLists",
    "rdiffbackup.meta.acl_win.ACL",
    "rdiffbackup.meta.ea.ExtendedAttributes",
    "re._compile",
    # rdiff-backup custom exceptions
    "rdiff_backup.connection.ConnectionError",
    "rdiff_backup.connection.ConnectionQuit",
    "rdiff_backup.connection.ConnectionReadError",
    "rdiff_backup.connection.ConnectionWriteError",
    "rdiff_backup.FilenameMapping.QuotingException",
    "rdiff_backup.iterfile.IterFileException",
    "rdiff_backup.librsync.librsyncError",
    "rdiff_backup.log.LoggerError",
    "rdiff_backup.restore.RestoreError",
    "rdiff_backup.robust.SignalException",
    "rdiff_backup.rpath.RPathException",
    "rdiff_backup.rpath.SkipFileException",
    "rdiff_backup.Security.Violation",
    "rdiff_backup.selection.FilePrefixError",
    "rdiff_backup.selection.GlobbingError",
    "rdiff_backup.selection.SelectError",
    "rdiff_backup.SetConnections.SetConnectionsException",
    "rdiff_backup.statistics.StatsException",
    "rdiff_backup.Time.TimeException",
    "rdiffbackup.locations.map.filenames.QuotingException",
    "rdiffbackup.meta.ParsingError",
    # Required for v2.0.5
    "__builtin__.object",
    # Required for test.
    "__main__.ITRBadder",
    "__main__.ITRBadder2",
    "rdiff_backup.rorpiter.IterTreeReducer",
}


def secure_reconstructor(cls, base, state):
    """
    A hardened wrapper around copyreg._reconstructor.
    Required to support pickle protocol v1.
    It inspects the target class BEFORE object creation occurs.
    """
    if base is not object:
        raise _pickle.UnpicklingError(f"unexpected base class {base!r}")

    request = f"{cls.__module__}.{cls.__name__}"

    if request not in ALLOWED_CLASSES:
        raise _pickle.UnpicklingError(
            f"'{request}' is neither in the allowed whitelist nor a builtin exception"
        )
    return copyreg._reconstructor(cls, base, state)


def secure_codecs_encode(obj, encoding="utf-8", errors="strict"):
    """
    A hardened wrapper around codecs.encode().
    Required to support pickle protocol v1.
    """
    from pickle import UnpicklingError

    if not isinstance(obj, str):
        raise UnpicklingError("codecs.encode: only str input is allowed")
    if encoding != "latin1":
        raise UnpicklingError("codecs.encode: only 'latin1' is allowed")
    if errors != "strict":
        raise UnpicklingError("codecs.encode: only errors='strict' is allowed")
    if len(obj) > MAX_ENCODE_LENGTH:
        raise UnpicklingError("codecs.encode: input too large")
    return obj.encode("latin1")


# Only required to support protocol v1.
MAP_CLASSES = {
    "copy_reg._reconstructor": secure_reconstructor,
    "copyreg._reconstructor": secure_reconstructor,
    "_codecs.encode": secure_codecs_encode,
}


class RestrictedUnpickler(_pickle.Unpickler):
    """
    A secure unpickler.
    """

    def find_class(self, module, name):
        request = f"{module}.{name}"
        if request in ALLOWED_CLASSES:
            return super().find_class(module, name)

        # For protocol v1,we need to wrap the reconstructor.
        if request in MAP_CLASSES:
            return MAP_CLASSES[request]

        # For protocol v1, we need to map exceptions to builtins.
        if module == "exceptions":
            module = "builtins"

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
