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

run_test cat $srcdir/*.{c,h,py,sh} >$from

run_test $srcdir/gen-inbuftest.py $cmds $expect $from

# In this case we make the input be a pipe, which is a reasonable
# imitation of a socketpair.  This makes sure that map_ptr works OK on
# a file on which we can neither seek nor determine the real size.
cat $from | run_test hsmapread - `cat $cmds` >$new
run_test cmp $expect $new

# the output files are pretty huge, so if we completed successfully
# delete them.  if we failed they're left behind so that you can find
# the cause of death.

run_test rm $expect $new
