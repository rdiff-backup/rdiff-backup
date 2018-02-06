# Common test utilities for librsync.

# Copyright (C) 2000, 2001, 2014 by Martin Pool

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


# For CMake tests
bindir=$1
if [ -z "$bindir" ]
then
   # Fallback to automake tests
   bindir='..'
fi
echo "BINDIR $bindir"

testinputdir=$srcdir/$test_base.input
tmpdir=`mktemp -d -t librsynctest_XXXXXXXX`
trap "{ rm -r $tmpdir; }" EXIT

block_len=2048

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
bufsizes='0 1 2 3 7 15 100 10000 200000'

run_test () {
    if :|| test -n "$VERBOSE" 
    then
	echo "    $@" >&2
    fi

    "$@" || fail_test "$?" "$@" 
}

fail_test () {
    result=$1
    shift
    echo "not ok $testcounter: returned $result: $@" >&2
    exit 2
}

test_skipped () {
    echo $test_name: skipped; exit 77
}

check_compare() {
    if ! cmp "$1" "$2"
    then
        echo "$test_name: comparison failed from command: $3" >&2
        exit 2
    fi
}

triple_test () {
    buf="$1"
    old="$2"
    new="$3"
    hashopt="$4"
    
    run_test $bindir/rdiff $debug $hashopt -f -I$buf -O$buf $stats signature --block-size=$block_len \
             $old $tmpdir/sig
    run_test $bindir/rdiff $debug $hashopt -f -I$buf -O$buf $stats delta $tmpdir/sig $new $tmpdir/delta
    run_test $bindir/rdiff $debug $hashopt -f -I$buf -O$buf $stats patch $old $tmpdir/delta $tmpdir/new
    check_compare $new $tmpdir/new "triple -f -I$buf -O$buf $old $new"
}

make_input () {
    cat $srcdir/COPYING
}
