#! /bin/sh -pe

# Regression test driver for libhsync.

# Copyright (C) 2000 by Martin Pool
# $Id$

# This script doesn't do anything except general setup.  It should be
# passed the name of the actual script file as the first parameter.
# Normally you don't call this directly, but instead it's sourced near
# the top of every test script to do setup.

# You can pass additional arguments to give options which are usually
# passed through.  For example in most cases -D will turn on debugging
# trace.

# NB: tests should exit with code 77 if they can't be run but haven't failed.

if [ $# -lt 1 ]
then
    echo 'test-driver: must have at least one parameter, the test script'
    exit 1
fi

test_script=$1
shift
test_name=`basename $test_script .sh`
test_opts="$*"

if [ "$srcdir" = "" ]
then
    srcdir=`dirname $0`
fi
srcdir=`cd $srcdir; pwd`
builddir=`pwd`

PATH=$builddir:$srcdir:$PATH

testdir=$srcdir/$test_name
tmpdir=$builddir/$test_name.d
[ -d $tmpdir ] || mkdir $tmpdir || exit 2

function test_skipped {
    echo $test_name: skipped; return 77
}

function run_test {
    $* || (echo $test_name: failed: "$*" >&2; return 2)
}

# more than this many on any one test gets boring
ntests=300
function countdown {
    [ $ntests -lt 0 ] && exit 0
}

echo "$test_name"



