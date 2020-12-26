#!/bin/bash -v
# Reproducer for issue https://github.com/rdiff-backup/rdiff-backup/issues/9

BASE_DIR=${TOX_ENV_DIR:-${VIRTUAL_ENV:-build}}/issue9
rm -fr ${BASE_DIR}/*
SRC_DIR=${BASE_DIR}/source
DST_DIR=${BASE_DIR}/dest

# Create a long file name -- 211 characters.  This length is chosen to be less
# than the maximum allowed for ext4 filesystems (255 max.), but long enough for
# rdiff-backup to give it special treament (see longname.py).
longName=b
a=0123456789
for (( i = 0; i < 21; i++ )); do
	longName=$longName$a
done

# Set up a source directory containing a file with the long name:
mkdir -p ${SRC_DIR}
echo test1 > ${SRC_DIR}/$longName
echo TEST1 > ${SRC_DIR}/dummy
ls -l ${SRC_DIR}

# Make a backup:
rdiff-backup ${SRC_DIR} ${DST_DIR}
sleep 1

# Keep a copy of the current_mirror file for use later:
cp ${DST_DIR}/rdiff-backup-data/current_mirror* ${BASE_DIR}

# Modify the ${SRC_DIR} file:
echo test22 > ${SRC_DIR}/$longName
echo TEST22 > ${SRC_DIR}/dummy

# Make a 2nd backup:
rdiff-backup ${SRC_DIR} ${DST_DIR}

# Notice that the increment file is put in
# ${DST_DIR}/rdiff-backup-data/long_filename_data/:
ls -l ${DST_DIR}/rdiff-backup-data/long_filename_data


# Copy the saved current_mirror back so as to force rdiff-backup into
# concluding that the last backup failed  (a simulated failure for this test):
mv ${BASE_DIR}/current_mirror* ${DST_DIR}/rdiff-backup-data

# rdiff-backup will now report that there is a problem:
rdiff-backup --list-increments ${DST_DIR}

# this avoids the error in the next call to rdiff-backup
if [[ "$1" == "nocheck" ]]
then
	exit
fi

# Perform the usual fix for the problem (regress the repository):
rdiff-backup --check-destination-dir ${DST_DIR}

# See that rdiff-backup appears to be happy:
rdiff-backup --list-increments ${DST_DIR}

# Here's the problem: regressing the repository failed to remove the increment
# file from the 2nd backup:
ls -l ${DST_DIR}/rdiff-backup-data/long_filename_data

# this avoids the error in the next call to rdiff-backup
if [[ "$1" == "fakeclean" ]]
then
	rm ${DST_DIR}/rdiff-backup-data/long_filename_data/1*
fi

# Retry the 2nd backup.  It fails as long as the old increment file is in the way:
rdiff-backup ${SRC_DIR} ${DST_DIR}
