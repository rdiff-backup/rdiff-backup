#!/bin/sh
set -e -x

basedir=$1
shift
plat=$2
shift
pybindirs="$@"

build_dir=${basedir}/build
dist_dir=${basedir}/dist

# Install a system package required by our library
yum install -y librsync-devel

# Compile wheels
for PYBIN in $pybindirs; do
    "${PYBIN}/pip" install --user \
        'importlib-metadata ~= 1.0 ; python_version < "3.8"' 'PyYAML'
    "${PYBIN}/pip" wheel ${basedir} -w ${build_dir}/
done

# Bundle external shared libraries into the wheels
for whl in ${build_dir}/rdiff_backup*.whl; do
    auditwheel repair "$whl" --plat ${plat} -w ${dist_dir}/
done

# Install packages
for PYBIN in $pybindirs; do
    "${PYBIN}/pip" install rdiff-backup --no-index -f ${dist_dir}
done
