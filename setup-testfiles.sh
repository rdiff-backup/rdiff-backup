#!/bin/bash

# Exit on erros immediately
set -e

if [ -d ../rdiff-backup_testfiles/bigdir ]
then
  echo "Test files found, not re-installng them.."
else
  echo "Test files not found, installng them.."
  cd ..
  if [ ! -f rdiff-backup_testfiles.tar.gz ]
  then
    rm -rf rdiff-backup_testfiles.tar.gz # Clean away potential cruft
    if [ -f cache/rdiff-backup_testfiles.tar.gz ]
    then
      echo "Using cached testfiles package"
      mv -vf cache/rdiff-backup_testfiles.tar.gz .
    else
      echo "Downloading testfiles package"
      curl -L https://github.com/ericzolf/rdiff-backup/releases/download/Testfiles2019-08-10/rdiff-backup_testfiles_2019-08-10.tar.gz --output rdiff-backup_testfiles.tar.gz
      mkdir -p cache/
      cp rdiff-backup_testfiles.tar.gz cache/
    fi
  fi
  tar xf rdiff-backup_testfiles.tar.gz # This must be run as root
  ./rdiff-backup_testfiles.fix.sh "${RDIFF_TEST_USER}" "${RDIFF_TEST_GROUP}" # This must be run as root
  cd rdiff-backup
fi

echo "
Verify a normal user for tests exist:
RDIFF_TEST_UID: ${RDIFF_TEST_UID}
RDIFF_TEST_USER: ${RDIFF_TEST_USER}
RDIFF_TEST_GROUP: ${RDIFF_TEST_GROUP}
"
