#! /bin/sh -pe

# libhsync test case.
# Copyright (C) 2000 by Martin Pool

# Test the inbuf input routines, by extracting chunks of a file
# using a known-good Python implementation, and also by passing the
# same parameters to the hsmapread driver.

# $Id$

source ${srcdir:-.}/testfns.sh $0 $@

from=$tmpdir/basis
new=$tmpdir/new.tmp
cmds=$tmpdir/cmds
expect=$tmpdir/expect

run_test cat $srcdir/*.{c,h,sh} >$from

run_test genmaptest forward 5000 $cmds $expect $from

# In this case we make the input be a pipe, which is a reasonable
# imitation of a socketpair.  This makes sure that map_ptr works OK on
# a file on which we can neither seek nor determine the real size.

# Also, we try this using different async IO strategies:
# -k means `insist on mapping the whole region'
# -n means `use nonblocking reads'
# -s means `use select(2)'

for ioargs in '' '-k' '-n -s'
do
    cat $from | run_test hsmapread $ioargs - `cat $cmds` >$new
    run_test cmp $expect $new
done

# the output files are pretty huge, so if we completed successfully
# delete them.  if we failed they're left behind so that you can find
# the cause of death.

run_test rm $expect $new
