#! /bin/sh -pe

# Regression test driver for libhsync.

# Copyright (C) 2000 by Martin Pool

# This script doesn't do anything except general setup.  It should be
# passed the name of the actual script file as the first parameter.

if [ $# != 1 ]
then
    echo 'test-driver: must have one parameter, the test script'
    exit 1
fi

test_script=$1
test_name=`basename $1 .sh`

if [ "$srcdir" = "" ]
then
    srcdir=`dirname $0`
fi
srcdir=`cd $srcdir; pwd`
builddir=`pwd`

PATH=$builddir:$srcdir:$PATH

testdir=$srcdir/$test_name
tmpdir=/tmp/$test_name
[ -d $tmpdir ] || mkdir $tmpdir

function run_test {
    $* || (echo $test_name: failed: "$*" >&2; return 2)
}

echo "$test_name"
