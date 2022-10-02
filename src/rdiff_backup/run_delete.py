#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (C) 2020 Patrik Dufresne<info@patrikdufresne.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
#
#
# rdiff-backup-delete
#
# Deletes files and directories from a rdiff-backup repository, including the
# current mirror and all its history. Also remove any reference from the
# metadata.
#

import getopt
import gzip
import io
import os
import re
import shutil
import stat
import struct
import subprocess
import sys


# List of suffixes for increments
SUFFIXES = [b".missing", b".snapshot.gz", b".snapshot",
            b".diff.gz", b".data.gz", b".data", b".dir", b".diff"]


def _bytes(value):
    if isinstance(value, bytes):
        return value
    else:
        return value.encode('utf8', errors='surrogateescape')


def _str(value):
    if isinstance(value, str):
        return value
    else:
        return value.decode('utf-8', errors='replace')


# Check if gzip is available.
_GZIP = shutil.which('gzip')


class WrapClose:
    """
    Helper for _open() -- a proxy for a file whose close waits for the process.
    """

    def __init__(self, stream, proc):
        self._stream = stream
        self._proc = proc

    def close(self):
        if self._proc.stdin:
            self._proc.stdin.close()
        returncode = self._proc.wait()
        if self._proc.stdout:
            self._proc.stdout.close()
        return returncode

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def __getattr__(self, name):
        return getattr(self._stream, name)

    def __iter__(self):
        return iter(self._stream)


def _open(fn, mode):
    """
    Wrapper to open a file with or without compression using gzip executable or
    pure-python implementation.
    """
    compress = fn.endswith(b'.gz')
    buffered = io.BufferedReader if 'r' in mode else io.BufferedWriter
    # Open file directly if compression is not required
    if not compress:
        return buffered(open(fn, mode))

    # Open file using python gzip if zcat and gzip are not available.
    if not _GZIP:
        return buffered(gzip.open(fn, mode))

    # When available, open file using subprocess gzip for better performance
    if 'r' in mode:
        proc = subprocess.Popen([_bytes(_GZIP), b'-cd', fn],
                                stdout=subprocess.PIPE)
        return WrapClose(proc.stdout, proc)
    else:  # wb
        proc = subprocess.Popen([_GZIP],
                                stdin=subprocess.PIPE,
                                stdout=open(fn, mode))
        return WrapClose(proc.stdin, proc)


def _print_usage(error_message=None):
    if error_message:
        print(error_message)
    print("""
Usage: %s [OPTION]... PATH
    Delete PATH from a rdiff-backup repository including the current
    mirror and all its history.
Options:
    h, --help
            Display this help text and exit
    d, --dry-run
            Run the script without doing modifications to the repository.
    PATH
            A relative or absolute path to be deleted. This path must be
            inside a rdiff-backup repository.
""" % (sys.argv[0],))
    sys.exit(1 if error_message else 0)


def _parse_options():
    """
    Used to parse the arguments.
    """
    # Support environment variable
    try:
        optlist, args = getopt.getopt(
            sys.argv[1:], "hd", ["help", "dry-run"],
        )
    except getopt.GetoptError as e:
        _print_usage("fatal: bad command line: " + str(e))
    dry_run = False
    for opt, arg in optlist:
        if opt in ["-h", "--help"]:
            _print_usage()
        elif opt in ["-d", "--dry-run"]:
            dry_run = True
        else:
            _print_usage("fatal: invalid arguments: %s" % opt)

    # Make sure we get a folder or a file to be deleted.
    if len(args) == 0:
        _print_usage('fatal: missing arguments')
    elif len(args) > 1:
        _print_usage('fatal: too many arguments')
    # NOTE: we can't check for actual existence of path because it might only
    #       exist in past increments
    # elif not os.path.lexists(args[0]):
    #    # we use lexists so that we can delete a dangling link (?)
    #    _print_usage('fatal: path must refer to an existing file or directory')

    # Check the repository, root dir must be at least one level up
    full_path = os.path.abspath(_bytes(args[0]))
    root_dir = os.path.dirname(full_path)

    # we need to make sure we won't try to remove rdiff-backup-data or a file
    # within this directory (os.altsep is for Windows)
    if (b"rdiff-backup-data" in full_path.split(os.fsencode(os.sep))
            or (os.altsep
                and (b"rdiff-backup-data"
                     in full_path.split(os.fsencode(os.altsep))))):
        sys.exit("fatal: path to delete can't be rdiff-backup-data or within")

    while root_dir != b'/':
        rdiff_backup_data = os.path.join(root_dir, b'rdiff-backup-data')
        if os.path.isdir(rdiff_backup_data):
            relpath = os.path.relpath(full_path, start=root_dir)
            return root_dir, relpath, dry_run
        # Continue with parent directory.
        root_dir = os.path.dirname(root_dir)

    sys.exit("fatal: not a rdiff-backup repository (or any parent up to mount point /)")


def _filename_from_increment(file):
    """
    Return the filename from an increment entry.
    e.g.: Revisions.2014-11-05T16:04:30-05:00.dir
    return "Revision"
    """
    for suffix in SUFFIXES:
        if file.endswith(suffix):
            with_suffix = file[:-len(suffix)]
            return with_suffix.rsplit(b".", 1)[0]
    return None


def _remove_from_metadata(repopath, file, dry_run):
    """
    This function is used to remove the repo path from the given `file` metadata.
    """
    if os.path.basename(file).startswith(b'file_statistics'):
        start_marker = b''

        def matches(line):
            path = line.rsplit(b' ', 4)[0]
            return path == repopath.metaquote or path.startswith(repopath.metaquote + b'/')

    elif os.path.basename(file).startswith(b'mirror_metadata'):
        start_marker = b'File '

        def matches(line):
            return line == b'File ' + repopath.metaquote + b'\n' or line.startswith(b'File ' + repopath.metaquote + b'/')

    elif (os.path.basename(file).startswith(b'extended_attributes')
          or os.path.basename(file).startswith(b'access_control_lists')
          or os.path.basename(file).startswith(b'win_access_control_lists')):
        start_marker = b'# file: '

        def matches(line):
            return line == b'# file: ' + repopath.aclquote + b'\n' or line.startswith(b'# file: ' + repopath.aclquote + b'/')

    else:
        return

    print('removing entries `%s` from %s' % (_str(repopath.relpath), _str(file)))
    input = _open(file, 'rb')
    tmp_file = os.path.join(os.path.dirname(file), b'.tmp.' + os.path.basename(file))
    output = _open(tmp_file, 'wb')
    try:
        line = input.readline()
        while line:
            if line.startswith(start_marker) and matches(line):
                line = input.readline()
                while line and not line.startswith(start_marker):
                    # Special case to handle longfilename
                    if line.startswith(b'  AlternateIncrementName ') or line.startswith(b'  AlternateMirrorName '):
                        name = line.strip(b'\n').rsplit(b' ', 1)[1]
                        path = os.path.join(repopath.repo.long_filename_data, name)
                        _remove_increments(path, dry_run)
                    line = input.readline()
            else:
                output.write(line)
                line = input.readline()
    finally:
        input.close()
        output.close()
    if not dry_run:
        os.rename(tmp_file, file)
    else:
        os.remove(tmp_file)


def _remove_increments(path, dry_run):
    """
    Remove all <path>.*.<suffixes>
    """
    # If the increment is a directory, remove it and all it's content.
    _rmtree(path, dry_run)

    # Then let find all the increment entries (.missing, .dir, .gz, .diff.gz)
    dir = os.path.dirname(path)
    fn = os.path.basename(path)

    if os.path.isdir(dir):
        for p in os.listdir(dir):
            file = os.path.join(dir, p)
            if not os.path.isdir(file) and fn == _filename_from_increment(p):
                # Remove the increment entry
                print('deleting increments `%s`' % (_str(file),))
                if not dry_run:
                    os.remove(file)


def _rmtree(path, dry_run):
    """
    Custom implementation of shutil.rmtree() to handle permission errors,
    fifo and symlink deletion.
    """
    if dry_run:
        return

    # Try to change the permissions of the file or directory to delete them.
    def on_error(func, path, exc):
        """
        Handle permissions error while deleting file or directory by changing
        the permissions to allow deletion.
        """
        # Parent directory must allow o+rwx
        parent_dir = os.path.dirname(path)
        if not os.access(parent_dir, os.W_OK | os.R_OK | os.X_OK):
            prev_mode = os.stat(parent_dir).st_mode
            os.chmod(parent_dir, prev_mode | stat.S_IRWXU)
        if not os.access(path, os.W_OK | os.R_OK):
            os.chmod(path, 0o0600)
        return func(path)

    try:
        mode = os.lstat(path).st_mode
    except FileNotFoundError:
        # Nothing to delete
        mode = 0
    except PermissionError as exc:
        mode = on_error(os.lstat, path, exc).st_mode
    if stat.S_ISDIR(mode):
        names = []
        names = os.listdir(path)
        for name in names:
            fullname = os.path.join(path, name)
            _rmtree(fullname, dry_run)
        try:
            os.rmdir(path)
        except PermissionError as exc:
            on_error(os.rmdir, path, exc)
    elif mode:
        try:
            os.remove(path)
        except PermissionError as exc:
            on_error(os.remove, path, exc)


def _unquote(name):
    """Remove quote (;000) from the given name."""
    assert isinstance(name, bytes), (
        "Input %s to function must be bytes not %s." % (name, type(name)))

    # This function just gives back the original text if it can decode it
    def unquoted_char(match):
        """For each ;000 return the corresponding byte."""
        if not len(match.group()) == 4:
            return match.group
        try:
            return bytes([int(match.group()[1:])])
        except Exception:
            return match.group

    # Remove quote using regex
    return re.sub(b";[0-9]{3}", unquoted_char, name, re.S)


def _acl_quote(s):
    """Quote filename for ACL usages."""
    # Table mapping for meta_quote and meta_unquote
    _safe = b'0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ!"#$%&\'()*+,-./:;<>?@[]^_`{|}~'
    _meta_quote_map = {}
    for i in range(1, 256):
        c = struct.pack('B', i)
        if c in _safe:
            _meta_quote_map[i] = c
        else:
            _meta_quote_map[i] = '\\{0:03o}'.format(i).encode('ascii')
    return b''.join(map(_meta_quote_map.__getitem__, s))


class Repo():
    """
    Represent the rediff-backup repository.

    rdiff_backup_data: <root>/rdiff-backup-data/
    long_filename_data: <root>/rdiff-backup-data/long_filename_data/
    """

    def __init__(self, root):
        self.root = root
        self.rdiff_backup_data = os.path.join(self.root, b'rdiff-backup-data')
        self.long_filename_data = os.path.join(self.rdiff_backup_data, b'long_filename_data')

    def is_lock(self):
        """
        Try to lock the repository. Raise an error if the repository
        is already locked by another process.
        """
        # Check if the repository has multiple current_mirror.
        count = len([x for x in os.listdir(self.rdiff_backup_data) if x.startswith(b'current_mirror.')])
        return count > 1


class RepoPath():
    """
    Object used to provide all the variation of the same path with different escaping.

    root: absolute location of the rdiff-backup repository
    relpath: relative path to the file of folder to be deleted
    abspath: absolute path to the file or folder to be delete (may not exists)
    metaquote: unquoted relative path (;000 replace by bytes) with quoted \
    aclquote: quoted relative path (bytes converted into \000)
    increments: <root>/rdiff-backup-data/increments/<relpath>
    """

    def __init__(self, root, relpath):
        # assert is kind of OK as everything is also checked in _parse_options
        assert root
        assert isinstance(root, bytes)
        assert os.path.isdir(root)
        assert os.path.isdir(os.path.join(root, b'rdiff-backup-data'))
        assert relpath
        assert isinstance(relpath, bytes)
        assert relpath != b'rdiff-backup-data'

        self.repo = Repo(root)
        self.relpath = relpath
        self.metaquote = _unquote(self.relpath).replace(b'\\', b'\\\\')
        self.aclquote = _acl_quote(self.relpath)

        # Return the absolute location of this path on the filesystem
        self.abspath = os.path.join(self.repo.root, self.relpath)
        self.increments = os.path.join(self.repo.rdiff_backup_data, b'increments', self.relpath)


def main():
    # Parse the arguments.
    # root maybe None
    root, relpath, dry_run = _parse_options()
    repopath = RepoPath(root, relpath)
    if repopath.repo.is_lock():
        sys.exit('failed to acquire repository lock. A backup may be running.')

    # Check if the repository is "locked"
    print("start deleting path `%s` from repository %s" % (_str(relpath), _str(root)))
    if dry_run:
        print("running in dry-run mode")

    # Remove any entries from metadata files: file_statistics, mirror_metadata, extended_attributes, access_control_lists
    dir = repopath.repo.rdiff_backup_data
    for f in os.listdir(dir):
        _remove_from_metadata(repopath, os.path.join(dir, f), dry_run)

    print('deleting directory `%s` recursively' % (_str(repopath.abspath),))
    _rmtree(repopath.abspath, dry_run)

    # Then let find all the increment entries (.missing, .dir, .gz, .diff.gz)
    _remove_increments(repopath.increments, dry_run)
    print('done')


# Call main if this script is call directly.
if __name__ == "__main__":
    main()
