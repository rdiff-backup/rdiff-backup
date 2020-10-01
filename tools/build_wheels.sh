#!/bin/sh
set -e -x

pybindirs="$*"

# Install a system package required by our library
yum install -y librsync-devel

# Compile wheels
for PYBIN in $pybindirs; do
    "${PYBIN}/pip" install --user \
        'importlib-metadata ~= 1.0 ; python_version < "3.8"'
    "${PYBIN}/pip" wheel /io/ -w dist/
done

# Bundle external shared libraries into the wheels
for whl in dist/rdiff_backup*.whl; do
    auditwheel repair "$whl" --plat $PLAT -w /io/dist/
done

# Install packages
for PYBIN in $pybindirs; do
    "${PYBIN}/pip" install rdiff-backup --no-index -f /io/dist
done
