# Makefile to automate rdiff-backup build and install steps

# Currently all steps are run isolated inside a Docker image, but this could
# be extended to have more options.
RUN_COMMAND ?= docker run -i -v ${PWD}/..:/build -w /build/rdiff-backup rdiff-backup-dev:debian-sid

all: clean container test build

test: test-static test-runtime

test-static:
	${RUN_COMMAND} tox -c tox.ini -e flake8

test-runtime: test-runtime-base test-runtime-root test-runtime-slow

test-runtime-files:
	@echo "=== Install files required by the tests ==="
	${RUN_COMMAND} ./setup-testfiles.sh # This must run as root

test-runtime-base: test-runtime-files
	@echo "=== Base tests ==="
	${RUN_COMMAND} tox -c tox.ini -e py37

test-runtime-root: test-runtime-files
	@echo "=== Tests that require root permissions ==="
	${RUN_COMMAND} tox -c tox_root.ini -e py37 # This must be run as root
	# NOTE! Session will user=root inside Docker)

test-runtime-slow: test-runtime-files
	@echo "=== Long running performance tests ==="
	${RUN_COMMAND} tox -c tox_slow.ini -e py37

build:
	# Build rdiff-backup (assumes source is in directory 'rdiff-backup' and it's
	# parent is writeable)
	${RUN_COMMAND} ./setup.py build

container:
	# Build development image
	docker build --pull --tag rdiff-backup-dev:debian-sid .

clean:
	${RUN_COMMAND} rm -rf .tox.root/	.tox/	MANIFEST build/ testing/__pycache__/
