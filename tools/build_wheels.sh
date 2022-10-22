#!/bin/sh
set -e -x

basedir=$1
plat=$2
shift 2
pybindirs="$@"

build_dir=${basedir}/build
dist_dir=${basedir}/dist
requs_dir=${basedir}/requs

# Install a system package required by our library
if ! yum install -y librsync-devel rubygems
then  # re-try with EPEL
	yum install -y epel-release
	yum install -y librsync-devel rubygems
fi

# asciidoctor 2.x isn't compatible with Ruby 1.8
ruby_version=$(rpm -qi ruby | awk -F' *: *' '$1=="Version" {print $2}')
case "${ruby_version}" in
	1.*)
		gem install asciidoctor -v 1.5.8
		;;
	2.0.*)
		gem install asciidoctor -v 2.0.12
		;;
	2.[12].*)
		gem install asciidoctor -v 2.0.17
		;;
	*)
		gem install asciidoctor
		;;
esac

# Compile wheels
for PYBIN in $pybindirs; do
    "${PYBIN}/pip" install --user -r ${requs_dir}/base.txt
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
