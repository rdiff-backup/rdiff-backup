# Makefile to automate rdiff-backup build and install steps

# By default, steps are run directly on the host (no isolation).
# Set RUN_COMMAND to wrap each step, e.g. in a Docker container, if desired.
# e.g.: docker run --rm -i -v ${PWD}/..:/build/ -w /build/$(shell basename `pwd`) rdiff-backup-dev:debian-sid
RUN_COMMAND ?=

# Define SUDO=sudo if you don't want to run the whole thing as root
# we set SUDO="sudo -E env PATH=$PATH" if we want to keep the whole environment
SUDO ?=

.NOTPARALLEL: all test-misc

all: clean test build

test: test-static test-runtime

check:
	@command -v rdiff >/dev/null && echo "rdiff is installed" || { echo "Error: rdiff is not installed"; exit 1; }

test-static:
	${RUN_COMMAND} tox -c tox.ini -e check-static

test-runtime: test-runtime-base test-runtime-root test-runtime-slow

test-runtime-files:
	@echo "=== Install files required by the tests ==="
	${RUN_COMMAND} ./tools/setup-testfiles.sh  # This must run as root or sudo be available

test-runtime-base: check test-runtime-files
	@echo "=== Base tests ==="
	${RUN_COMMAND} tox -c tox.ini -e py

test-runtime-root: test-runtime-files
	@echo "=== Tests that require root permissions ==="
	${RUN_COMMAND} ${SUDO} tox -c tox_root.ini -e py  # This must run as root
	# NOTE! Session will user=root inside Docker)

test-runtime-slow: test-runtime-files
	@echo "=== Long running performance tests ==="
	${RUN_COMMAND} tox -c tox_slow.ini -e py

test-misc: clean build test-static test-runtime-slow

build:
	# Build rdiff-backup (assumes src/ is in directory 'rdiff-backup' and
	# its parent is writeable)
	${RUN_COMMAND} pyproject-build

dist_deb:
	${RUN_COMMAND} debian/autobuild.sh

container:
	# Build development image
	docker build --pull --tag rdiff-backup-dev:debian-sid .

clean:
	${RUN_COMMAND} rm -rf .tox/ MANIFEST build/ testing/__pycache__/ dist/
	${RUN_COMMAND} ${SUDO} rm -rf .tox.root/
