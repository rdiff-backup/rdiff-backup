#! /bin/sh -pe

# libhsync test case.

# Copyright (C) 2000 by Martin Pool
# $Id$

# Test that inbufs do the right thing near EOF.

from=$tmpdir/basis
new=$tmpdir/new.tmp
cmds=$tmpdir/cmds

run_test date >$from

# In this case we make the input be a pipe, which is a reasonable
# imitation of a socketpair.  This makes sure that map_ptr works OK on
# a file on which we can neither seek nor determine the real size.
for ioargs in '' '-k' '-n -s -k'
do
    cat $from | run_test hsmapread $ioargs 0,1000 >$new
    run_test cmp $from $new
done


