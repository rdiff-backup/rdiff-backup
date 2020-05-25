#!/bin/bash
# small script to prepare ArchLinux for rdiff-backup development
# run it as root, it was developed under the conditions of a container,
# e.g. created with:
#     podman run -it docker.io/library/archlinux
# CAUTION: it is more meant as an example of helpful commands for a developer/tester
#          not fully knowledgeable of the platform than as a truly and fully tested script.

DEVUSER=devuser

# upgrade all packages
#pacman -Syu --noconfirm

# packages under Arch generally contains what other distros place in -dev/-devel packages
pacman -S --noconfirm librsync libffi
pacman -S --noconfirm python python-pylibacl python-pyxattr
pacman -S --noconfirm python-setuptools python-setuptools-scm tox
pacman -S --noconfirm git openssh
pacman -S --noconfirm base-devel
pacman -S --noconfirm vim  # optional if you like vim as editor

# in order to not always work as root (though it might not be an issue in a container)
useradd -m ${DEVUSER}
cd /home/${DEVUSER}

# only if you need a specific version of a package (just an example):
#pacman -U https://archive.archlinux.org/packages/l/librsync/librsync-1%3A2.0.2-1-x86_64.pkg.tar.xz

# I only test under ArchLinux but if you want to really develop, you should use SSH instead of HTTPS
su - ${DEVUSER} -c 'git clone https://github.com/rdiff-backup/rdiff-backup.git'
su - ${DEVUSER} -c 'git clone https://github.com/rdiff-backup/rdiff-backup-filesrepo.git'

#su - ${DEVUSER} -c 'git clone git@github.com:rdiff-backup/rdiff-backup.git'
#su - ${DEVUSER} -c 'git clone git@github.com:rdiff-backup/rdiff-backup-filesrepo.git'

tar xvf ./rdiff-backup-filesrepo/rdiff-backup_testfiles.tar
# if devuser hasn't the ID 1000, you will need following command, assuming 1234 is the UID/GID:
#./rdiff-backup-filesrepo/rdiff-backup_testfiles.fix.sh 1234 1234

# after that, as `DEVUSER`, following commands should be possible (for example)
#  ./setup.py clean --all
#  ./setup.py build
#  PATH=$PWD/build/scripts-3.8:$PATH PYTHONPATH=$PWD/build/lib.linux-x86_64-3.8 rdiff-backup --version
#  PATH=$PWD/build/scripts-3.8:$PATH PYTHONPATH=$PWD/build/lib.linux-x86_64-3.8 python testing/eas_aclstest.py

