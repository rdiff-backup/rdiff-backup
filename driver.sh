#! /bin/sh -pe

# Regression test driver for libhsync.

# Copyright (C) 2000 by Martin Pool
# $Id$

# This script doesn't do anything except general setup.  It should be
# passed the name of the actual script file as the first parameter.  

# You can pass additional arguments to give options which are usually
# passed through.  For example in most cases -D will turn on debugging
# trace.

# NB: tests should exit with code 77 if they can't be run but haven't failed.

# TODO: Rather than using source files, write some programs that
# generate random data of defined lengths.  However, it should not be
# totally random: it should have some kind of autocorrelation.  Also,
# perhaps generate random pairs of related files.  Perhaps do this
# using genmaptest.

if [ $# -lt 1 ]
then
    echo 'runtest: must have at least one parameter, the test script'
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
export PATH

testdir=$srcdir/$test_name
tmpdir=$builddir/$test_name.d
[ -d $tmpdir ] || mkdir $tmpdir || exit 2

test_skipped () {
    echo $test_name: skipped; exit 77
}

run_test () {
    if $* 
    then
	:
    else
	echo $test_name: failed: "$*" >&2
	exit 2
    fi
}

# more than this many on any one test gets boring
ntests=300
countdown () {
    if [ $ntests -lt 0 ] 
    then
	echo truncated 1>&2
        exit 0
    fi
    ntests=`expr $ntests - 1`
}

make_input () {
    cat $srcdir/*.h $srcdir/*.sh $srcdir/*.c
}

make_manyfiles() {
    find $srcdir $builddir -type f
}

echo "$test_name"

. $srcdir/$test_script $*

# If nothing failed, then
exit 0