#!/bin/sh
set -e -x

pybindirs="/opt/python/cp35*/bin /opt/python/cp36*/bin /opt/python/cp37*/bin /opt/python/cp38*/bin"

# Install a system package required by our library
yum install -y librsync-devel

# Compile wheels
for PYBIN in $pybindirs; do
    "${PYBIN}/pip" wheel /io/ -w dist/
done

# Bundle external shared libraries into the wheels
for whl in dist/*.whl; do
    auditwheel repair "$whl" --plat $PLAT -w /io/dist/
done

# Install packages
for PYBIN in $pybindirs; do
    "${PYBIN}/pip" install rdiff-backup --no-index -f /io/dist
done
