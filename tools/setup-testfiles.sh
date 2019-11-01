#!/bin/bash
# help file to download and unpack/prepare the test files required by the automated tox tests
# this script is being called from the Makefile in the root directory of the rdiff-backup repo

# Exit on errors immediately
set -e

OLDTESTDIR=../rdiff-backup_testfiles
TESTREPODIR=rdiff-backup-filesrepo
TESTREPOURL=https://github.com/rdiff-backup/${TESTREPODIR}.git
TESTTARFILE=rdiff-backup_testfiles.tar

if [ -d ${OLDTESTDIR}/various_file_types ]
then
	echo "Test files found, not re-installing them..." >&2
else
	echo "Test files not found, installing them..." >&2
	cd ..
	if [ ! -f ${TESTREPODIR}/${TESTTARFILE} ]
	then
		rm -fr ${TESTREPODIR}  # Clean away potential cruft
		git clone ${TESTREPOURL}
	else  # update the existing Git repo
		git -C ${TESTREPODIR} pull --ff-only  # fail if things don't look right
	fi

	if [ $(id -u) -eq 0 ]
	then  # we do this because sudo might not be installed
		SUDO=
	else
		SUDO=sudo
	fi

	# the following commands must be run as root
	${SUDO} rm -fr ${OLDTESTDIR}  # Clean away potential cruft
	${SUDO} tar xf ${TESTREPODIR}/${TESTTARFILE}
	${SUDO} ${TESTREPODIR}/rdiff-backup_testfiles.fix.sh "${RDIFF_TEST_USER}" "${RDIFF_TEST_GROUP}"

	cd rdiff-backup
fi

echo "
Verify a normal user for tests exist:
RDIFF_TEST_UID: ${RDIFF_TEST_UID}
RDIFF_TEST_USER: ${RDIFF_TEST_USER}
RDIFF_TEST_GROUP: ${RDIFF_TEST_GROUP}
"
