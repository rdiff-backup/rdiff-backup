#! /bin/sh -pe

# Regression test suite for libhsync.

# Copyright (C) 2000 by Martin Pool
# $Id$

# OK, this is how we test feeding hsync it's own filth.  Starting
# with an empty signature, we generate the difference from one
# file to another.

diff=$tmpdir/diff.tmp
files=`echo $srcdir/*.c|head -20`
out=$tmpdir/out.tmp
sig=$tmpdir/sig.tmp
newsig=$tmpdir/newsig.tmp
old=/dev/null

fromsig=$tmpdir/fromsig.tmp
fromlt=$tmpdir/fromlt.tmp
ltfile=$tmpdir/lt.tmp

for from in $files
do
    run_test hsnad /dev/null <$from >$ltfile
    run_test hsdecode /dev/null $sig $out $ltfile

    run_test cmp $out $from

    for new in $files
    do
	countdown
        run_test hsnad $sig <$new >$diff
        run_test hsdecode $old $newsig $out $diff 
    
        run_test cmp $out $new
    done
done
    
    
