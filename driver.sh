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

# Don't ever allow undefined shell variables to default
set -u

if [ $# -lt 1 ]
then
    echo 'runtest: must have at least one parameter, the test script'
    exit 1
fi

test_script=$1
shift
test_name=`basename $test_script .sh`

# TODO: Add more pair instructions here
delta_instr="
0,1024
0,2048
1024,1024:0,1024
0,1025
0,1
0,10
0,1000
0,2000
0,10000
0,100000
1,10
1,10000
0,2000:2000,2000:4000,100000
1,10000:0,1:10000,1000000
10,1:8,4:6,8:4,10:2,12
0,10000:0,10000:0,10000
"

# Process command-line options
trace=:
stats=
debug=
time=
for o in "$@"
do
    case "$o" in 
    -D)
	debug=-D
	;;
    -S)
	stats=-S
	;;
    -x)
	trace='set -x'
	;;
    -t)
	time='time'
	;;
    *)
	echo "unrecognized driver option $o" >&2
	exit 1
	;;
    esac
done

if [ "${srcdir:-}" = "" ]
then
    srcdir=`dirname $0`
fi
srcdir=`cd $srcdir; pwd`
builddir=`pwd`

PATH=$builddir:$srcdir:$PATH
export PATH

testdir=$srcdir/$test_name
tmpdir=$builddir/`echo $test_name | sed -e s/^test-/tmp-/`
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
    ntests=`expr $ntests - 1` || exit 0
}

make_input () {
    cat $srcdir/COPYING
}

#  make_manyfiles() {
#      find $srcdir $builddir -type f |head -1000
#  }

echo "$test_name"

$trace
. $test_script $*

rm -f $tmpdir/*
rmdir $tmpdir

# If nothing failed, then
exit 0