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
    libacl1-dev # /usr/include/sys/acl.h \
    rdiff

# Build dev image
# docker build --pull --tag rdiff-backup-dev:debian-sid .

# Build rdiff-backup
# docker run -it -v ${PWD}:/build -w /build rdiff-backup-dev:debian-sid ./setup.py build

# Run tests
# docker run -it -v ${PWD}:/build -w /build rdiff-backup-dev:debian-sid bash
#   curl -O https://download-mirror.savannah.gnu.org/releases/rdiff-backup/testfiles.tar.gz && tar xvf testfiles.tar.gz
#   tox -e py37
