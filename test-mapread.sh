#! /bin/sh -pe

# libhsync test case.
# Copyright (C) 2000 by Martin Pool

# Test the map_ptr input routines, by extracting chunks of a file
# using a known-good Python implementation, and also by passing the
# same parameters to the hsmapread driver.

# $Id$

from=$srcdir/COPYING
new=$tmpdir/new.tmp
cmds=$tmpdir/cmds
expect=$tmpdir/expect

run_test genmaptest map 1000 $cmds $expect $from
run_test hsmapread $from `cat $cmds` >$new
run_test cmp $expect $new

# the output files are pretty huge, so if we completed successfully
# delete them.  if we failed they're left behind so that you can find
# the cause of death.

run_test rm $expect $cmds $new
