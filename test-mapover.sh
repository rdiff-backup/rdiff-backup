#! /bin/sh -pe

# libhsync test case.
# Copyright (C) 2000 by Martin Pool

# $Id$

source ${srcdir:-.}/testfns.sh $0 $@

from=$srcdir/COPYING
new=$tmpdir/new.tmp
cmds=$tmpdir/cmds
expect=$tmpdir/expect

run_test $srcdir/gen-mapover.py $cmds $expect $from
run_test hsmapread $from `cat $cmds` >$new
run_test cmp $expect $new

# the output files are pretty huge, so if we completed successfully
# delete them.  if we failed they're left behind so that you can find
# the cause of death.

run_test rm $expect $new
