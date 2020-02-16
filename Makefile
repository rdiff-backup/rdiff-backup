# Makefile to automate rdiff-backup build and install steps

# Currently all steps are run isolated inside a Docker image, but this could
# be extended to have more options.
RUN_COMMAND ?= docker run --rm -i -v ${PWD}/..:/build/ -w /build/$(shell basename `pwd`) rdiff-backup-dev:debian-sid

# Define SUDO=sudo if you don't want to run the whole thing as root
# we set SUDO="sudo -E env PATH=$PATH" if we want to keep the whole environment
SUDO ?=

all: clean container test build

test: test-static test-runtime

test-static:
	${RUN_COMMAND} tox -c tox.ini -e flake8

test-runtime: test-runtime-base test-runtime-root test-runtime-slow

test-runtime-files:
	@echo "=== Install files required by the tests ==="
	${RUN_COMMAND} ./tools/setup-testfiles.sh  # This must run as root or sudo be available

test-runtime-base: test-runtime-files
	@echo "=== Base tests ==="
	${RUN_COMMAND} tox -c tox.ini -e py

test-runtime-root: test-runtime-files
	@echo "=== Tests that require root permissions ==="
	${RUN_COMMAND} ${SUDO} tox -c tox_root.ini -e py  # This must run as root
	# NOTE! Session will user=root inside Docker)

test-runtime-slow: test-runtime-files
	@echo "=== Long running performance tests ==="
	${RUN_COMMAND} tox -c tox_slow.ini -e py

build:
	# Build rdiff-backup (assumes src/ is in directory 'rdiff-backup' and it's
	# parent is writeable)
	${RUN_COMMAND} ./setup.py build

bdist_wheel:
	# Prepare wheel for deployment.
	# See the notes for target "build"
	# auditwheel unfortunately does not work with modern glibc
	${RUN_COMMAND} ./setup.py bdist_wheel
	# ${RUN_COMMAND} auditwheel repair dist/*.whl

sdist:
	# Prepare wheel for deployment.
	${RUN_COMMAND} ./setup.py sdist

bdist_deb:
	${RUN_COMMAND} debian/autobuild.sh

container:
	# Build development image
	docker build --pull --tag rdiff-backup-dev:debian-sid .

clean:
	${RUN_COMMAND} rm -rf .tox/ MANIFEST build/ testing/__pycache__/ dist/
	${RUN_COMMAND} ${SUDO} rm -rf .tox.root/
