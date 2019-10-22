#!/bin/bash
# Used by travis pipeline to run the test and compile wheel packages
set -e
set -x

# Install a system package required by our build.
# TODO We may detect if the linux is debian or redhat and install different packages here.
yum install -y wget libacl-devel librsync-devel rdiff rsync

# Compile wheels to also compile rdiff-backup
"${PYBIN}/pip" wheel /rdiff-backup/ -w wheelhouse/

case "${1,,}" in
deploy)
    auditwheel repair wheelhouse/*.whl --plat $PLAT -w /rdiff-backup/wheelhouse/
    "${PYBIN}/pip" install twine
    "${PYBIN}/twine" upload /rdiff-backup/wheelhouse/*manylinux*.whl
    ;;

test)
    # Download testfiles
    wget -q -O rdiff-backup_testfiles.tar.gz https://github.com/ericzolf/rdiff-backup/releases/download/Testfiles2019-08-10/rdiff-backup_testfiles_2019-08-10.tar.gz
    tar -xf rdiff-backup_testfiles.tar.gz
    useradd -ms /bin/bash testuser
    chown -R testuser:testuser /rdiff-backup/
    bash -x ./rdiff-backup_testfiles.fix.sh testuser testuser
    
    # Run tox test as non-root user.
    "${PYBIN}/pip" install tox flake8
    cd /rdiff-backup/
    su testuser -c "${PYBIN}/tox"
    
    # Run tox test as root if needed.
    if [ "$TOXENV" != "flake8" ]; then
        RDIFF_TEST_UID=$(id -u testuser) RDIFF_TEST_USER=testuser "${PYBIN}/tox" -c tox_root.ini
    fi
    ;;

*)
    echo "Usage: ./build-linux.sh [test|deploy]"
    exit 1
    ;;
esac
