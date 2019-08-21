# rdiff-backup build environment (for developers)
FROM debian:sid

# General Debian build dependencies
RUN DEBIAN_FRONTEND=noninteractive apt-get update -yqq && \
    apt-get install -y --no-install-recommends \
    devscripts \
    equivs \
    curl \
    ccache \
    git \
    git-buildpackage \
    pristine-tar

# Build dependencies specific for rdiff-backup
RUN DEBIAN_FRONTEND=noninteractive apt-get update -yqq && \
    apt-get install -y --no-install-recommends \
    librsync-dev \
    python3-all-dev \
    python3-pylibacl \
    python3-pyxattr

# Build dependencies specific for rdiff-backup development and testing
RUN DEBIAN_FRONTEND=noninteractive apt-get update -yqq && \
    apt-get install -y --no-install-recommends \
    tox \
    rdiff \
    libacl1-dev # /usr/include/sys/acl.h
 
# Build dev image
# docker build --pull --tag rdiff-backup-dev:debian-sid .

# Build rdiff-backup
# docker run -it -v ${PWD}:/build -w /build rdiff-backup-dev:debian-sid ./setup.py build

# Run tests
# docker run -it -v ${PWD}:/build -w /build rdiff-backup-dev:debian-sid bash
#   curl -LO https://github.com/ericzolf/rdiff-backup/releases/download/Testfiles2019-08-10/rdiff-backup_testfiles_2019-08-10.tar.gz
#   tar xvf *.tar.gz
#   mv rdiff-backup_testfiles testfiles
#   tox -e py37

