#!/bin/sh
set -e -x

basedir=$1
plat=$2
shift 2
pybindirs="$@"

build_dir=${basedir}/build
dist_dir=${basedir}/dist

# Install a system package required by our library
yum install -y librsync-devel rubygems

# asciidoctor 2.x isn't compatible with Ruby 1.8
ruby_major=$(rpm -qi ruby | awk -F' *[:.] *' '$1=="Version" {print $2}')
if [[ ${ruby_major} -lt 2 ]]
then
	gem install asciidoctor -v 1.5.8
else
	gem install asciidoctor
fi

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
