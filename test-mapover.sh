#! /bin/sh -pe

# libhsync test case.

# Copyright (C) 2000 by Martin Pool
# $Id$

from=$srcdir/COPYING
new=$tmpdir/new.tmp
cmds=$tmpdir/cmds
expect=$tmpdir/expect

for seed in `seq 10`
do
run_test genmaptest mapover 1000 $cmds $expect $from $seed

for ioargs in '' '-k' '-n -s -k'
do
    run_test hsmapread $debug `cat $cmds` <$from >$new
    run_test cmp $expect $new
done
done # seed

# the output files are pretty huge, so if we completed successfully
# delete them.  if we failed they're left behind so that you can find
# the cause of death.

run_test rm $expect $new
