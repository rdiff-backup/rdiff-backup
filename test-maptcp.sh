#! /bin/sh -pe

# libhsync test case.
# Copyright (C) 2000 by Martin Pool
# $Id$

# Test the mapptr routines by running them across a localhost TCP
# socket.  We try several different strategies for generating the
# sequence of commands, and also for doing IO.

from=$tmpdir/basis
new=$tmpdir/new.tmp
cmds=$tmpdir/cmds
expect=$tmpdir/expect
port=$tmpdir/port

run_test cat $srcdir/libhsync.a >$from

# NB: Can't use the `forward' pattern with map_copy because it
# discards buffered data and can't step backwards even to the previous
# region.

for strategy in decoder stepping ones 
do
    run_test genmaptest $strategy 1000 $cmds $expect $from

    for ioargs in '-c' '' '-k' '-n -k -s'
    do
	run_test sockrun -- hsmapread $debug $ioargs `cat $cmds` <$from >$new
	run_test cmp $expect $new
    done
done

for strategy in forward 
do
    run_test genmaptest $strategy 1000 $cmds $expect $from

    for ioargs in '' '-k' '-n -k -s'
    do
	run_test sockrun -- hsmapread $debug $ioargs `cat $cmds` <$from >$new
	run_test cmp $expect $new
    done
done

# the output files are pretty huge, so if we completed successfully
# delete them.  if we failed they're left behind so that you can find
# the cause of death.

run_test rm $expect $new $cmds $from
