#! /bin/sh -pe

# Regression test suite for libhsync.

# Copyright (C) 2000 by Martin Pool

# Check that the sum generated is independant of whether we're
# generating from scratch or as a delta.

source ${srcdir:-.}/testfns.sh $0 $@

diff=$tmpdir/diff.tmp
files=`find ${srcdir:-.} -type f |head -40`
newsig=$tmpdir/newsig.tmp
out=$tmpdir/out.tmp
origsig=$tmpdir/origsig.tmp
old=/dev/null

fromsig=$tmpdir/fromsig.tmp
fromlt=$tmpdir/fromlt.tmp
ltfile=$tmpdir/lt.tmp

for from in $files
do
    run_test hsnad /dev/null <$from >$ltfile
    run_test hsdecode /dev/null $origsig /dev/null $ltfile 

    for new in $files
    do
	run_test hsnad $origsig <$new >$diff 
        run_test hsdecode $old $newsig $out $diff 
   
        run_test cmp $out $new
   done
done
    
    
