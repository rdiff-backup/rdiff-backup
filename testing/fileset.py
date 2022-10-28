# Copyright (C) 2021 Eric Lavarde <ewl+rdiffbackup@lavar.de>
#
# This program is licensed under the GNU General Public License (GPL).
# you can redistribute it and/or modify it under the terms of the GNU
# General Public License as published by the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA;
# either version 2 of the License, or (at your option) any later version.
# Distributions of rdiff-backup should include a copy of the GPL in a
# file called COPYING.  The GPL is also available online at
# https://www.gnu.org/copyleft/gpl.html.

"""
This library allows to create a set of files (and directories), using a
structure of dictionaries.

The name of the files and directories in the base directory are used as keys
in a dictionary of dictionaries.

A directory has the type "dir" or a "subs" key to contain sub-directories or
files.

Both directories and files can have the following keys:
* a "mode" to define the chmod to apply

Files can also have the following keys:
* "content" which is written to the file.
* "open" flag, "t" or "b" for the write mode to the file

Example:
{
    "a_dir": {"subs": {"fileA": {"content": "initial"}, "fileB": {}}},
    "empty_dir": {"type": "dir", "mode": 0o777},
    "a_bin_file": {"content": b"some_binary_content", "open": "b"},
}
"""

import os
import shutil
import stat

DEFAULT_DIR_MODE = 0o755
DEFAULT_FILE_MODE = 0o644
DEFAULT_FILE_OPEN = "t"  # or "b"
DEFAULT_FILE_CONTENT = ""


def create_fileset(base_dir, structure):
    """
    Create the file set as represented by the structure in the base directory

    base_dir can be path-like, str or bytes,
    structure contains names as str
    """
    _create_directory(base_dir)
    for name in structure:
        _create_fileset(os.path.join(os.fsdecode(base_dir), name),
                        structure[name])


def remove_fileset(base_dir, structure):
    """
    Remove the file set as represented by the strucutre in the base directory

    The base directory itself isn't removed unless it's empty
    """
    for name in structure:
        fullname = os.path.join(os.fsdecode(base_dir), name)
        struct = structure[name]
        try:
            if struct.get("type") == "dir" or "subs" in struct:
                shutil.rmtree(fullname)
            else:
                os.remove(fullname)
        except FileNotFoundError:
            pass  # if the file doesn't exist, we don't need to remove it
        except IsADirectoryError:
            shutil.rmtree(fullname)
        except NotADirectoryError:
            os.remove(fullname)

    # at the end we try to remove the base directory, if it's empty
    try:
        os.removedirs(base_dir)
    except OSError:
        pass  # directory isn't empty, we don't really care


def compare_paths(path1, path2):
    """
    Compare two paths, possibly created by this library

    Comparaison is made recursively according to the names of the files and
    sub-directories.
    If there are commonalities, those common files/dirs are then compared for
    type, link numbers, size and/or content, access mode, uid, gid.

    The result is a list of explained differences, empty if there are no
    differences. None is returned if the two paths happen to point at the
    same directory.
    """
    differences = []
    # if the paths are pointing to the same file, no need to compare
    if os.path.samefile(path1, path2):
        return None

    # compare first the paths as normal files
    stat1 = os.lstat(path1)
    stat2 = os.lstat(path2)

    differences += _compare_files(path1, stat1, path2, stat2)

    # stop the comparaison here if the paths don't both point to directories
    if not (stat.S_ISDIR(stat1.st_mode) and stat.S_ISDIR(stat2.st_mode)):
        return differences

    # then compare them as directories
    files1 = set(os.listdir(os.fsdecode(path1)))
    files2 = set(os.listdir(os.fsdecode(path2)))
    if len(files1 - files2):
        differences.append(
            "Files {fi} are in base dir {bd1} but not in {bd2}".format(
                fi=files1 - files2, bd1=path1, bd2=path2))
    if len(files2 - files1):
        differences.append(
            "Files {fi} are not in base dir {bd1} but in {bd2}".format(
                fi=files2 - files1, bd1=path1, bd2=path2))
    if files1.isdisjoint(files2):
        return differences  # there are no files in common

    for file in files1 & files2:
        next_path1 = os.path.join(os.fsdecode(path1), file)
        next_path2 = os.path.join(os.fsdecode(path2), file)
        differences += compare_paths(next_path1, next_path2)

    return differences


def _create_fileset(fullname, struct):
    """
    Recursive part of the fileset creation
    """
    if struct.get("type") == "dir" or "subs" in struct:
        _create_directory(fullname, settings=struct, always_delete=True)
        for name in struct.get("subs", {}):
            _create_fileset(os.path.join(fullname, name), struct["subs"][name])
    elif (struct.get("type") == "hardlink"
            or ("link" in struct and "type" not in struct)):
        _create_link(fullname, settings=struct)
    elif struct.get("type") == "symlink":  # a link is hard by default
        _create_link(fullname, settings=struct, linker=os.symlink)
    else:
        _create_file(fullname, settings=struct)
    # other types of items are ignored for now


def _create_directory(dir_name, settings={}, always_delete=False):
    """
    Create a directory according to settings.

    The directory is created according to "mode". It is first destroyed if
    requested. It is currently the recommended approach to make sure the
    structure is exactly as expected (a delta mechanism could be added).
    """
    if os.path.exists(dir_name):
        if always_delete or not os.path.isdir(dir_name):
            shutil.rmtree(dir_name)
        else:
            return
    os.makedirs(dir_name, mode=settings.get("mode", DEFAULT_DIR_MODE))


def _create_file(file_name, settings, always_delete=False):
    """
    Creates a file according to settings

    The file will have the access rights according to "mode", and the "content"
    from the corresponding key, written in binary mode if "open" is set to "b",
    else "t".
    """
    if os.path.exists(file_name):
        if always_delete or not os.path.isfile(file_name):
            shutil.rmtree(file_name)
    with open(file_name, "w" + settings.get("open", DEFAULT_FILE_OPEN)) as fd:
        fd.write(settings.get("content", DEFAULT_FILE_CONTENT))
    os.chmod(file_name, mode=settings.get("mode", DEFAULT_FILE_MODE))


def _create_link(link_name, settings, linker=os.link):
    """
    Creates a link according to settings, hard or soft depending on function
    """
    link = settings["link"]
    if os.path.isabs(link):
        linker(link, link_name)
    else:
        currdir = os.getcwd()
        os.chdir(os.path.dirname(link_name))
        linker(link, link_name)
        os.chdir(currdir)


def _compare_files(file1, stat1, file2, stat2):
    """
    Compares two files and their file stats.

    Those files are compared for type, link numbers, size and/or content,
    access mode, uid, gid.

    The result is a list of explained differences, empty if there are no
    differences.
    """
    differences = []

    if stat.S_IFMT(stat1.st_mode) != stat.S_IFMT(stat2.st_mode):
        differences.append(
            "Paths {pa1} and {pa2} have different types {ft1} vs. {ft2}".format(
                pa1=file1, pa2=file2,
                ft1=stat.S_IFMT(stat1.st_mode),
                ft2=stat.S_IFMT(stat2.st_mode)))
        # if the files don't have the same type, there is no point comparing
        # them further...
        return differences

    if stat.S_IMODE(stat1.st_mode) != stat.S_IMODE(stat2.st_mode):
        differences.append(
            "Paths {pa1} and {pa2} have different "
            "access rights {ar1} vs. {ar2}".format(
                pa1=file1, pa2=file2,
                ar1=stat.S_IMODE(stat1.st_mode),
                ar2=stat.S_IMODE(stat2.st_mode)))

    if stat1.st_nlink != stat2.st_nlink:
        differences.append(
            "Paths {pa1} and {pa2} have different "
            "link numbers {ln1} vs. {ln2}".format(
                pa1=file1, pa2=file2, ln1=stat1.st_nlink, ln2=stat2.st_nlink))

    if stat1.st_size != stat2.st_size:
        differences.append(
            "Paths {pa1} and {pa2} have different "
            "file sizes {fs1} vs. {fs2}".format(
                pa1=file1, pa2=file2, fs1=stat1.st_size, fs2=stat2.st_size))
    elif stat.S_ISREG(stat1.st_mode) and stat.S_ISREG(stat2.st_mode):
        with open(file1) as fd1, open(file2) as fd2:
            content1 = fd1.read()
            content2 = fd2.read()
        if content1 != content2:
            if len(content1) > 75:
                content1 = content1[:36] + "..." + content1[-36:]
            if len(content2) > 75:
                content2 = content2[:36] + "..." + content2[-36:]
            differences.append(
                "Paths {pa1} and {pa2} have different "
                "regular file' contents '{rc1}' vs. '{rc2}'".format(
                    pa1=file1, pa2=file2, rc1=content1, rc2=content2))

    # we compare only the modification seconds, because rdiff-backup doesn't
    # save milliseconds.
    if int(stat1.st_mtime) != int(stat2.st_mtime):
        differences.append(
            "Paths {pa1} and {pa2} have different "
            "modification times {mt1} vs. {mt2}".format(
                pa1=file1, pa2=file2,
                mt1=int(stat1.st_mtime), mt2=int(stat2.st_mtime)))

    if stat1.st_uid != stat2.st_uid:
        differences.append(
            "Paths {pa1} and {pa2} have different "
            "user owners {uo1} vs. {uo2}".format(
                pa1=file1, pa2=file2, uo1=stat1.st_uid, uo2=stat2.st_uid))

    if stat1.st_gid != stat2.st_gid:
        differences.append(
            "Paths {pa1} and {pa2} have different "
            "group owners {go1} vs. {go2}".format(
                pa1=file1, pa2=file2, go1=stat1.st_uid, go2=stat2.st_uid))

    return differences
