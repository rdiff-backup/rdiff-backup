#!/usr/bin/env python3
"""rdiff-backup-delete.py
Script to delete a file or directory from rdiff-backup mirrors, including metadata and file statistics

Copyright 2017 Sol1 Pty. Ltd.

author(s):  Wes Cilldhaire
license:    GPL v2
"""

import gzip
import argparse
import os
import shutil
import re
import glob

parser = argparse.ArgumentParser(
    description="Delete files or directories from rdiff-backup mirrors including metadata",
    epilog='')

parser.add_argument(
    'base',
    help='base directory of the backup (the one containing the rdiff-backup-data directory)')

parser.add_argument(
    'path',
    help='path of the file or directory to delete, relative to the base directory')

parser.add_argument(
    '-d',
    '--dry',
    action='store_true',
    help='dry run - do not perform any action but print what would be done')

base = parser.parse_args().base.rstrip('/')
path = parser.parse_args().path.rstrip('/')
dryrun = parser.parse_args().dry


def check_type(base, path):
    """
    Determine whether specified path is a single file/link or
    directory that needs to be deleted recursively
    """
    filetype = None
    p = base + '/' + path
    if os.path.lexists(p):
        if os.path.islink(p):
            filetype = 'sym'
        elif os.path.isdir(p):
            filetype = 'dir'
        else:
            filetype = 'file'
    return filetype


def delete_entry(base, path):
    """
    Delete specified path, recursively if it is a directory.  Fall through
    if it doesn't exist (ie if it was removed from the source or mirror
    prior to script execution)
    """
    filetype = check_type(base, path)
    p = (base + '/' + path).replace('//', '/')
    if filetype is None:
        # print "File/Directory '%s' doesn't appear to exist, skipping deletion" % p
        return
    if filetype == 'dir':
        print("dir:\t'%s' - deleting recursively" % p)
        if not dryrun:
            shutil.rmtree(p)
        else:
            print("\t(dryrun, not deleting)")
    else:
        print("%s:\t'%s'" % (filetype, p))
        if not dryrun:
            os.remove(p)
        else:
            print("\t(dryrun, not deleted)")


def remove_mirror():
    """Delete specified file/dir from mirror"""
    global base
    global path
    global dryrun
    print("\nLooking for mirror in %s" % base)
    delete_entry(base, path)


def remove_increments():
    """Delete all increments and dropfiles associated with specified file/dir"""
    global base
    global path
    global dryrun
    pattern = r"^%s\.[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}.+?[0-9]{2}:[0-9]{2}\.(dir|missing|diff|diff\.gz)$"
    p = (base + '/rdiff-backup-data/increments' + '/' + '/'.join(
        path.split('/')[0:-1])).rstrip('/')
    print("\nLooking for increments in %s" % p)
    increments = []
    fname = path.split('/')[-1]
    list([
        re.match(pattern % fname, x) and increments.append(x)
        for x in os.listdir(p)
    ])
    for inc in increments:
        delete_entry(p, inc)
    delete_entry(p, fname)


def remove_metadata():
    """Parse mirror metadata and remove references to file/dir"""
    global base
    global path
    global dryrun
    global filetype
    p = base + "/rdiff-backup-data"
    pattern_head = r"^File\s+%s(/.*)?$"
    pattern_body = r"^\s+.*$"
    print("\nLooking for mirror metadata in %s" % p)
    metadata = []
    list([
        metadata.append(x.split('/')[-1])
        for x in glob.glob(base + '/rdiff-backup-data/mirror_metadata*')
    ])
    for meta in metadata:
        matchfound = 0
        print("file:\t%s" % meta)
        fdin = gzip.GzipFile(p + '/' + meta, 'rb')
        fdout = gzip.GzipFile(p + '/' + 'temp_' + meta, 'wb', 9)
        switch = False
        for r in fdin:
            if re.match(pattern_head % path, r):
                switch = True
                matchfound += 1
                print("\t\t%s" % r.strip())
            elif switch:
                if not re.match(pattern_body, r):
                    fdout.write(r)
                    switch = False
            else:
                fdout.write(r)
        fdout.close()
        fdin.close()
        print("\t%s match%s found." % (matchfound,
                                       "" if matchfound == 1 else "es"))
        if dryrun:
            print("\t(dryrun, not altered)\n")
            os.remove(p + '/' + 'temp_' + meta)
        else:
            print()
            os.remove(p + '/' + meta)
            os.rename(p + '/' + 'temp_' + meta, p + '/' + meta)


def remove_statistics():
    """Parse file statistics and remove references to file/dir"""
    global base
    global path
    global dryrun
    global filetype
    p = base + "/rdiff-backup-data"
    pattern = r"^%s(/[^\s]*)?(\s[^\s]+){4}$"
    print("\nLooking for statistics in %s" % p)
    statistics = []
    list([
        statistics.append(x.split('/')[-1])
        for x in glob.glob(base + '/rdiff-backup-data/file_statistics*')
    ])
    for stats in statistics:
        matchfound = 0
        print("file:\t%s" % stats)
        fdin = gzip.GzipFile(p + '/' + stats, 'rb')
        fdout = gzip.GzipFile(p + '/' + 'temp_' + stats, 'wb', 9)
        for r in fdin:
            if re.match(pattern % path, r):
                matchfound += 1
                print("\t\t%s" % r.strip())
            else:
                fdout.write(r)
        fdout.close()
        fdin.close()
        print("\t%s match%s found." % (matchfound,
                                       "" if matchfound == 1 else "es"))
        if dryrun:
            print("\t(dryrun, not altered)\n")
            os.remove(p + '/' + 'temp_' + stats)
        else:
            print()
            os.remove(p + '/' + stats)
            os.rename(p + '/' + 'temp_' + stats, p + '/' + stats)


remove_mirror()
remove_increments()
remove_metadata()
remove_statistics()
