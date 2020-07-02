#!/bin/bash
# this script is more to be considered as an example on how to create
# a file system for specific tests as a normal user. It works for vfat,
# but not always, fails on the last command with exfat (use mount.exfat
# instead), and doesn't seem to work for ntfs, but is still a good basis
# for tests of "exotic" file systems under Linux.

if [ -z "$1" ] || [ "$1" == '-h' ] || [ "$1" == '--help' ]
then
	echo "$0 <loop_file> <fs_format> <fs_label>" >&2
	exit 0
fi

if [ "$1" == '-d' ] || [ "$1" == '--delete' ]
then
	ACTION=delete
	shift
else
	ACTION=create
fi

LOOP_FILE=$1
FS_FORMAT=$2
FS_LABEL=$3

if [ ${ACTION} == "create" ]
then
	fallocate -l 1m ${LOOP_FILE}
	udisksctl loop-setup --no-user-interaction -f ${LOOP_FILE}

	case ${FS_FORMAT} in
	vfat|exfat)
		mkfs.${FS_FORMAT} -n ${FS_LABEL} ${LOOP_FILE}
		;;
	ntfs)
		mkfs.${FS_FORMAT} -L ${FS_LABEL} ${LOOP_FILE}
		;;
	esac

	# we assume the last loop is the right one
	LOOP_DEV=$(ls -1v /dev/loop[0-9]* | tail -n 1)

	udisksctl mount --no-user-interaction -t ${FS_FORMAT} -b ${LOOP_DEV}
elif [ ${ACTION} == "delete" ]
then
	LOOP_DEV=$(ls -1v /dev/loop[0-9]* | tail -n 1)
	udisksctl unmount --no-user-interaction -b ${LOOP_DEV}
	udisksctl loop-delete --no-user-interaction -b ${LOOP_DEV}
	rm -f ${LOOP_FILE}
fi
