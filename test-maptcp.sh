#! /bin/sh -pe

# libhsync test case.
# Copyright (C) 2000 by Martin Pool
# $Id$

# Test the mapptr routines by running them across a localhost TCP
# socket.

from=$tmpdir/basis
new=$tmpdir/new.tmp
cmds=$tmpdir/cmds
expect=$tmpdir/expect
port=$tmpdir/port

run_test cat $srcdir/*.{c,h,sh} >$from

run_test genmaptest forward 2000 $cmds $expect $from

# In this case we make the input be a pipe, which is a reasonable
# imitation of a socketpair.  This makes sure that map_ptr works OK on
# a file on which we can neither seek nor determine the real size.

# Also, we try this using different async IO strategies:
# -k means `insist on mapping the whole region'
# -n means `use nonblocking reads'
# -s means `use select(2)'

for ioargs in '' '-k' '-n -s'
do
    run_test sockrun -D -- hsmapread $test_opts $ioargs - `cat $cmds` <$from >$new
    run_test cmp $expect $new
done

# the output files are pretty huge, so if we completed successfully
# delete them.  if we failed they're left behind so that you can find
# the cause of death.

run_test rm $expect $new
