#! /bin/sh -pe

source ${srcdir:-.}/testfns.sh $0 $@

from=$srcdir/COPYING
new=$tmpdir/new.tmp
cmds=$tmpdir/cmds
expect=$tmpdir/expect

run_test $srcdir/gen-maptest.py $cmds $expect $from
run_test hsmapread $from `cat $cmds` >$new
run_test cmp $expect $new
