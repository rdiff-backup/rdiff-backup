#! /bin/sh -pe

# Regression test driver for libhsync.

# Copyright (C) 2000, 2001 by Martin Pool
# $Id$

# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public License
# as published by the Free Software Foundation; either version 2.1 of
# the License, or (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
# 
# You should have received a copy of the GNU Lesser General Public
# License along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.

# This script doesn't do anything except general setup.  It should be
# passed the name of the actual script file as the first parameter.  

# You can pass additional arguments to give options which are usually
# passed through.  For example in most cases -D will turn on debugging
# trace.

# NB: Tests should exit with code 77 if they can't be run but haven't
# failed.

# NB: We can't rely on having the executable bit set on this script or
# any other, because CVS doesn't always update them properly.

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
test_name=`basename $test_script`
test_base=`basename $test_script .test`

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
bufsizes='1 2 3 7 15 100 600 4096 10000 200000'

# Process command-line options
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
	VERBOSE=1
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

testdir=$srcdir/$test_base.input
tmpdir=$builddir/$test_base.tmp
[ -d $tmpdir ] || mkdir $tmpdir || exit 2

test_skipped () {
    echo $test_name: skipped; exit 77
}

fail_test () {
    result=$1
    shift
    echo "$test_name: returned $result: $@" >&2
    exit 2
}

check_compare() {
    if ! cmp "$1" "$2"
    then
        echo "$test_name: comparison failed from command: $3" >&2
        exit 2
    fi
}

run_test () {
    if [ -n "${VERBOSE:-}" ] 
    then
	echo "    $@" >&2
    else
        show_progress
    fi

    "$@" >$builddir/testout.log 2>$builddir/testerr.log || fail_test "$?" "$@" 
}

# more than this many on any one test gets boring
ntests=300
countdown () {
    ntests=`expr $ntests - 1` || exit 0
}

make_input () {
    cat $srcdir/COPYING
}

show_progress () {
    echo -n .
}

echo -n "$test_name: "

. $test_script $*

echo OK

rm -f $tmpdir/*
rmdir $tmpdir

# If nothing failed, then
exit 0
