#! /bin/sh -pe

# Regression test suite for libhsync.

# Copyright (C) 2000 by Martin Pool
# $Id$

# Try some files specifically created to trip the library up.

source ${srcdir:-.}/testfns.sh $0 $@

files=`ls $srcdir/in-tricky/in-*`

diff=$tmpdir/diff.tmp
out=$tmpdir/out.tmp
sig=$tmpdir/sig.tmp
newsig=$tmpdir/newsig.tmp
old=/dev/null

fromsig=$tmpdir/fromsig.tmp
fromlt=$tmpdir/fromlt.tmp
ltfile=$tmpdir/lt.tmp

for from in $files
do
    run_test hsnad $test_opts /dev/null <$from >$ltfile
    run_test hsdecode $test_opts /dev/null $sig $out $ltfile
	
    run_test cmp $out $from
	
    for new in $files
    do
	countdown
	run_test hsnad $test_opts $sig <$new >$diff
	run_test hsdecode $test_opts $from $newsig $out $diff 
	    
	run_test cmp $out $new
    done
done
